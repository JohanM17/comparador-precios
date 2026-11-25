"""Pruebas de integración del historial de precios (A2).

Requieren una base de datos PostgreSQL con las migraciones aplicadas. Si no hay
`DATABASE_URL` ni `MIGRATIONS_DATABASE_URL` configuradas, se omiten con un mensaje
claro en lugar de fallar.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.config import obtener_configuracion


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
