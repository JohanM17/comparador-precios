"""Modulo de dominio para el calculo de vigencia temporal y pesos de reportes."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.dominio.parametros import ParametrosDominio


@dataclass(frozen=True)
class CandidatoReporte:
    """Entidad pura que representa un reporte candidato para evaluar precio vigente."""

    id: UUID
    precio_cop: int
    observado_en: datetime
    autor_id: str | None
    reputacion_autor: float
    tiene_foto: bool
    estado: str
    fuente: str
    cantidad_base: Decimal


def calcular_peso_reporte(
    reporte: CandidatoReporte,
    ahora: datetime,
    params: ParametrosDominio,
) -> float:
    """Calcula el peso ponderado w_i de un reporte aplicando decaimiento exponencial."""
    edad_segundos = (ahora - reporte.observado_en).total_seconds()
    edad_horas = max(0.0, edad_segundos / 3600.0)

    delta_fresco = max(0.0, edad_horas - params.vigencia_fresco_horas)
    exponente = delta_fresco / params.vigencia_vida_media_horas

    factor_foto = params.peso_con_foto if reporte.tiene_foto else 1.0
    es_usuario = reporte.fuente == "usuario"
    rep_autor = reporte.reputacion_autor if es_usuario else params.reputacion_inicial

    peso = rep_autor * (0.5**exponente) * factor_foto
    return float(peso)


def calcular_mediana_ponderada(
    reportes_con_pesos: list[tuple[CandidatoReporte, float]],
) -> tuple[CandidatoReporte, int]:
    """Calcula la mediana ponderada eligiendo el reporte que alcanza el 50 % del peso acumulado."""
    if not reportes_con_pesos:
        raise ValueError("No se puede calcular mediana ponderada de una lista vacia.")

    # Ordenar por precio ascendente y ante empate por fecha mas reciente
    ordenados = sorted(
        reportes_con_pesos,
        key=lambda par: (par[0].precio_cop, -par[0].observado_en.timestamp()),
    )
    peso_total = sum(peso for _, peso in ordenados)
    umbral_mitad = peso_total / 2.0

    acumulado = 0.0
    for rep, peso in ordenados:
        acumulado += peso
        if acumulado >= umbral_mitad:
            return rep, rep.precio_cop

    # Respaldo de seguridad por redondeo en coma flotante
    ultimo_rep = ordenados[-1][0]
    return ultimo_rep, ultimo_rep.precio_cop


def calcular_dispersion_mad(precios: list[int]) -> float:
    """Calcula la dispersion relativa MAD / mediana. Retorna 0.0 si hay menos de 2 elementos."""
    if len(precios) < 2:
        return 0.0

    m = statistics.median(precios)
    if m <= 0:
        return 0.0

    diferencias = [abs(p - m) for p in precios]
    mad = statistics.median(diferencias)
    return float(mad / m)
