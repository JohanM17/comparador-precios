"""Modulo de dominio para la clasificacion y asignacion del sello de confianza del precio."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.dominio.parametros import ParametrosDominio
from app.dominio.unidades import calcular_precio_por_base
from app.dominio.vigencia import (
    CandidatoReporte,
    calcular_dispersion_mad,
    calcular_mediana_ponderada,
    calcular_peso_reporte,
)


@dataclass(frozen=True)
class ResultadoSelloYPrecio:
    """Resultado del calculo del precio vigente y su evaluacion de sello de calidad."""

    sello: str
    motivo_sello: str | None
    precio_cop: int
    precio_por_base: Decimal
    cantidad_base: Decimal
    n_reportes_validos: int
    n_fuentes: int
    dispersion: float | None
    ultimo_reporte_en: datetime
    reporte_origen_id: UUID | None


def _clasificar_reportes(
    reportes: list[CandidatoReporte],
    ahora: datetime,
    params: ParametrosDominio,
) -> tuple[list[CandidatoReporte], list[CandidatoReporte], list[CandidatoReporte]]:
    """Clasifica los reportes en vigentes, antiguos y dudosos recientes."""
    seg_vigente = params.vigencia_vigente_dias * 86400
    seg_antiguo = params.vigencia_antiguo_dias * 86400

    vigentes: list[CandidatoReporte] = []
    antiguos: list[CandidatoReporte] = []
    dudosos_recientes: list[CandidatoReporte] = []

    for r in reportes:
        edad = (ahora - r.observado_en).total_seconds()
        if r.estado == "aceptado":
            if edad <= seg_vigente:
                vigentes.append(r)
            elif edad <= seg_antiguo:
                antiguos.append(r)
        elif r.estado == "dudoso" and edad <= seg_vigente:
            dudosos_recientes.append(r)

    return vigentes, antiguos, dudosos_recientes


def _evaluar_sin_aceptados(
    dudosos_recientes: list[CandidatoReporte],
) -> ResultadoSelloYPrecio | None:
    """Aplica Regla 1: Dudoso por ausencia de aceptados pero con dudosos recientes."""
    if not dudosos_recientes:
        return None

    precios = [r.precio_cop for r in dudosos_recientes]
    mediana_p = int(statistics.median(precios))
    mas_reciente = max(dudosos_recientes, key=lambda x: x.observado_en)
    ppb = calcular_precio_por_base(mediana_p, mas_reciente.cantidad_base)

    return ResultadoSelloYPrecio(
        sello="dudoso",
        motivo_sello="En revisión: reportes sin confirmar",
        precio_cop=mediana_p,
        precio_por_base=ppb,
        cantidad_base=mas_reciente.cantidad_base,
        n_reportes_validos=0,
        n_fuentes=len({r.autor_id for r in dudosos_recientes if r.autor_id}),
        dispersion=None,
        ultimo_reporte_en=mas_reciente.observado_en,
        reporte_origen_id=mas_reciente.id,
    )


def _evaluar_desactualizados(
    antiguos: list[CandidatoReporte],
    ahora: datetime,
) -> ResultadoSelloYPrecio:
    """Aplica Regla 2: Desactualizado por reportes aceptados de entre 8 y 30 dias."""
    mas_antiguo = max(antiguos, key=lambda x: x.observado_en)
    dias = int((ahora - mas_antiguo.observado_en).total_seconds() // 86400)
    ppb = calcular_precio_por_base(mas_antiguo.precio_cop, mas_antiguo.cantidad_base)

    return ResultadoSelloYPrecio(
        sello="desactualizado",
        motivo_sello=f"Sin actualizar hace {dias} días",
        precio_cop=mas_antiguo.precio_cop,
        precio_por_base=ppb,
        cantidad_base=mas_antiguo.cantidad_base,
        n_reportes_validos=0,
        n_fuentes=1,
        dispersion=None,
        ultimo_reporte_en=mas_antiguo.observado_en,
        reporte_origen_id=mas_antiguo.id,
    )


def _evaluar_vigentes(
    vigentes: list[CandidatoReporte],
    ahora: datetime,
    params: ParametrosDominio,
) -> ResultadoSelloYPrecio:
    """Aplica Reglas 3, 4 y 5 sobre reportes vigentes aceptados."""
    pesos = [calcular_peso_reporte(r, ahora, params) for r in vigentes]
    pares = list(zip(vigentes, pesos, strict=True))
    rep_elegido, precio_mediana = calcular_mediana_ponderada(pares)

    n_validos = len(vigentes)
    cuentas_distintas = len({r.autor_id for r in vigentes if r.autor_id and r.fuente == "usuario"})
    hay_semilla = 1 if any(r.fuente == "semilla" for r in vigentes) else 0
    n_fuentes = cuentas_distintas + hay_semilla

    dispersion = calcular_dispersion_mad([r.precio_cop for r in vigentes])
    ultimo_observado = max(r.observado_en for r in vigentes)
    ppb = calcular_precio_por_base(precio_mediana, rep_elegido.cantidad_base)

    if n_validos < params.sello_n_min_validos or n_fuentes < params.sello_min_fuentes:
        sello = "pocos_datos"
        motivo = "Pocos datos: ayúdanos a confirmarlo"
    elif dispersion > params.sello_dispersion_max:
        sello = "dudoso"
        motivo = "Reportes contradictorios"
    else:
        sello = "confiable"
        motivo = None

    return ResultadoSelloYPrecio(
        sello=sello,
        motivo_sello=motivo,
        precio_cop=precio_mediana,
        precio_por_base=ppb,
        cantidad_base=rep_elegido.cantidad_base,
        n_reportes_validos=n_validos,
        n_fuentes=n_fuentes,
        dispersion=round(dispersion, 4),
        ultimo_reporte_en=ultimo_observado,
        reporte_origen_id=rep_elegido.id,
    )


def evaluar_sello_y_precio(
    reportes: list[CandidatoReporte],
    ahora: datetime,
    params: ParametrosDominio,
) -> ResultadoSelloYPrecio | None:
    """Aplica el arbol determinista de 5 reglas para establecer el precio vigente y su sello."""
    vigentes, antiguos, dudosos_recientes = _clasificar_reportes(reportes, ahora, params)

    if not vigentes and not antiguos:
        return _evaluar_sin_aceptados(dudosos_recientes)

    if not vigentes and antiguos:
        return _evaluar_desactualizados(antiguos, ahora)

    return _evaluar_vigentes(vigentes, ahora, params)
