"""Pruebas de integracion para comparador publico y neutralidad comercial EC-06 (T-26)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.main import app


@pytest.mark.asyncio
async def test_comparador_contrato_json_y_neutralidad_ec06() -> None:
    async with sesion_transaccional() as sesion:
        res = (
            await sesion.execute(text("SELECT id FROM producto WHERE activo = true LIMIT 1;"))
        ).first()
        assert res is not None
        producto_id = str(res[0])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.get(f"/v1/productos/{producto_id}/comparacion")
        assert resp.status_code == 200
        cuerpo = resp.json()
        assert "datos" in cuerpo
        datos = cuerpo["datos"]

        # 1. Encabezado de producto
        assert "producto" in datos
        assert datos["producto"]["id"] == producto_id
        assert "presentaciones" in datos["producto"]

        # 2. Resultados ordenados y neutralidad comercial
        assert "resultados" in datos
        assert "promociones" in datos
        assert isinstance(datos["promociones"], list)
        assert len(datos["promociones"]) == 0  # EC-06: Bloque separado e independiente

        # 3. Metadatos
        meta = datos["meta"]
        assert meta["criterio_orden"] == "precio_unitario"
        assert (
            "neutralidad" in meta["texto_neutralidad"].lower()
            or "promociones" in meta["texto_neutralidad"].lower()
        )
        assert "vigentes" in meta["bloques"]


@pytest.mark.asyncio
async def test_comparador_validaciones_de_ordenamiento() -> None:
    producto_id = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Orden por precio sin presentacion_id -> 422
        resp_p = await cliente.get(f"/v1/productos/{producto_id}/comparacion?orden=precio")
        assert resp_p.status_code == 422

        # Orden por distancia sin lat/lng -> 422
        resp_d = await cliente.get(f"/v1/productos/{producto_id}/comparacion?orden=distancia")
        assert resp_d.status_code == 422


@pytest.mark.asyncio
async def test_comparador_con_coordenadas_calcula_distancia_ram() -> None:
    async with sesion_transaccional() as sesion:
        res = (
            await sesion.execute(text("SELECT id FROM producto WHERE activo = true LIMIT 1;"))
        ).first()
        assert res is not None
        producto_id = str(res[0])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Consulta con coordenadas de Armenia (Plaza de Bolivar: 4.5339, -75.6811)
        resp = await cliente.get(
            f"/v1/productos/{producto_id}/comparacion?lat=4.5339&lng=-75.6811&orden=distancia"
        )
        assert resp.status_code == 200
        datos = resp.json()["datos"]
        assert datos["meta"]["criterio_orden"] == "distancia"
        for item in datos["resultados"]:
            assert item["establecimiento"]["distancia_m"] is not None
            assert item["establecimiento"]["distancia_m"] >= 0
