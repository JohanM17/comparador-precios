"""Modulo puro de la serie historica de precios (Historia A2).

Reglas innegociables:
- Cero I/O: sin base de datos, red, reloj del sistema ni variables de entorno.
- Aritmetica exacta con Decimal; los precios en COP se conservan como enteros.
- Solo se exponen datos publicos: nunca identidad, red, foto ni coordenadas.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from app.dominio.unidades import calcular_precio_visualizacion

# Contratos del dominio: no son umbrales calibrables de negocio.
ORIGENES_VALIDOS: Final[frozenset[str]] = frozenset({"usuario", "comercio", "semilla"})
ESTADOS_VALIDOS: Final[frozenset[str]] = frozenset({"aceptado", "dudoso", "rechazado"})
ESTADOS_VISIBLES: Final[frozenset[str]] = frozenset({"aceptado", "dudoso"})
UNIDADES_BASE_VALIDAS: Final[frozenset[str]] = frozenset({"g", "ml", "unidad"})


@dataclass(frozen=True)
class ReporteSerie:
    """Reporte historico de precio recibido desde la capa de persistencia."""

    id: UUID
    observado_en: datetime
    precio_cop: int
    cantidad_base: Decimal
    precio_por_base: Decimal
    origen: str
    estado: str
    es_demo: bool
    presentacion_id: UUID | None


@dataclass(frozen=True)
class PuntoSeriePrecio:
    """Punto publico de la serie, listo para graficar sin exponer datos privados."""

    id: UUID
    observado_en: datetime
    precio_cop: int
    precio_por_base: Decimal
    precio_por_unidad: int
    unidad_visualizacion: str
    origen: str
    estado: str
    es_demo: bool
    presentacion_id: UUID | None
    cantidad_base: Decimal


@dataclass(frozen=True)
class ResultadoSerie:
    """Resultado inmutable con los puntos visibles y sus banderas de contexto."""

    puntos: tuple[PuntoSeriePrecio, ...]
    truncado: bool
    datos_de_demostracion: bool


def construir_serie(
    reportes: Sequence[ReporteSerie],
    *,
    desde: datetime,
    hasta: datetime,
    unidad_base: str,
    limite: int,
) -> ResultadoSerie:
    """Construye la serie historica filtrada por ventana y estado, ordenada y limitada.

    La ventana incluye ambos extremos y solo se exponen los estados aceptado y dudoso.
    Si hay mas puntos visibles que ``limite`` se conservan los mas recientes, se
    mantiene el orden ascendente y se marca ``truncado``.
    """
    _validar_parametros(desde=desde, hasta=hasta, unidad_base=unidad_base, limite=limite)
    unidad = unidad_base.lower()

    visibles = _recolectar_visibles(reportes, desde=desde, hasta=hasta)
    truncado = len(visibles) > limite
    puntos = tuple(
        _construir_punto(reporte, observado_en, unidad)
        for observado_en, reporte in visibles[-limite:]
    )

    return ResultadoSerie(
        puntos=puntos,
        truncado=truncado,
        datos_de_demostracion=any(punto.es_demo for punto in puntos),
    )


def _recolectar_visibles(
    reportes: Sequence[ReporteSerie],
    *,
    desde: datetime,
    hasta: datetime,
) -> list[tuple[datetime, ReporteSerie]]:
    """Filtra por ventana inclusiva y estado visible, y ordena de forma estable."""
    visibles: list[tuple[datetime, ReporteSerie]] = []
    for reporte in reportes:
        _validar_reporte(reporte)
        observado_en = _normalizar_observado(reporte.observado_en)
        if desde <= observado_en <= hasta and reporte.estado in ESTADOS_VISIBLES:
            visibles.append((observado_en, reporte))
    visibles.sort(key=lambda item: (item[0], str(item[1].id)))
    return visibles


def _validar_parametros(
    *,
    desde: datetime,
    hasta: datetime,
    unidad_base: str,
    limite: int,
) -> None:
    """Valida los parametros de la ventana, el limite y la unidad base."""
    if desde > hasta:
        raise ValueError("La fecha 'desde' no puede ser posterior a 'hasta'.")
    if limite < 1:
        raise ValueError("El limite debe ser mayor o igual a 1.")
    if unidad_base.lower() not in UNIDADES_BASE_VALIDAS:
        raise ValueError(f"La unidad base '{unidad_base}' no esta soportada.")


def _validar_reporte(reporte: ReporteSerie) -> None:
    """Valida que el origen y el estado pertenezcan al contrato del dominio."""
    if reporte.origen not in ORIGENES_VALIDOS:
        raise ValueError(f"El origen '{reporte.origen}' no es valido.")
    if reporte.estado not in ESTADOS_VALIDOS:
        raise ValueError(f"El estado '{reporte.estado}' no es valido.")


def _normalizar_observado(observado_en: datetime) -> datetime:
    """Exige una fecha con zona horaria y la normaliza a UTC."""
    if observado_en.tzinfo is None or observado_en.utcoffset() is None:
        raise ValueError("La fecha de observacion debe incluir zona horaria.")
    return observado_en.astimezone(UTC)


def _construir_punto(
    reporte: ReporteSerie,
    observado_en: datetime,
    unidad_base: str,
) -> PuntoSeriePrecio:
    """Convierte un reporte visible en un punto publico de la serie."""
    precio_por_unidad, unidad_visualizacion = calcular_precio_visualizacion(
        reporte.precio_por_base, unidad_base
    )
    return PuntoSeriePrecio(
        id=reporte.id,
        observado_en=observado_en,
        precio_cop=reporte.precio_cop,
        precio_por_base=reporte.precio_por_base,
        precio_por_unidad=precio_por_unidad,
        unidad_visualizacion=unidad_visualizacion,
        origen=reporte.origen,
        estado=reporte.estado,
        es_demo=reporte.es_demo,
        presentacion_id=reporte.presentacion_id,
        cantidad_base=reporte.cantidad_base,
    )
