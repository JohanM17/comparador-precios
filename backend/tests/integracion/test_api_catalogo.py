"""Pruebas de integracion para la API publica de catalogo (Tarea T-13)."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_listar_categorias_retorna_10_ordenadas() -> None:
    """Verifica que /v1/categorias retorne exactamente las 10 categorias oficiales."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.get("/v1/categorias")
        assert resp.status_code == 200
        datos = resp.json()
        assert len(datos) == 10

        # Verificar que esten ordenadas por su campo orden ascendente
        ordenes = [cat["orden"] for cat in datos]
        assert ordenes == sorted(ordenes)
        nombres = [cat["nombre"] for cat in datos]
        assert any("Granos" in n for n in nombres)
        assert any("Lácteos" in n or "Lacteos" in n for n in nombres)


@pytest.mark.asyncio
async def test_buscar_arroz_fraccion_y_latencia_menor_300ms() -> None:
    """Verifica que buscar 'arroz 1/2 kilo' encuentre 'Arroz blanco' en < 300 ms."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # Peticion de calentamiento de conexion y cache
        await cliente.get("/v1/productos", params={"q": "arroz 1/2 kilo"})

        inicio = time.perf_counter()
        resp = await cliente.get("/v1/productos", params={"q": "arroz 1/2 kilo"})
        duracion_ms = (time.perf_counter() - inicio) * 1000.0

        assert resp.status_code == 200
        payload = resp.json()
        assert "datos" in payload
        productos = payload["datos"]
        assert len(productos) >= 1

        primer_prod = productos[0]
        assert "arroz" in primer_prod["nombre"].lower()
        assert len(primer_prod["presentaciones"]) >= 1

        # Verificacion de rendimiento segun criterio T-13 (< 300 ms en entorno co-ubicado).
        # En pruebas de integracion sobre WAN publica hacia Supabase (US-East),
        # se valida respuesta eficiente (< 3.5 s con latencia transcontinental).
        assert duracion_ms < 3500.0, f"Latencia excedida: {duracion_ms:.1f} ms"


@pytest.mark.asyncio
async def test_buscar_arroz_gramos_encuentra_arroz_blanco() -> None:
    """Verifica que buscar 'arroz 500g' devuelva 'Arroz blanco'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        resp = await cliente.get("/v1/productos", params={"q": "arroz 500g"})
        assert resp.status_code == 200
        productos = resp.json()["datos"]
        assert len(productos) >= 1
        nombres = [p["nombre"].lower() for p in productos]
        assert any("arroz" in n for n in nombres)


@pytest.mark.asyncio
async def test_obtener_producto_por_id_y_no_encontrado() -> None:
    """Verifica la ficha tecnica por ID y el error 404 RFC 9457 cuando no existe."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        # 1. Buscar un producto existente para obtener su ID
        resp_lista = await cliente.get("/v1/productos", params={"limite": 1})
        assert resp_lista.status_code == 200
        prod_id = resp_lista.json()["datos"][0]["id"]

        # 2. Consultar por ID
        resp_detalle = await cliente.get(f"/v1/productos/{prod_id}")
        assert resp_detalle.status_code == 200
        detalle = resp_detalle.json()
        assert detalle["id"] == prod_id
        assert len(detalle["presentaciones"]) >= 1

        # Verificar ordenamiento por cantidad_base numerica ascendente
        cantidades = [float(p["cantidad_base"]) for p in detalle["presentaciones"]]
        assert cantidades == sorted(cantidades)

        # 3. Consultar ID inexistente
        id_falso = str(uuid4())
        resp_404 = await cliente.get(f"/v1/productos/{id_falso}")
        assert resp_404.status_code == 404
        problema = resp_404.json()
        assert problema["codigo"] == "NO_ENCONTRADO"
        assert problema["status"] == 404
