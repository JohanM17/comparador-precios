"""Pruebas de integración del historial de precios (A2).

Requieren una base de datos PostgreSQL con las migraciones aplicadas. Si no hay
`DATABASE_URL` ni `MIGRATIONS_DATABASE_URL` configuradas, se omiten con un mensaje
claro en lugar de fallar.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.config import obtener_configuracion
from app.modulos.precios.repositorio import listar_reportes_serie
from app.modulos.precios.servicio_historial import ServicioHistorial


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


async def _buscar_par_con_datos(sesion: Any, desde: datetime, hasta: datetime) -> Any:
    """Busca un par producto-establecimiento activo con reportes visibles recientes."""
    par = (
        await sesion.execute(
            text("""
                SELECT rp.producto_id, rp.establecimiento_id, rp.presentacion_id
                FROM public.reporte_precio rp
                JOIN public.producto p ON p.id = rp.producto_id AND p.activo = true
                JOIN public.establecimiento e
                  ON e.id = rp.establecimiento_id AND e.activo = true
                JOIN public.presentacion pr
                  ON pr.id = rp.presentacion_id AND pr.activa = true
                WHERE rp.estado::text IN ('aceptado', 'dudoso')
                  AND rp.observado_en BETWEEN :desde AND :hasta
                ORDER BY rp.observado_en DESC, rp.id DESC
                LIMIT 1;
            """),
            {"desde": desde, "hasta": hasta},
        )
    ).first()
    if par is None:
        pytest.skip(
            "No hay reportes visibles de un producto, establecimiento y presentacion "
            "activos en los ultimos 90 dias; siembra datos antes de ejecutar esta prueba."
        )
    return par


def _claves_serializadas(valor: Any) -> set[str]:
    """Recolecta todas las claves de un DTO serializado, incluidas las anidadas."""
    if isinstance(valor, dict):
        claves = set(valor)
        for anidado in valor.values():
            claves |= _claves_serializadas(anidado)
        return claves
    if isinstance(valor, list):
        claves: set[str] = set()
        for elemento in valor:
            claves |= _claves_serializadas(elemento)
        return claves
    return set()


@pytest.mark.asyncio
async def test_servicio_historial_devuelve_dto_sin_pii() -> None:
    """El servicio arma la serie con la ventana pedida y sin campos personales."""
    hasta = datetime.now(UTC)
    desde = hasta - timedelta(days=90)

    async with sesion_transaccional() as sesion:
        par = await _buscar_par_con_datos(sesion, desde, hasta)
        respuesta = await ServicioHistorial(sesion, ahora=hasta).obtener_historial(
            producto_id=par.producto_id,
            establecimiento_id=par.establecimiento_id,
            desde=desde,
            hasta=hasta,
        )

    datos = respuesta.datos
    assert datos.producto.id == par.producto_id
    assert datos.establecimiento.id == par.establecimiento_id
    assert datos.presentacion is None
    assert datos.desde == desde
    assert datos.hasta == hasta
    assert datos.puntos, "La serie debe tener al menos un punto para un par con datos."
    assert datos.total == len(datos.puntos)
    assert isinstance(datos.truncado, bool)
    if datos.truncado:
        assert datos.total == 200, "Sin limite explicito, el truncado ocurre en 200 puntos."

    for punto in datos.puntos:
        assert isinstance(punto.precio_por_unidad.valor_cop, int)
        assert punto.precio_por_unidad.por in {"kg", "l", "unidad"}
        assert punto.precio_por_unidad.por == datos.producto.unidad_visualizacion
        assert punto.estado in {"aceptado", "dudoso"}
        assert punto.origen in {"usuario", "comercio", "semilla"}
        assert desde <= punto.observado_en <= hasta
        assert punto.cantidad_base > 0
        assert isinstance(punto.es_demo, bool)

    assert datos.datos_de_demostracion == any(punto.es_demo for punto in datos.puntos)

    claves = _claves_serializadas(respuesta.model_dump(mode="json"))
    assert not (CLAVES_PROHIBIDAS & claves), "El DTO no debe exponer datos personales."


@pytest.mark.asyncio
async def test_servicio_historial_filtra_por_presentacion_activa() -> None:
    """Al pedir una presentacion, el DTO la identifica y todos los puntos corresponden."""
    hasta = datetime.now(UTC)
    desde = hasta - timedelta(days=90)

    async with sesion_transaccional() as sesion:
        par = await _buscar_par_con_datos(sesion, desde, hasta)
        respuesta = await ServicioHistorial(sesion, ahora=hasta).obtener_historial(
            producto_id=par.producto_id,
            establecimiento_id=par.establecimiento_id,
            presentacion_id=par.presentacion_id,
        )

    datos = respuesta.datos
    assert datos.presentacion is not None
    assert datos.presentacion.id == par.presentacion_id
    assert datos.desde == hasta - timedelta(days=90)
    assert datos.puntos, "La presentacion elegida debe tener puntos visibles."
    assert all(punto.presentacion_id == par.presentacion_id for punto in datos.puntos)
    assert datos.total == len(datos.puntos)
