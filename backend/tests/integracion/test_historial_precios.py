"""Pruebas de integración del historial de precios (A2).

Requieren una base de datos PostgreSQL con las migraciones aplicadas. Si no hay
`DATABASE_URL` ni `MIGRATIONS_DATABASE_URL` configuradas, se omiten con un mensaje
claro en lugar de fallar.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.config import obtener_configuracion
from app.modulos.precios.repositorio import listar_reportes_serie


def _hay_url_bd() -> bool:
    """Indica si existe una cadena de conexión configurada para PostgreSQL."""
    configuracion = obtener_configuracion()
    return bool(configuracion.DATABASE_URL or configuracion.MIGRATIONS_DATABASE_URL)


pytestmark = pytest.mark.skipif(
    not _hay_url_bd(),
    reason=(
        "Sin base de datos: configura DATABASE_URL o MIGRATIONS_DATABASE_URL "
        "en .env para ejecutar las pruebas de integración."
    ),
)


@pytest.mark.asyncio
async def test_indice_historial_serie_existe() -> None:
    """Verifica que la migración 0005 haya creado el índice idx_reporte_historial_serie."""
    async with sesion_transaccional() as sesion:
        resultado = await sesion.execute(
            text("""
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'reporte_precio'
                  AND indexname = 'idx_reporte_historial_serie';
            """)
        )
        fila = resultado.fetchone()

    assert fila is not None, (
        "No existe el índice idx_reporte_historial_serie; aplica la migración "
        "0005_historial_precios.sql."
    )

    definicion = fila[0]
    assert "producto_id" in definicion
    assert "establecimiento_id" in definicion
    assert "observado_en DESC" in definicion
    assert "WHERE" in definicion.upper()
    assert "'aceptado'" in definicion
    assert "'dudoso'" in definicion


CLAVES_ESPERADAS = {
    "id",
    "observado_en",
    "precio_cop",
    "cantidad_base_snapshot",
    "precio_por_base",
    "origen",
    "estado",
    "es_demo",
    "presentacion_id",
}

CLAVES_PROHIBIDAS = {"reportante_id", "huella_red", "foto_prueba_path", "lat", "lng"}


@pytest.mark.asyncio
async def test_listar_reportes_serie_sin_pii_y_ordenada_ascendentemente() -> None:
    """Consulta la serie de un par existente sin exponer datos personales."""
    hasta = datetime.now(UTC)
    desde = hasta - timedelta(days=90)

    async with sesion_transaccional() as sesion:
        par = (
            await sesion.execute(
                text("""
                    SELECT producto_id, establecimiento_id
                    FROM public.reporte_precio
                    WHERE estado::text IN ('aceptado', 'dudoso')
                      AND observado_en BETWEEN :desde AND :hasta
                    ORDER BY observado_en DESC, id DESC
                    LIMIT 1;
                """),
                {"desde": desde, "hasta": hasta},
            )
        ).first()

        if par is None:
            pytest.skip(
                "No hay reportes aceptados o dudosos en los ultimos 90 dias; "
                "siembra datos antes de ejecutar esta prueba."
            )

        filas = await listar_reportes_serie(
            sesion,
            producto_id=par.producto_id,
            establecimiento_id=par.establecimiento_id,
            desde=desde,
            hasta=hasta,
        )

        assert filas, "La consulta debe devolver al menos un reporte para un par con datos."

        for fila in filas:
            claves = set(fila)
            assert CLAVES_ESPERADAS <= claves, (
                f"Faltan claves esperadas: {CLAVES_ESPERADAS - claves}"
            )
            assert not (CLAVES_PROHIBIDAS & claves), "La serie no debe exponer datos personales."
            assert fila["estado"] in {"aceptado", "dudoso"}
            assert desde <= fila["observado_en"] <= hasta

        fechas = [fila["observado_en"] for fila in filas]
        assert fechas == sorted(fechas), "Los reportes deben venir en orden ascendente."

        # El filtro opcional por presentacion debe restringir la serie sin romperla.
        presentacion_id = filas[0]["presentacion_id"]
        if presentacion_id is not None:
            filas_presentacion = await listar_reportes_serie(
                sesion,
                producto_id=par.producto_id,
                establecimiento_id=par.establecimiento_id,
                desde=desde,
                hasta=hasta,
                presentacion_id=presentacion_id,
            )
            assert filas_presentacion
            assert all(fila["presentacion_id"] == presentacion_id for fila in filas_presentacion)
