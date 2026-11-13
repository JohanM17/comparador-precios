"""Pruebas de integración para la carga idempotente de la semilla (Tarea T-12)."""

import pytest
from scripts.semilla import ejecutar_semilla
from sqlalchemy import text

from app.bd import sesion_transaccional


@pytest.mark.asyncio
async def test_semilla_es_completamente_idempotente() -> None:
    """Verifica que ejecutar la semilla dos veces consecutivas no duplica registros."""
    # Primera ejecución
    res1 = await ejecutar_semilla()
    assert res1["categorias"] == 10
    assert res1["productos"] >= 100
    assert res1["presentaciones"] >= 80
    assert res1["establecimientos"] == 30

    async with sesion_transaccional() as sesion:
        n_cat_1 = await sesion.scalar(text("SELECT count(*) FROM categoria;"))
        n_prod_1 = await sesion.scalar(text("SELECT count(*) FROM producto;"))
        n_pres_1 = await sesion.scalar(text("SELECT count(*) FROM presentacion;"))
        n_est_1 = await sesion.scalar(text("SELECT count(*) FROM establecimiento;"))

    # Segunda ejecución (prueba de idempotencia estricta)
    res2 = await ejecutar_semilla()
    assert res2 == res1

    async with sesion_transaccional() as sesion:
        n_cat_2 = await sesion.scalar(text("SELECT count(*) FROM categoria;"))
        n_prod_2 = await sesion.scalar(text("SELECT count(*) FROM producto;"))
        n_pres_2 = await sesion.scalar(text("SELECT count(*) FROM presentacion;"))
        n_est_2 = await sesion.scalar(text("SELECT count(*) FROM establecimiento;"))

    # Los conteos no deben variar
    assert n_cat_1 == n_cat_2
    assert n_prod_1 == n_prod_2
    assert n_pres_1 == n_pres_2
    assert n_est_1 == n_est_2


@pytest.mark.asyncio
async def test_establecimientos_georreferenciados_armenia() -> None:
    """Verifica que los establecimientos tengan coordenadas válidas en Armenia."""
    async with sesion_transaccional() as sesion:
        resultado = await sesion.execute(
            text("""
                SELECT nombre, municipio,
                       ST_Y(ubicacion::geometry) as lat,
                       ST_X(ubicacion::geometry) as lng
                FROM establecimiento
                WHERE activo = true;
            """)
        )
        tiendas = resultado.fetchall()
        assert len(tiendas) >= 30

        for tienda in tiendas:
            nombre, muni, lat, lng = tienda
            assert muni == "Armenia"
            # Rango geográfico del municipio de Armenia, Quindío
            assert 4.45 <= lat <= 4.60, f"Latitud fuera de rango para {nombre}: {lat}"
            assert -75.75 <= lng <= -75.60, f"Longitud fuera de rango para {nombre}: {lng}"
