"""Pruebas de integracion para la API publica de establecimientos (Tarea T-14)."""

from __future__ import annotations

import io
import logging
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.compartido.logging_cfg import FiltroPrivacidadLey1581
from app.main import app


@pytest.mark.asyncio
async def test_listar_establecimientos_armenia() -> None:
    """Verifica que el listado de Armenia devuelva las 30 tiendas de la semilla."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.get("/v1/establecimientos", params={"municipio": "Armenia"})
        assert resp.status_code == 200
        datos = resp.json()["datos"]
        assert len(datos) >= 30
        for est in datos:
            assert est["municipio"] == "Armenia"
            assert "lat" in est
            assert "lng" in est


@pytest.mark.asyncio
async def test_filtro_espacial_calcula_distancia_y_ordena() -> None:
    """Verifica que PostGIS calcule distancia_m y ordene por cercania."""
    # Plaza Bolivar de Armenia: lat=4.5339, lng=-75.6811
    lat_centro = 4.5339
    lng_centro = -75.6811

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.get(
            "/v1/establecimientos",
            params={
                "lat": lat_centro,
                "lng": lng_centro,
                "radio_km": 5.0,
            },
        )
        assert resp.status_code == 200
        tiendas = resp.json()["datos"]
        assert len(tiendas) >= 1

        distancias = [t["distancia_m"] for t in tiendas]
        assert all(d is not None for d in distancias)
        assert all(d <= 5000 for d in distancias)  # type: ignore[operator]
        assert distancias == sorted(distancias)


@pytest.mark.asyncio
async def test_privacidad_ley_1581_coordenadas_no_aparecen_en_logs() -> None:
    """Verifica que las coordenadas en query params se redacten en los logs."""
    captura_logs = io.StringIO()
    manejador = logging.StreamHandler(captura_logs)
    manejador.addFilter(FiltroPrivacidadLey1581())
    logger = logging.getLogger("app.acceso")
    logger.addHandler(manejador)

    lat_sensible = 4.54321
    lng_sensible = -75.65432

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
            resp = await cliente.get(
                "/v1/establecimientos",
                params={"lat": lat_sensible, "lng": lng_sensible, "radio_km": 2.0},
            )
            assert resp.status_code == 200
    finally:
        logger.removeHandler(manejador)

    contenido = captura_logs.getvalue()
    assert str(lat_sensible) not in contenido
    assert str(lng_sensible) not in contenido


@pytest.mark.asyncio
async def test_detalle_establecimiento_y_solicitud_correccion_con_honeypot() -> None:
    """Verifica la ficha de tienda y el flujo de solicitud con proteccion honeypot."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # 1. Obtener una tienda existente
        resp_lista = await cliente.get("/v1/establecimientos", params={"limite": 1})
        tienda = resp_lista.json()["datos"][0]
        tienda_id = tienda["id"]

        # 2. Consultar ficha
        resp_det = await cliente.get(f"/v1/establecimientos/{tienda_id}")
        assert resp_det.status_code == 200
        assert resp_det.json()["id"] == tienda_id

        # 3. Solicitud con honeypot (sitio_web_trampa con contenido -> no guarda en BD)
        resp_trampa = await cliente.post(
            f"/v1/establecimientos/{tienda_id}/solicitudes-correccion",
            json={
                "correo": "bot@spam.com",
                "mensaje": "Mensaje publicitario automatico no deseado",
                "sitio_web_trampa": "https://spam.net",
            },
        )
        assert resp_trampa.status_code == 201
        assert resp_trampa.json()["id"] is None

        # 4. Solicitud legitima -> Guarda en caso_moderacion
        resp_legitima = await cliente.post(
            f"/v1/establecimientos/{tienda_id}/solicitudes-correccion",
            json={
                "correo": "ciudadano@armenia.gov.co",
                "mensaje": "El establecimiento cambio de numero de local al local 104.",
                "sitio_web_trampa": None,
            },
        )
        assert resp_legitima.status_code == 201
        caso_id = resp_legitima.json()["id"]
        assert caso_id is not None

        # Verificar en PostgreSQL que el caso existe
        async with sesion_transaccional() as sesion:
            fila = (
                await sesion.execute(
                    text("SELECT tipo, estado FROM caso_moderacion WHERE id = :id;"),
                    {"id": caso_id},
                )
            ).fetchone()
            assert fila is not None
            assert fila[0] == "solicitud_correccion"
            assert fila[1] == "abierto"

        # 5. Intentar corregir tienda inexistente -> 404
        resp_404 = await cliente.post(
            f"/v1/establecimientos/{uuid4()}/solicitudes-correccion",
            json={
                "correo": "test@armenia.gov.co",
                "mensaje": "Direccion invalida reportada",
                "sitio_web_trampa": None,
            },
        )
        assert resp_404.status_code == 404
        assert resp_404.json()["codigo"] == "NO_ENCONTRADO"
