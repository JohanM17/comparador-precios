"""Pruebas unitarias estáticas para la migración 0005 (índice del historial de precios)."""

from __future__ import annotations

import re
from pathlib import Path

RUTA_SQL = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "0005_historial_precios.sql"
)


def _sql_normalizado() -> str:
    """Lee el SQL, elimina comentarios de línea y normaliza espacios y mayúsculas."""
    texto = RUTA_SQL.read_text(encoding="utf-8")
    sin_comentarios = re.sub(r"--[^\n]*", "", texto)
    return " ".join(sin_comentarios.lower().split())


def test_archivo_de_migracion_existe() -> None:
    """La migración 0005 debe existir en supabase/migrations."""
    assert RUTA_SQL.is_file(), f"No existe la migración esperada: {RUTA_SQL}"


def test_crea_indice_de_forma_idempotente() -> None:
    """El índice se crea con IF NOT EXISTS para poder aplicar la migración dos veces."""
    sql = _sql_normalizado()
    assert "create index if not exists idx_reporte_historial_serie" in sql
    assert "drop index" not in sql


def test_indice_apunta_a_reporte_precio_en_public() -> None:
    """El índice debe construirse sobre public.reporte_precio."""
    sql = _sql_normalizado()
    assert re.search(r"on public\.reporte_precio\s*\(", sql), (
        "El índice debe declararse sobre public.reporte_precio"
    )


def test_columnas_del_indice_en_orden() -> None:
    """Las columnas deben ser producto_id, establecimiento_id y observado_en desc."""
    sql = _sql_normalizado()
    coincidencia = re.search(r"on public\.reporte_precio\s*\(([^)]*)\)", sql)
    assert coincidencia is not None, "No se pudo leer la lista de columnas del índice"
    columnas = " ".join(coincidencia.group(1).split())
    assert columnas == "producto_id, establecimiento_id, observado_en desc"


def test_predicado_parcial_solo_aceptado_y_dudoso() -> None:
    """El índice debe ser parcial y cubrir únicamente los estados aceptado y dudoso."""
    sql = _sql_normalizado()
    assert "where estado in ('aceptado', 'dudoso')" in sql


def test_no_altera_tablas_columnas_ni_datos() -> None:
    """La migración es aditiva: no crea, altera ni borra tablas ni manipula datos."""
    sql = _sql_normalizado()
    sentencias_prohibidas = (
        "create table",
        "alter table",
        "drop table",
        "insert into",
        "update ",
        "delete from",
        "truncate ",
    )
    for sentencia in sentencias_prohibidas:
        assert sentencia not in sql, f"La migración 0005 no debe contener: {sentencia!r}"
