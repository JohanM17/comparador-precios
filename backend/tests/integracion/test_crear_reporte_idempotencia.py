"""Pruebas de integracion para creacion de reportes e idempotencia F2 (T-23)."""

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


async def preparar_usuario(usuario_id: str) -> str:
    token = generar_token(usuario_id)
    alias = f"rep_{usuario_id[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        await cliente.post(
            "/v1/mi-cuenta/autorizacion",
            headers={"Authorization": f"Bearer {token}"},
            json={"alias": alias, "version_politica": "1.0", "acepta": True},
        )
    return token


@pytest.mark.asyncio
async def test_crear_reporte_flujo_exitoso_e_idempotencia() -> None:
    uid = str(uuid4())
    token = await preparar_usuario(uid)

    async with sesion_transaccional() as sesion:
        res_pres = (await sesion.execute(text("SELECT id FROM presentacion LIMIT 1;"))).first()
        res_est = (await sesion.execute(text("SELECT id FROM establecimiento LIMIT 1;"))).first()
        assert res_pres is not None
        assert res_est is not None
        pres_id, est_id = str(res_pres[0]), str(res_est[0])

    idempotency_key = str(uuid4())
    obs = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    cuerpo = {
        "presentacion_id": pres_id,
        "establecimiento_id": est_id,
        "precio_cop": 3200,
        "observado_en": obs,
        "foto_ruta": None,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # 1. Primera llamada -> 201 Created
        resp1 = await cliente.post(
            "/v1/reportes",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
            json=cuerpo,
        )
        assert resp1.status_code == 201
        datos1 = resp1.json()["datos"]
        reporte_id = datos1["id"]
        assert datos1["estado_visible"] in ("recibido", "en_revision")

        # 2. Reintento con la misma Idempotency-Key -> 200 OK (sin duplicar)
        resp2 = await cliente.post(
            "/v1/reportes",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
            json=cuerpo,
        )
        assert resp2.status_code == 200
        datos2 = resp2.json()["datos"]
        assert datos2["id"] == reporte_id
        assert datos2["estado_visible"] == datos1["estado_visible"]

        # 3. Comprobar en BD que no se duplico la fila
        async with sesion_transaccional() as sesion:
            sql_conteo = text("SELECT count(*) FROM reporte_precio WHERE idempotency_key = :k;")
            conteo = (await sesion.execute(sql_conteo, {"k": idempotency_key})).scalar()
            assert conteo == 1


@pytest.mark.asyncio
async def test_crear_reporte_rechazo_precio_fuera_de_rango() -> None:
    uid = str(uuid4())
    token = await preparar_usuario(uid)

    async with sesion_transaccional() as sesion:
        res_pres = (await sesion.execute(text("SELECT id FROM presentacion LIMIT 1;"))).first()
        res_est = (await sesion.execute(text("SELECT id FROM establecimiento LIMIT 1;"))).first()
        assert res_pres is not None
        assert res_est is not None
        pres_id, est_id = str(res_pres[0]), str(res_est[0])

    obs = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Precio por debajo de 50 COP
        resp_bajo = await cliente.post(
            "/v1/reportes",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())},
            json={
                "presentacion_id": pres_id,
                "establecimiento_id": est_id,
                "precio_cop": 10,
                "observado_en": obs,
            },
        )
        assert resp_bajo.status_code == 422
        assert resp_bajo.json()["codigo"] == "PRECIO_FUERA_DE_RANGO"

        # Precio por encima de 2.000.000 COP
        resp_alto = await cliente.post(
            "/v1/reportes",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())},
            json={
                "presentacion_id": pres_id,
                "establecimiento_id": est_id,
                "precio_cop": 5000000,
                "observado_en": obs,
            },
        )
        assert resp_alto.status_code == 422
        assert resp_alto.json()["codigo"] == "PRECIO_FUERA_DE_RANGO"


@pytest.mark.asyncio
async def test_mis_reportes_paginacion() -> None:
    uid = str(uuid4())
    token = await preparar_usuario(uid)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.get(
            "/v1/mis-reportes?pagina=1&limite=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert "datos" in datos
        assert "total" in datos
        assert datos["pagina"] == 1
        assert datos["limite"] == 10
