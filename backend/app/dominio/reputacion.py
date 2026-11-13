"""Modulo de dominio para el calculo bayesiano de reputacion y estado de cuenta."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal


def calcular_reputacion_bayesiana(
    reportes_corroborados: int,
    reportes_malos_confirmados: int,
) -> Decimal:
    """Calcula la reputacion bayesiana segun la formula (A + 2) / (A + 3M + 4)."""
    if reportes_corroborados < 0 or reportes_malos_confirmados < 0:
        raise ValueError("Los contadores de reportes no pueden ser negativos.")

    numerador = Decimal(reportes_corroborados + 2)
    denominador = Decimal(reportes_corroborados + 3 * reportes_malos_confirmados + 4)

    reputacion = numerador / denominador
    return reputacion.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def es_cuenta_nueva(
    creado_en: datetime,
    ahora: datetime,
    reportes_corroborados: int,
    dias_umbral: int = 7,
    min_aceptados: int = 3,
) -> bool:
    """Retorna True si la cuenta tiene menos de 7 dias O menos de 3 corroboraciones."""
    edad_segundos = (ahora - creado_en).total_seconds()
    antiguedad_insuficiente = edad_segundos < (dias_umbral * 86400)
    reportes_insuficientes = reportes_corroborados < min_aceptados
    return antiguedad_insuficiente or reportes_insuficientes


def tiene_reputacion_baja(
    reputacion: Decimal,
    umbral: Decimal = Decimal("0.350"),
) -> bool:
    """Retorna True si la reputacion es estrictamente menor al umbral critico."""
    return reputacion < umbral
