"""Pruebas de integracion para consulta y actualizacion en vivo de parametros (T-36)."""

from __future__ import annotations

from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.config import obtener_configuracion
from app.main import app


def generar_token(usuario_id: str) -> str:
    cfg = obtener_configuracion()
    secreto = cfg.SUPABASE_JWT_SECRET or "secreto_jwt_prueba_local_32_bytes_min"
    cfg.SUPABASE_JWT_SECRET = secreto
    return jwt.encode(
        {"sub": usuario_id, "email": "admin@armenia.gov.co"}, secreto, algorithm="HS256"
    )


async def crear_perfil(uid: str, rol: str) -> None:
    async with sesion_transaccional() as sesion:
        sql = text("""
            INSERT INTO perfil (id, alias, rol, estado, reputacion)
            VALUES (:id, :alias, CAST(:rol AS rol_usuario), 'activa', 0.9)
            ON CONFLICT (id) DO UPDATE SET rol = CAST(:rol AS rol_usuario), estado = 'activa';
        """)
        await sesion.execute(sql, {"id": uid, "alias": f"u_{uid[:8]}", "rol": rol})


@pytest.mark.asyncio
async def test_listar_parametros_seguridad_y_contenido() -> None:
    rep_id = str(uuid4())
    mod_id = str(uuid4())
    await crear_perfil(rep_id, "reportante")
    await crear_perfil(mod_id, "moderador")

    token_rep = generar_token(rep_id)
    token_mod = generar_token(mod_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Reportante recibe 403
        r_rep = await cliente.get(
            "/v1/moderacion/parametros", headers={"Authorization": f"Bearer {token_rep}"}
        )
        assert r_rep.status_code == 403

        # Moderador recibe 200 con la lista de parametros
        r_mod = await cliente.get(
            "/v1/moderacion/parametros", headers={"Authorization": f"Bearer {token_mod}"}
        )
        assert r_mod.status_code == 200
        items = r_mod.json()["datos"]
        assert len(items) >= 40
        claves = {it["clave"] for it in items}
        assert "precio.min_cop" in claves
        assert "precio.max_cop" in claves
        assert "riesgo.pesos" in claves


@pytest.mark.asyncio
async def test_actualizar_parametros_valido_e_invalido() -> None:
    mod_id = str(uuid4())
    await crear_perfil(mod_id, "moderador")
    token_mod = generar_token(mod_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # 1. Intentar actualizar fuera de rango (precio.min_cop < 10) -> 422
        r_inv1 = await cliente.put(
            "/v1/moderacion/parametros",
            headers={"Authorization": f"Bearer {token_mod}"},
            json={"parametros": {"precio.min_cop": 5}},
        )
        assert r_inv1.status_code == 422

        # 2. Intentar actualizar con pesos que no suman 1.0 -> 422
        r_inv2 = await cliente.put(
            "/v1/moderacion/parametros",
            headers={"Authorization": f"Bearer {token_mod}"},
            json={
                "parametros": {
                    "riesgo.pesos": {
                        "sin_foto": 0.5,
                        "cuenta_nueva": 0.5,
                        "rafaga": 0.5,
                        "reputacion_baja": 0.5,
                    }
                }
            },
        )
        assert r_inv2.status_code == 422

        # 3. Intentar parametro fantasma -> 422
        r_inv3 = await cliente.put(
            "/v1/moderacion/parametros",
            headers={"Authorization": f"Bearer {token_mod}"},
            json={"parametros": {"parametro_inexistente": 100}},
        )
        assert r_inv3.status_code == 422

        # 4. Actualizacion valida dentro de rangos
        r_ok = await cliente.put(
            "/v1/moderacion/parametros",
            headers={"Authorization": f"Bearer {token_mod}"},
            json={"parametros": {"precio.min_cop": 75, "cache.ttl_segundos": 45}},
        )
        assert r_ok.status_code == 200
        datos = {it["clave"]: it["valor"] for it in r_ok.json()["datos"]}
        assert datos["precio.min_cop"] == 75
        assert datos["cache.ttl_segundos"] == 45

        # 5. Restaurar valores originales
        r_rest = await cliente.put(
            "/v1/moderacion/parametros",
            headers={"Authorization": f"Bearer {token_mod}"},
            json={"parametros": {"precio.min_cop": 50, "cache.ttl_segundos": 60}},
        )
        assert r_rest.status_code == 200
        rest_datos = {it["clave"]: it["valor"] for it in r_rest.json()["datos"]}
        assert rest_datos["precio.min_cop"] == 50
