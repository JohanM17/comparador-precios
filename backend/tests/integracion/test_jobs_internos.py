"""Pruebas de integracion para endpoints de tareas programadas con X-Job-Token (T-34)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import obtener_configuracion
from app.main import app


@pytest.mark.asyncio
async def test_seguridad_job_token() -> None:
    cfg = obtener_configuracion()
    cfg.JOB_TOKEN = "token_secreto_prueba_jobs_123"  # noqa: S105

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Sin cabecera
        res1 = await cliente.post("/internal/jobs/ping_bd")
        assert res1.status_code == 401
        assert res1.json()["codigo"] == "NO_AUTENTICADO"

        # Con token invalido
        res2 = await cliente.post(
            "/internal/jobs/ping_bd",
            headers={"X-Job-Token": "token_falso_invalido"},
        )
        assert res2.status_code == 401
        assert res2.json()["codigo"] == "NO_AUTENTICADO"


@pytest.mark.asyncio
async def test_ejecucion_todos_los_jobs() -> None:
    cfg = obtener_configuracion()
    token = "token_secreto_prueba_jobs_123"  # noqa: S105
    cfg.JOB_TOKEN = token
    headers = {"X-Job-Token": token}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # 1. Ping BD
        res_ping = await cliente.post("/internal/jobs/ping_bd", headers=headers)
        assert res_ping.status_code == 200
        assert res_ping.json()["ok"] is True
        assert res_ping.json()["servicio"] == "bd"

        # 2. Recalcular reputacion
        res_rep = await cliente.post("/internal/jobs/recalcular_reputacion", headers=headers)
        assert res_rep.status_code == 200
        assert "procesados" in res_rep.json()
        assert res_rep.json()["procesados"] >= 0

        # 3. Reconstruir precio vigente
        res_rec = await cliente.post("/internal/jobs/reconstruir_precio_vigente", headers=headers)
        assert res_rec.status_code == 200
        assert "reconstruidos" in res_rec.json()
        assert res_rec.json()["reconstruidos"] >= 0

        # 4. Limpiar huellas
        res_lim = await cliente.post("/internal/jobs/limpiar_huellas", headers=headers)
        assert res_lim.status_code == 200
        assert "huellas_limpiadas" in res_lim.json()
        assert res_lim.json()["huellas_limpiadas"] >= 0
