"""Pruebas estaticas y de integracion de la semilla de historial demo (T-118).

Las pruebas estaticas siempre se ejecutan: inspeccionan el SQL del escritor sin
tocar la base de datos.

La prueba de idempotencia real escribe filas demo append-only, por lo que es
**opt-in**: ademas de una URL de BD exige ``SEMILLA_HISTORIAL_PERMITIR_BD=1``.
No debe ejecutarse contra produccion ni contra una CI compartida.

La prueba de regresion de ``precio_vigente`` inserta reportes dentro de una
transaccion que siempre se revierte; no deja datos persistidos.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.bd import obtener_creador_sesiones, sesion_transaccional
from app.compartido.parametros import obtener_parametros_dominio
from app.config import obtener_configuracion
from app.dominio.unidades import calcular_precio_por_base
from app.puertos.politica_precio import SoloUsuarios, reconstruir_precio_vigente
from scripts.semilla_historial import (
    PERFIL_VECINO_CENTENARIO,
    SQL_INSERTAR_REPORTE,
    SQL_PRECIO_VIGENTE,
    SQL_SELECCIONAR_ESTABLECIMIENTOS,
    SQL_SELECCIONAR_PRESENTACIONES,
    SQL_ULTIMO_REPORTE,
    SQL_ULTIMO_REPORTE_PRESENTACION,
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


def _permite_escritura_bd() -> bool:
    """Indica si el entorno autoriza explicitamente escribir datos demo en la BD."""
    return os.environ.get("SEMILLA_HISTORIAL_PERMITIR_BD") == "1"


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


def test_sql_de_precio_base_excluye_puntos_demo() -> None:
    """El precio base de respaldo no se retroalimenta de los puntos demo ya sembrados."""
    for sql in (SQL_ULTIMO_REPORTE, SQL_ULTIMO_REPORTE_PRESENTACION):
        normalizado = _sql_normalizado(sql)
        assert normalizado.startswith("select ")
        assert "es_demo = false" in normalizado


@pytest.mark.asyncio
@pytest.mark.skipif(
    not (_hay_url_bd() and _permite_escritura_bd()),
    reason=(
        "Escritura en BD no autorizada: configura DATABASE_URL o MIGRATIONS_DATABASE_URL "
        "y define SEMILLA_HISTORIAL_PERMITIR_BD=1. No ejecutar contra produccion ni CI compartida."
    ),
)
async def test_semilla_historial_idempotente_en_bd() -> None:
    """Ejecutar el escritor dos veces no duplica puntos demo ni altera precio_vigente.

    ADVERTENCIA: este test deja filas demo append-only en la BD configurada.
    Solo debe ejecutarse contra una base de desarrollo desechable o aceptada
    explicitamente mediante ``SEMILLA_HISTORIAL_PERMITIR_BD=1``.
    """
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


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _hay_url_bd(),
    reason=(
        "Sin base de datos: configura DATABASE_URL o MIGRATIONS_DATABASE_URL "
        "en .env para ejecutar la prueba de regresion de precio_vigente."
    ),
)
async def test_reconstruccion_ignora_reportes_demo_y_conserva_reales() -> None:
    """Un reporte demo aislado no crea precio_vigente; uno real si lo sigue creando.

    La prueba inserta datos dentro de una transaccion que siempre se revierte,
    por lo que no deja filas persistidas en la base compartida.
    """
    ahora = datetime.now(UTC)
    creador = obtener_creador_sesiones()

    async with creador() as sesion:
        transaccion = await sesion.begin()
        try:
            await sesion.execute(text("SET LOCAL ROLE app_backend;"))
            parametros = await obtener_parametros_dominio(sesion)
            limite = ahora - timedelta(days=parametros.vigencia_antiguo_dias)

            pares = (
                await sesion.execute(
                    text("""
                        SELECT pr.id AS presentacion_id, pr.producto_id,
                               pr.cantidad_base, e.id AS establecimiento_id
                        FROM public.presentacion pr
                        JOIN public.producto p ON p.id = pr.producto_id
                        CROSS JOIN public.establecimiento e
                        WHERE pr.activa = true
                          AND p.activo = true
                          AND e.activo = true
                          AND NOT EXISTS (
                              SELECT 1
                              FROM public.reporte_precio rp
                              WHERE rp.presentacion_id = pr.id
                                AND rp.establecimiento_id = e.id
                                AND rp.observado_en >= :limite
                          )
                          AND NOT EXISTS (
                              SELECT 1
                              FROM public.precio_oficial po
                              WHERE po.presentacion_id = pr.id
                                AND po.establecimiento_id = e.id
                                AND po.activo = true
                          )
                        ORDER BY pr.id, e.id
                        LIMIT 2;
                    """),
                    {"limite": limite},
                )
            ).fetchall()
            if len(pares) < 2:
                pytest.skip(
                    "No hay dos pares producto-establecimiento activos sin reportes "
                    "recientes; no se puede aislar la prueba de regresion."
                )

            par_demo, par_real = pares[0], pares[1]
            observado_en = ahora - timedelta(days=5)
            insertar_reporte = text("""
                INSERT INTO public.reporte_precio (
                    id, presentacion_id, establecimiento_id, producto_id,
                    precio_cop, cantidad_base_snapshot, precio_por_base,
                    fuente, reportante_id, observado_en,
                    estado, estado_original, conjunto_referencia, es_demo
                ) VALUES (
                    :id, :pres_id, :est_id, :prod_id,
                    :precio_cop, :cant_base, :precio_por_base,
                    'semilla', NULL, :observado_en,
                    'aceptado', 'aceptado', 'presentacion_tienda', :es_demo
                );
            """)

            precio_demo = 9000
            precio_real = 11000
            for par, precio_cop, es_demo in (
                (par_demo, precio_demo, True),
                (par_real, precio_real, False),
            ):
                cantidad_base = Decimal(str(par.cantidad_base))
                await sesion.execute(
                    insertar_reporte,
                    {
                        "id": uuid4(),
                        "pres_id": par.presentacion_id,
                        "est_id": par.establecimiento_id,
                        "prod_id": par.producto_id,
                        "precio_cop": precio_cop,
                        "cant_base": cantidad_base,
                        "precio_por_base": calcular_precio_por_base(precio_cop, cantidad_base),
                        "observado_en": observado_en,
                        "es_demo": es_demo,
                    },
                )

            resultado_demo = await SoloUsuarios().recalcular_par(
                sesion,
                par_demo.presentacion_id,
                par_demo.establecimiento_id,
                ahora,
                parametros,
            )
            assert resultado_demo is None, (
                "El recalculo puntual del job no debe usar reportes demo."
            )

            recalculados = await reconstruir_precio_vigente(sesion, ahora=ahora)
            assert recalculados >= 1

            sql_vigente = text("""
                SELECT precio_cop
                FROM public.precio_vigente
                WHERE presentacion_id = :pres_id
                  AND establecimiento_id = :est_id;
            """)
            vigente_demo = (
                await sesion.execute(
                    sql_vigente,
                    {
                        "pres_id": par_demo.presentacion_id,
                        "est_id": par_demo.establecimiento_id,
                    },
                )
            ).first()
            assert vigente_demo is None, (
                "Un reporte demo no debe crear ni actualizar precio_vigente."
            )

            vigente_real = (
                await sesion.execute(
                    sql_vigente,
                    {
                        "pres_id": par_real.presentacion_id,
                        "est_id": par_real.establecimiento_id,
                    },
                )
            ).first()
            assert vigente_real is not None, (
                "Un reporte real debe seguir produciendo la fila de precio_vigente."
            )
            assert vigente_real.precio_cop == precio_real
        finally:
            await transaccion.rollback()
