"""Modulo de ordenamiento neutral en dos bloques para la comparacion de precios."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from app.compartido.texto import normalizar_texto

CriterioOrden = Literal["precio_unitario", "precio", "distancia"]

SELLOS_BLOQUE_1 = {"confiable", "pocos_datos", "oficial", "en_disputa"}
SELLOS_BLOQUE_2 = {"dudoso", "desactualizado"}


@dataclass(frozen=True)
class ItemComparacion:
    """Representa una fila de comparacion de un establecimiento para ordenar."""

    establecimiento_id: UUID
    establecimiento_nombre: str
    precio_cop: int
    precio_por_base: Decimal
    sello: str
    ultimo_reporte_en: datetime
    distancia_m: int | None = None
    es_bloque_secundario: bool = False


def ordenar_comparacion(
    items: list[ItemComparacion],
    criterio: CriterioOrden = "precio_unitario",
) -> list[ItemComparacion]:
    """Particiona en Bloque 1 y Bloque 2 y ordena internamente segun el criterio especificado."""
    bloque_1: list[ItemComparacion] = []
    bloque_2: list[ItemComparacion] = []

    for it in items:
        if it.sello in SELLOS_BLOQUE_1:
            bloque_1.append(replace(it, es_bloque_secundario=False))
        else:
            bloque_2.append(replace(it, es_bloque_secundario=True))

    def _clave_orden(item: ItemComparacion) -> tuple[Any, ...]:
        ts_desc = -item.ultimo_reporte_en.timestamp()
        nom_norm = normalizar_texto(item.establecimiento_nombre)
        eid_str = str(item.establecimiento_id)

        if criterio == "precio":
            return (item.precio_cop, ts_desc, nom_norm, eid_str)
        if criterio == "distancia":
            dist = item.distancia_m if item.distancia_m is not None else 999999999
            return (dist, item.precio_por_base, ts_desc, eid_str)
        # Por defecto precio_unitario
        return (item.precio_por_base, ts_desc, nom_norm, eid_str)

    b1_ordenado = sorted(bloque_1, key=_clave_orden)
    b2_ordenado = sorted(bloque_2, key=_clave_orden)

    return b1_ordenado + b2_ordenado
