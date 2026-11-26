"""Pruebas estaticas y de integracion de la semilla de historial demo (T-118).

Las pruebas estaticas siempre se ejecutan: inspeccionan el SQL del escritor sin
tocar la base de datos. La prueba de idempotencia real se omite cuando no hay
``DATABASE_URL`` ni ``MIGRATIONS_DATABASE_URL`` configuradas.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.config import obtener_configuracion
from scripts.semilla_historial import (
    PERFIL_VECINO_CENTENARIO,
    SQL_INSERTAR_REPORTE,
    SQL_PRECIO_VIGENTE,
    SQL_SELECCIONAR_ESTABLECIMIENTOS,
    SQL_SELECCIONAR_PRESENTACIONES,
    ejecutar_semilla_historial,
)

RUTA_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "semilla_historial.py"


def _sql_normalizado(sql: str) -> str:
    """Elimina comentarios de linea y normaliza espacios y mayusculas."""
    sin_comentarios = re.sub(r"--[^\n]*", "", sql)
    return " ".join(sin_comentarios.lower().split())


def _texto_script_normalizado() -> str:
    """Lee el script completo y normaliza espacios y mayusculas."""
    return _sql_normalizado(RUTA_SCRIPT.read_text(encoding="utf-8"))


def _hay_url_bd() -> bool:
    """Indica si existe una cadena de conexion configurada para PostgreSQL."""
    configuracion = obtener_configuracion()
    return bool(configuracion.DATABASE_URL or configuracion.MIGRATIONS_DATABASE_URL)


def test_sql_insertar_reporte_es_idempotente() -> None:
    """El insert usa ON CONFLICT (id) DO NOTHING sobre reporte_precio."""
    sql = _sql_normalizado(SQL_INSERTAR_REPORTE)

    assert "insert into public.reporte_precio" in sql
    assert "on conflict (id) do nothing" in sql
    assert "es_demo" in sql
    assert "update " not in sql
    assert "delete from" not in sql


def test_sql_del_escritor_no_modifica_reportes_ni_precio_vigente() -> None:
    """El script solo lee precio_vigente y solo inserta reportes, sin update/delete."""
    texto = _texto_script_normalizado()

    sentencias_prohibidas = (
        "update public.reporte_precio",
        "delete from public.reporte_precio",
        "update public.precio_vigente",
        "delete from public.precio_vigente",
        "insert into public.precio_vigente",
    )
    for sentencia in sentencias_prohibidas:
        assert sentencia not in texto, f"El escritor no debe contener: {sentencia!r}"

    assert "insert into public.reporte_precio" in texto
    assert "select precio_cop" in _sql_normalizado(SQL_PRECIO_VIGENTE)
    assert "on conflict (id) do nothing" in texto


def test_sql_de_seleccion_no_modifica_datos() -> None:
    """Las consultas de catalogo son de solo lectura."""
    for sql in (SQL_SELECCIONAR_PRESENTACIONES, SQL_SELECCIONAR_ESTABLECIMIENTOS):
        normalizado = _sql_normalizado(sql)
        assert normalizado.startswith("select ")
        assert "update " not in normalizado
        assert "delete from" not in normalizado
        assert "insert into" not in normalizado


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _hay_url_bd(),
    reason=(
        "Sin base de datos: configura DATABASE_URL o MIGRATIONS_DATABASE_URL "
        "en .env para ejecutar la prueba de idempotencia real."
    ),
)
async def test_semilla_historial_idempotente_en_bd() -> None:
    """Ejecutar el escritor dos veces no duplica puntos demo ni altera precio_vigente."""
    async with sesion_transaccional() as sesion:
        perfil_semilla = await sesion.scalar(
            text("SELECT 1 FROM public.perfil WHERE id = :id;"),
            {"id": PERFIL_VECINO_CENTENARIO},
        )
        if perfil_semilla is None:
            pytest.skip(
                "No existe el perfil semilla 'vecino_centenario'; ejecuta "
                "scripts/semilla.py antes de esta prueba."
            )

        vigente_antes = (
            await sesion.execute(
                text(
                    "SELECT count(*) AS filas, coalesce(sum(precio_cop), 0) AS total "
                    "FROM public.precio_vigente;"
                )
            )
        ).one()

    primero = await ejecutar_semilla_historial()
    if primero["puntos_generados"] == 0:
        pytest.skip(
            "No hay combinaciones con precio base; ejecuta scripts/semilla.py antes de esta prueba."
        )

    segundo = await ejecutar_semilla_historial()

    assert segundo["puntos_generados"] == primero["puntos_generados"]
    assert segundo["puntos_insertados"] == 0, "La segunda ejecucion no debe insertar filas."

    async with sesion_transaccional() as sesion:
        vigente_despues = (
            await sesion.execute(
                text(
                    "SELECT count(*) AS filas, coalesce(sum(precio_cop), 0) AS total "
                    "FROM public.precio_vigente;"
                )
            )
        ).one()
        demo_en_bd = await sesion.scalar(
            text("SELECT count(*) FROM public.reporte_precio WHERE es_demo = true;")
        )

    assert tuple(vigente_despues) == tuple(vigente_antes), (
        "La semilla de historial no debe modificar precio_vigente."
    )
    assert demo_en_bd is not None
    assert demo_en_bd >= primero["puntos_generados"]
