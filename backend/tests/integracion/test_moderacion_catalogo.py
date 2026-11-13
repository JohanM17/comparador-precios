"""Pruebas de integracion para endpoints de moderacion y auditoria (Tarea T-15)."""

from __future__ import annotations

from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.adaptadores.open_food_facts import AdaptadorOpenFoodFacts
from app.bd import sesion_transaccional
from app.config import obtener_configuracion
from app.main import app
from app.modulos.moderacion.api import obtener_puerto_catalogo


def generar_token(usuario_id: str) -> str:
    """Genera un token JWT de prueba firmado con el secreto local."""
    cfg = obtener_configuracion()
    secreto = cfg.SUPABASE_JWT_SECRET or "secreto_jwt_prueba_local_32_bytes_min"
    cfg.SUPABASE_JWT_SECRET = secreto
    payload = {"sub": usuario_id, "email": "mod@armenia.gov.co"}
    return jwt.encode(payload, secreto, algorithm="HS256")


async def asegurar_perfil(usuario_id: str, rol: str) -> None:
    """Inserta o actualiza un perfil en la tabla perfil de PostgreSQL."""
    async with sesion_transaccional() as sesion:
        alias = f"usr_{usuario_id[:8]}"
        sql = text("""
            INSERT INTO perfil (id, alias, rol, estado, reputacion)
            VALUES (:id, :alias, CAST(:rol AS rol_usuario), 'activa', 0.8)
            ON CONFLICT (id) DO UPDATE SET rol = CAST(:rol AS rol_usuario), estado = 'activa';
        """)
        await sesion.execute(sql, {"id": usuario_id, "alias": alias, "rol": rol})


@pytest.mark.asyncio
async def test_acceso_denegado_para_no_moderadores() -> None:
    """Verifica que un usuario consumidor reciba 403 PROHIBIDO en rutas de moderacion."""
    user_id = str(uuid4())
    await asegurar_perfil(user_id, "reportante")
    token = generar_token(user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.post(
            "/v1/moderacion/productos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre": "Prod No Autorizado", "categoria_id": 1, "unidad_base": "g"},
        )
        assert resp.status_code == 403
        assert resp.json()["codigo"] == "PROHIBIDO"


@pytest.mark.asyncio
async def test_crear_y_actualizar_producto_con_auditoria() -> None:
    """Verifica ciclo de vida de producto y registro inmutable en auditoria."""
    mod_id = str(uuid4())
    await asegurar_perfil(mod_id, "moderador")
    token = generar_token(mod_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # 1. Crear producto
        nombre_prod = f"Harina Prueba {mod_id[:6]}"
        resp_crear = await cliente.post(
            "/v1/moderacion/productos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre": nombre_prod, "categoria_id": 1, "unidad_base": "g"},
        )
        assert resp_crear.status_code == 201
        prod = resp_crear.json()
        prod_id = prod["id"]
        assert prod["nombre"] == nombre_prod

        # 2. Actualizar producto
        resp_act = await cliente.patch(
            f"/v1/moderacion/productos/{prod_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre": f"{nombre_prod} Extra", "imagen_url": "https://img.com/h.png"},
        )
        assert resp_act.status_code == 200
        assert resp_act.json()["nombre"] == f"{nombre_prod} Extra"

        # 3. Comprobar auditoria en PostgreSQL
        async with sesion_transaccional() as sesion:
            filas = (
                await sesion.execute(
                    text("""
                        SELECT accion, entidad, entidad_id
                        FROM auditoria
                        WHERE entidad_id = :entidad_id
                        ORDER BY creado_en ASC;
                    """),
                    {"entidad_id": prod_id},
                )
            ).fetchall()
            acciones = [f[0] for f in filas]
            assert "crear_producto" in acciones
            assert "actualizar_producto" in acciones


@pytest.mark.asyncio
async def test_crear_presentacion_y_prohibir_modificar_cantidad_base() -> None:
    """Verifica calculo de cantidad_base y prohibicion taxativa de editarla (T-15)."""
    mod_id = str(uuid4())
    await asegurar_perfil(mod_id, "moderador")
    token = generar_token(mod_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # 1. Obtener o crear un producto base
        resp_p = await cliente.post(
            "/v1/moderacion/productos",
            headers={"Authorization": f"Bearer {token}"},
            json={"nombre": f"Lentejas {mod_id[:6]}", "categoria_id": 1, "unidad_base": "g"},
        )
        prod_id = resp_p.json()["id"]

        # 2. Crear presentacion de 1/2 libra (250 g)
        resp_pres = await cliente.post(
            "/v1/moderacion/presentaciones",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "producto_id": prod_id,
                "marca": "Granos del Valle",
                "valor_cantidad": 250.0,
                "unidad": "g",
                "multiplicador": 1,
            },
        )
        assert resp_pres.status_code == 201
        pres = resp_pres.json()
        pres_id = pres["id"]
        assert float(pres["cantidad_base"]) == 250.0

        # 3. Criterio T-15: Prohibir taxativamente modificar cantidad_base -> 422 VALIDACION
        resp_patch_invalido = await cliente.patch(
            f"/v1/moderacion/presentaciones/{pres_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"cantidad_base": 500.0},
        )
        assert resp_patch_invalido.status_code == 422
        assert resp_patch_invalido.json()["codigo"] == "VALIDACION"

        # 4. Modificar marca valida -> 200 OK
        resp_patch_valido = await cliente.patch(
            f"/v1/moderacion/presentaciones/{pres_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"marca": "Granos Premium"},
        )
        assert resp_patch_valido.status_code == 200
        assert resp_patch_valido.json()["marca"] == "Granos Premium"


@pytest.mark.asyncio
async def test_circuit_breaker_catalogo_externo_degrada_sin_error_500() -> None:
    """Verifica que el Circuit Breaker intercepte fallos continuos y abra el circuito."""
    mod_id = str(uuid4())
    await asegurar_perfil(mod_id, "moderador")
    token = generar_token(mod_id)

    adaptador = AdaptadorOpenFoodFacts(umbral_fallos_circuito=3, tiempo_recuperacion_circuito=10.0)
    # Simular 3 fallos consecutivos
    adaptador.registrar_fallo()
    adaptador.registrar_fallo()
    adaptador.registrar_fallo()

    assert adaptador.estado_circuito == "OPEN"
    assert not adaptador.puede_ejecutar()

    # Inyectar el adaptador en app.dependency_overrides
    app.dependency_overrides[obtener_puerto_catalogo] = lambda: adaptador

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
            resp = await cliente.get(
                "/v1/moderacion/catalogo-externo",
                headers={"Authorization": f"Bearer {token}"},
                params={"codigo_barras": "7702001002003"},
            )
            # Debe retornar 200 con degradacion controlada (encontrado=False) y nunca 500
            assert resp.status_code == 200
            cuerpo = resp.json()
            assert not cuerpo["encontrado"]
            assert cuerpo["producto"] is None
    finally:
        app.dependency_overrides.pop(obtener_puerto_catalogo, None)
