"""Pruebas de integracion para deteccion de anomalias estadisticas y rafagas coordinadas (T-32)."""

from __future__ import annotations

from datetime import UTC, datetime
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
    payload = {"sub": usuario_id, "email": f"{usuario_id[:8]}@ejemplo.com"}
    return jwt.encode(payload, secreto, algorithm="HS256")


async def crear_usuario_con_autorizacion(usuario_id: str) -> str:
    token = generar_token(usuario_id)
    alias = f"usr_{usuario_id[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        await cliente.post(
            "/v1/mi-cuenta/autorizacion",
            headers={"Authorization": f"Bearer {token}"},
            json={"alias": alias, "version_politica": "1.0", "acepta": True},
        )
    return token


@pytest.mark.asyncio
async def test_reporte_anomalo_queda_dudoso_y_abre_caso_moderacion() -> None:
    """Verifica que un precio atipico ($900 vs $2600) quede en dudoso y abra caso_moderacion."""
    uid = str(uuid4())
    token = await crear_usuario_con_autorizacion(uid)
    instante = datetime.now(UTC)

    async with sesion_transaccional() as sesion:
        res_pres = (
            await sesion.execute(text("SELECT id, producto_id FROM presentacion LIMIT 1;"))
        ).first()
        res_est = (await sesion.execute(text("SELECT id FROM establecimiento LIMIT 1;"))).first()
        assert res_pres is not None
        assert res_est is not None
        pres_id, prod_id = res_pres[0], res_pres[1]
        est_id = res_est[0]

        # Sembrar 5 referencias normales de $2.600 en los ultimos dias
        for _ in range(5):
            await sesion.execute(
                text("""
                    INSERT INTO reporte_precio (
                        producto_id, presentacion_id, establecimiento_id, precio_cop,
                        cantidad_base_snapshot, precio_por_base, observado_en,
                        estado, estado_original, fuente, conjunto_referencia
                    ) VALUES (
                        :prod_id, :pres_id, :est_id, 2600,
                        1.000, 2600, :ahora,
                        'aceptado', 'aceptado', 'usuario', 'presentacion_tienda'
                    );
                """),
                {"prod_id": prod_id, "pres_id": pres_id, "est_id": est_id, "ahora": instante},
            )

    # Enviar reporte anomalo de $900
    idempotency_key = str(uuid4())
    obs = instante.strftime("%Y-%m-%dT%H:%M:%SZ")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.post(
            "/v1/reportes",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
            json={
                "presentacion_id": str(pres_id),
                "establecimiento_id": str(est_id),
                "precio_cop": 900,
                "observado_en": obs,
            },
        )
        assert resp.status_code == 201
        datos = resp.json()["datos"]
        assert datos["estado_visible"] == "en_revision"
        rep_id = datos["id"]

    # Verificar en BD que se abrio un caso_moderacion
    async with sesion_transaccional() as sesion:
        res_caso = (
            await sesion.execute(
                text("""
                SELECT tipo::text, prioridad FROM caso_moderacion
                WHERE referencia_tabla = 'reporte_precio' AND referencia_id = :rid;
            """),
                {"rid": rep_id},
            )
        ).first()
        assert res_caso is not None
        assert res_caso[0] == "reporte_dudoso"


@pytest.mark.asyncio
async def test_rafaga_de_cuentas_desde_misma_huella_abre_caso_prioritario() -> None:
    """Verifica que 3 cuentas en misma huella activen rafaga y reclasifiquen hacia atras."""
    instante = datetime.now(UTC)

    async with sesion_transaccional() as sesion:
        res_pres = (
            await sesion.execute(text("SELECT id, producto_id FROM presentacion LIMIT 1;"))
        ).first()
        res_est = (await sesion.execute(text("SELECT id FROM establecimiento LIMIT 1;"))).first()
        assert res_pres is not None
        assert res_est is not None
        pres_id, est_id = str(res_pres[0]), str(res_est[0])

    # Crear 3 usuarios distintos
    u1, u2, u3 = str(uuid4()), str(uuid4()), str(uuid4())
    t1 = await crear_usuario_con_autorizacion(u1)
    t2 = await crear_usuario_con_autorizacion(u2)
    t3 = await crear_usuario_con_autorizacion(u3)

    obs = instante.strftime("%Y-%m-%dT%H:%M:%SZ")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Reporte usuario 1
        resp1 = await cliente.post(
            "/v1/reportes",
            headers={"Authorization": f"Bearer {t1}", "Idempotency-Key": str(uuid4())},
            json={
                "presentacion_id": pres_id,
                "establecimiento_id": est_id,
                "precio_cop": 3000,
                "observado_en": obs,
            },
        )
        assert resp1.status_code == 201
        rep1_id = resp1.json()["datos"]["id"]

        # Reporte usuario 2
        resp2 = await cliente.post(
            "/v1/reportes",
            headers={"Authorization": f"Bearer {t2}", "Idempotency-Key": str(uuid4())},
            json={
                "presentacion_id": pres_id,
                "establecimiento_id": est_id,
                "precio_cop": 3050,
                "observado_en": obs,
            },
        )
        assert resp2.status_code == 201
        rep2_id = resp2.json()["datos"]["id"]

        # Reporte usuario 3 (activa umbral de 3 cuentas en 30 min)
        resp3 = await cliente.post(
            "/v1/reportes",
            headers={"Authorization": f"Bearer {t3}", "Idempotency-Key": str(uuid4())},
            json={
                "presentacion_id": pres_id,
                "establecimiento_id": est_id,
                "precio_cop": 3100,
                "observado_en": obs,
            },
        )
        assert resp3.status_code == 201
        rep3_id = resp3.json()["datos"]["id"]

    # Verificar que se abrio un caso de moderacion de tipo 'rafaga' con prioridad 1
    async with sesion_transaccional() as sesion:
        res_caso = (
            await sesion.execute(
                text("""
                SELECT tipo::text, prioridad FROM caso_moderacion
                WHERE tipo = 'rafaga' AND referencia_id = :rid;
            """),
                {"rid": rep3_id},
            )
        ).first()
        assert res_caso is not None
        assert res_caso[0] == "rafaga"
        assert res_caso[1] == 1

        # Verificar que los reportes previos fueron reclasificados hacia atras a 'dudoso'
        for rid in (rep1_id, rep2_id, rep3_id):
            estado_rep = (
                await sesion.execute(
                    text("SELECT estado::text FROM reporte_precio WHERE id = :id;"),
                    {"id": rid},
                )
            ).scalar()
            assert estado_rep == "dudoso"
