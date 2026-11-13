"""Pruebas de integracion para sugerencias de presentacion y moderacion (Tarea T-16)."""

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
    """Genera token JWT firmado con el secreto de prueba."""
    cfg = obtener_configuracion()
    secreto = cfg.SUPABASE_JWT_SECRET or "secreto_jwt_prueba_local_32_bytes_min"
    cfg.SUPABASE_JWT_SECRET = secreto
    payload = {"sub": usuario_id, "email": "test@armenia.gov.co"}
    return jwt.encode(payload, secreto, algorithm="HS256")


async def configurar_usuario(usuario_id: str, rol: str, con_autorizacion: bool) -> None:
    """Configura el perfil y opcionalmente el consentimiento Ley 1581 en PostgreSQL."""
    async with sesion_transaccional() as sesion:
        alias = f"u_{usuario_id[:8]}"
        sql_perfil = text("""
            INSERT INTO perfil (id, alias, rol, estado, reputacion)
            VALUES (:id, :alias, CAST(:rol AS rol_usuario), 'activa', 0.8)
            ON CONFLICT (id) DO UPDATE SET rol = CAST(:rol AS rol_usuario), estado = 'activa';
        """)
        await sesion.execute(sql_perfil, {"id": usuario_id, "alias": alias, "rol": rol})

        if con_autorizacion:
            sql_aut = text("""
                INSERT INTO autorizacion_datos (usuario_id, version_politica, finalidad)
                VALUES (:uid, '1.0', 'Consentimiento expreso para reporte de precios y sugerencias')
                ON CONFLICT DO NOTHING;
            """)
            await sesion.execute(sql_aut, {"uid": usuario_id})


@pytest.mark.asyncio
async def test_sugerencia_exige_autorizacion_ley_1581() -> None:
    """Verifica que sin autorizacion de datos se rechace con 403 AUTORIZACION_REQUERIDA."""
    user_id = str(uuid4())
    await configurar_usuario(user_id, "reportante", con_autorizacion=False)
    token = generar_token(user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.post(
            "/v1/sugerencias-presentacion",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "producto_id": str(uuid4()),
                "texto_libre": "Arroz 1000g familiar",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["codigo"] == "AUTORIZACION_REQUERIDA"


@pytest.mark.asyncio
async def test_flujo_completo_sugerencia_y_aprobacion_moderador() -> None:
    """Verifica el flujo desde la propuesta del reportante hasta la aprobacion en catalogo."""
    reportante_id = str(uuid4())
    moderador_id = str(uuid4())
    await configurar_usuario(reportante_id, "reportante", con_autorizacion=True)
    await configurar_usuario(moderador_id, "moderador", con_autorizacion=True)

    token_rep = generar_token(reportante_id)
    token_mod = generar_token(moderador_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # 1. Obtener producto existente para asociar la sugerencia (arroz tiene unidad_base 'g')
        resp_prod = await cliente.get("/v1/productos", params={"q": "Arroz", "limite": 1})
        datos_prods = resp_prod.json()["datos"]
        assert len(datos_prods) > 0
        prod_id = datos_prods[0]["id"]

        # 2. Reportante envia sugerencia
        resp_sug = await cliente.post(
            "/v1/sugerencias-presentacion",
            headers={"Authorization": f"Bearer {token_rep}"},
            json={
                "producto_id": prod_id,
                "texto_libre": "Bolsa economica de 125 gramos",
                "marca": "Diana Economico",
                "valor_cantidad": 125.0,
                "unidad": "g",
            },
        )
        assert resp_sug.status_code == 201
        datos_sug = resp_sug.json()
        sug_id = datos_sug["id"]
        assert datos_sug["estado"] == "pendiente"

        # 3. Moderador aprueba la sugerencia
        resp_aprob = await cliente.post(
            f"/v1/moderacion/sugerencias/{sug_id}/aprobar",
            headers={"Authorization": f"Bearer {token_mod}"},
            json={
                "marca": "Diana Economico",
                "valor_cantidad": 125.0,
                "unidad": "g",
                "multiplicador": 1,
            },
        )
        assert resp_aprob.status_code == 200
        datos_aprob = resp_aprob.json()
        assert datos_aprob["estado"] == "aprobada"
        pres_id = datos_aprob["presentacion_id"]

        # 4. Verificar que la presentacion nacio en base de datos con cantidad_base calculada
        async with sesion_transaccional() as sesion:
            fila_pres = (
                await sesion.execute(
                    text("SELECT cantidad_base, activa FROM presentacion WHERE id = :id;"),
                    {"id": pres_id},
                )
            ).fetchone()
            assert fila_pres is not None
            assert float(fila_pres[0]) == 125.0
            assert fila_pres[1] is True

            # Verificar que el caso de moderacion se cerro
            fila_caso = (
                await sesion.execute(
                    text("""
                        SELECT estado, decision, moderador_id
                        FROM caso_moderacion
                        WHERE referencia_tabla = 'sugerencia_presentacion' AND referencia_id = :id;
                    """),
                    {"id": sug_id},
                )
            ).fetchone()
            assert fila_caso is not None
            assert fila_caso[0] == "resuelto"
            assert fila_caso[1] == "confirmar"
            assert str(fila_caso[2]) == moderador_id
