"""Pruebas unitarias TDD para deteccion de anomalias en reportes de precios (Tarea T-30)."""

from __future__ import annotations

from decimal import Decimal

from app.dominio.anomalia import (
    CandidatoAnomalia,
    NivelReferencia,
    evaluar_anomalia,
)
from app.dominio.parametros import ParametrosDominio


def test_caso_1_z_score_claro() -> None:
    """10 reportes entre 2600 y 2700; reporte de 900 genera anomalia con z-score."""
    params = ParametrosDominio()
    # Mediana ~2650, MAD ~25. 900 dista 1750, M = 0.6745 * 1750 / 25 >> 3.5
    valores_nivel_1 = [2600, 2620, 2640, 2650, 2660, 2670, 2680, 2690, 2700, 2650]
    niveles = NivelReferencia(presentacion_tienda=valores_nivel_1)

    candidato = CandidatoAnomalia(precio_cop=900, precio_por_base=Decimal("0.9"))
    resultado = evaluar_anomalia(candidato, niveles, params)

    assert resultado.conjunto_referencia == "presentacion_tienda"
    assert resultado.es_anomalo is True
    assert resultado.puntaje_anomalia is not None
    assert resultado.puntaje_anomalia > params.anomalia_z_umbral


def test_caso_2_metodo_porcentual_n_4() -> None:
    """Con n=4, desv > 30 % es anomalo (3510) y desv <= 30 % no lo es (3120)."""
    params = ParametrosDominio()
    valores_n4 = [2600, 2600, 2600, 2600]
    niveles = NivelReferencia(presentacion_tienda=valores_n4)

    # 3510 / 2600 = 1.35 (+35 %)
    cand_alto = CandidatoAnomalia(precio_cop=3510, precio_por_base=Decimal("3.51"))
    res_alto = evaluar_anomalia(cand_alto, niveles, params)
    assert res_alto.es_anomalo is True
    assert res_alto.puntaje_anomalia == 0.35

    # 3120 / 2600 = 1.20 (+20 %)
    cand_ok = CandidatoAnomalia(precio_cop=3120, precio_por_base=Decimal("3.12"))
    res_ok = evaluar_anomalia(cand_ok, niveles, params)
    assert res_ok.es_anomalo is False
    assert res_ok.puntaje_anomalia == 0.20


def test_caso_3_mad_cero_respaldo_porcentual() -> None:
    """6 reportes identicos (MAD=0) usan respaldo porcentual sin division por cero."""
    params = ParametrosDominio()
    valores_identicos = [2600, 2600, 2600, 2600, 2600, 2600]
    niveles = NivelReferencia(presentacion_tienda=valores_identicos)

    # 2700 (+3.8 %) -> normal
    res_ok = evaluar_anomalia(
        CandidatoAnomalia(precio_cop=2700, precio_por_base=Decimal("2.7")), niveles, params
    )
    assert res_ok.es_anomalo is False
    assert res_ok.puntaje_anomalia == 0.038

    # 3600 (+38.5 %) -> anomalo
    res_alto = evaluar_anomalia(
        CandidatoAnomalia(precio_cop=3600, precio_por_base=Decimal("3.6")), niveles, params
    )
    assert res_alto.es_anomalo is True
    assert res_alto.puntaje_anomalia == 0.385


def test_caso_4_sin_referencia_n_menor_que_3() -> None:
    """Si ningun nivel alcanza n >= 3, resultado es 'sin_referencia' y no es anomalo."""
    params = ParametrosDominio()
    niveles = NivelReferencia(
        presentacion_tienda=[2500, 2600],  # n = 2 < 3
        presentacion=[2550],  # n = 1 < 3
        producto_unitario=[Decimal("2.5"), Decimal("2.6")],  # n = 2 < 3
    )

    candidato = CandidatoAnomalia(precio_cop=2700, precio_por_base=Decimal("2.7"))
    resultado = evaluar_anomalia(candidato, niveles, params)

    assert resultado.conjunto_referencia == "sin_referencia"
    assert resultado.es_anomalo is False
    assert resultado.puntaje_anomalia is None
    assert "ratio_extremo" not in resultado.senales


def test_caso_5_aislamiento_tienda_vs_cadena() -> None:
    """Usa Nivel 1 (tienda de barrio a 2500) ignorando supermercados mas costosos (3200)."""
    params = ParametrosDominio()
    niveles = NivelReferencia(
        presentacion_tienda=[2500, 2500, 2500, 2500, 2500],  # Tienda de barrio
        presentacion=[3200, 3200, 3200, 3200, 3200],  # Cadenas
    )

    # Reporte de 2550 en la tienda de barrio: comparado con su propio nivel 1 da normal
    candidato = CandidatoAnomalia(precio_cop=2550, precio_por_base=Decimal("2.55"))
    resultado = evaluar_anomalia(candidato, niveles, params)

    assert resultado.conjunto_referencia == "presentacion_tienda"
    assert resultado.es_anomalo is False


def test_caso_6_error_digitacion_ratio_extremo() -> None:
    """Mediana 2600, reporte de 26000 (10x) activa ratio_extremo."""
    params = ParametrosDominio()
    niveles = NivelReferencia(presentacion_tienda=[2600, 2600, 2600, 2600, 2600])

    candidato = CandidatoAnomalia(precio_cop=26000, precio_por_base=Decimal("26.0"))
    resultado = evaluar_anomalia(candidato, niveles, params)

    assert resultado.es_anomalo is True
    assert "ratio_extremo" in resultado.senales


def test_caso_9_determinismo_estricto_1000_ejecuciones() -> None:
    """1.000 ejecuciones con la misma entrada producen exactamente el mismo resultado."""
    params = ParametrosDominio()
    niveles = NivelReferencia(presentacion_tienda=[2600, 2620, 2650, 2680, 2700])
    candidato = CandidatoAnomalia(precio_cop=2650, precio_por_base=Decimal("2.65"))

    primero = evaluar_anomalia(candidato, niveles, params)
    for _ in range(999):
        actual = evaluar_anomalia(candidato, niveles, params)
        assert actual == primero
