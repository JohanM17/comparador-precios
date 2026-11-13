"""Modulo de dominio para la evaluacion del riesgo de contexto y decision de aceptacion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.dominio.anomalia import (
    CandidatoAnomalia,
    NivelReferencia,
    evaluar_anomalia,
)
from app.dominio.parametros import ParametrosDominio
from app.dominio.reputacion import es_cuenta_nueva, tiene_reputacion_baja


@dataclass(frozen=True)
class ContextoReporte:
    """Metadatos del usuario y entorno al momento de emitir el reporte."""

    tiene_foto: bool
    creado_en_autor: datetime
    reportes_corroborados: int
    reputacion_autor: Decimal
    es_rafaga: bool = False


@dataclass(frozen=True)
class EvaluacionReporte:
    """Resultado integral de la evaluacion de fraude, anomalia y riesgo de un reporte."""

    estado: str
    senales: list[str] = field(default_factory=list)
    puntaje_anomalia: float | None = None
    riesgo_contexto: float = 0.0
    conjunto_referencia: str = "sin_referencia"
    es_anomalo: bool = False


def evaluar_reporte(
    candidato: CandidatoAnomalia,
    niveles: NivelReferencia,
    contexto: ContextoReporte,
    ahora: datetime,
    params: ParametrosDominio,
) -> EvaluacionReporte:
    """Ejecuta la evaluacion determinista integrando senales de contexto y anomalia estadistica."""
    anom = evaluar_anomalia(candidato, niveles, params)

    senales_contexto: list[str] = []
    if not contexto.tiene_foto:
        senales_contexto.append("sin_foto")

    if es_cuenta_nueva(
        contexto.creado_en_autor,
        ahora,
        contexto.reportes_corroborados,
        params.cuenta_nueva_dias,
        params.cuenta_nueva_min_aceptados,
    ):
        senales_contexto.append("cuenta_nueva")

    if contexto.es_rafaga:
        senales_contexto.append("rafaga")

    if tiene_reputacion_baja(
        contexto.reputacion_autor,
        Decimal(str(params.reputacion_baja_umbral)),
    ):
        senales_contexto.append("reputacion_baja")

    riesgo = sum(params.riesgo_pesos.get(s, 0.0) for s in senales_contexto)
    riesgo_redondeado = round(riesgo, 3)

    todas_las_senales = list(anom.senales) + senales_contexto

    es_dudoso = anom.es_anomalo or (riesgo_redondeado >= params.riesgo_umbral_dudoso)
    estado_final = "dudoso" if es_dudoso else "aceptado"

    return EvaluacionReporte(
        estado=estado_final,
        senales=todas_las_senales,
        puntaje_anomalia=anom.puntaje_anomalia,
        riesgo_contexto=riesgo_redondeado,
        conjunto_referencia=anom.conjunto_referencia,
        es_anomalo=anom.es_anomalo,
    )
