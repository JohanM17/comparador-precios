"""Modulo de dominio puro para la deteccion jerarquica y robusta de anomalias en precios."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from decimal import Decimal

from app.dominio.parametros import ParametrosDominio


@dataclass(frozen=True)
class CandidatoAnomalia:
    """Valores a evaluar para el nuevo reporte de precio."""

    precio_cop: int
    precio_por_base: Decimal


@dataclass(frozen=True)
class NivelReferencia:
    """Precios historicos organizados en los 3 niveles jerarquicos de comparacion."""

    presentacion_tienda: list[int] = field(default_factory=list)
    presentacion: list[int] = field(default_factory=list)
    producto_unitario: list[Decimal] = field(default_factory=list)


@dataclass(frozen=True)
class EvaluacionAnomalia:
    """Resultado del analisis estadistico de anomalia."""

    es_anomalo: bool
    puntaje_anomalia: float | None
    conjunto_referencia: str
    senales: list[str] = field(default_factory=list)


def _seleccionar_nivel(
    niveles: NivelReferencia,
    candidato: CandidatoAnomalia,
    min_ref: int,
) -> tuple[str, list[float], float] | None:
    """Selecciona el primer nivel jerarquico con al menos min_ref observaciones."""
    if len(niveles.presentacion_tienda) >= min_ref:
        return (
            "presentacion_tienda",
            [float(p) for p in niveles.presentacion_tienda],
            float(candidato.precio_cop),
        )
    if len(niveles.presentacion) >= min_ref:
        return (
            "presentacion",
            [float(p) for p in niveles.presentacion],
            float(candidato.precio_cop),
        )
    if len(niveles.producto_unitario) >= min_ref:
        return (
            "producto_unitario",
            [float(p) for p in niveles.producto_unitario],
            float(candidato.precio_por_base),
        )
    return None


def _calcular_anomalia_estadistica(
    x: float,
    valores: list[float],
    params: ParametrosDominio,
) -> tuple[bool, float, list[str]]:
    """Calcula Z-score modificado o desviacion porcentual de respaldo."""
    m = statistics.median(valores)
    diferencias = [abs(v - m) for v in valores]
    mad = statistics.median(diferencias)

    ratio_extremo = False
    if m > 0:
        ratio_max = m * params.precio_ratio_extremo
        ratio_min = m / params.precio_ratio_extremo
        ratio_extremo = (x > ratio_max) or (x < ratio_min)

    senales: list[str] = []
    if ratio_extremo:
        senales.append("ratio_extremo")

    n = len(valores)
    if n >= params.anomalia_n_min_z and mad > 0:
        m_score = 0.6745 * (x - m) / mad
        es_anomalo = (abs(m_score) > params.anomalia_z_umbral) or ratio_extremo
        puntaje = round(abs(m_score), 3)
        if abs(m_score) > params.anomalia_z_umbral:
            senales.append("anomalia_z")
    else:
        desv = abs(x - m) / m if m > 0 else 0.0
        es_anomalo = (desv > params.anomalia_desviacion_pct_umbral) or ratio_extremo
        puntaje = round(desv, 3)
        if desv > params.anomalia_desviacion_pct_umbral:
            senales.append("anomalia_desviacion")

    return es_anomalo, puntaje, senales


def evaluar_anomalia(
    candidato: CandidatoAnomalia,
    niveles: NivelReferencia,
    params: ParametrosDominio,
) -> EvaluacionAnomalia:
    """Evalua deterministicamente si un precio es anomalo siguiendo la jerarquia de 3 niveles."""
    seleccion = _seleccionar_nivel(niveles, candidato, params.anomalia_n_min_referencia)
    if seleccion is None:
        return EvaluacionAnomalia(
            es_anomalo=False,
            puntaje_anomalia=None,
            conjunto_referencia="sin_referencia",
            senales=[],
        )

    nivel_nombre, valores, x = seleccion
    es_anomalo, puntaje, senales = _calcular_anomalia_estadistica(x, valores, params)

    return EvaluacionAnomalia(
        es_anomalo=es_anomalo,
        puntaje_anomalia=puntaje,
        conjunto_referencia=nivel_nombre,
        senales=senales,
    )
