"""Pruebas unitarias TDD para reputacion bayesiana y riesgo de contexto (Tarea T-31)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.dominio.anomalia import CandidatoAnomalia, NivelReferencia
from app.dominio.parametros import ParametrosDominio
from app.dominio.reputacion import (
    calcular_reputacion_bayesiana,
    es_cuenta_nueva,
    tiene_reputacion_baja,
)
from app.dominio.riesgo import (
    ContextoReporte,
    evaluar_reporte,
)


def test_reputacion_bayesiana_4_casos_exactos() -> None:
    """Verifica la formula bayesiana (A + 2) / (A + 3M + 4) redondeada a 3 decimales."""
    # (A=0, M=0) -> 2/4 = 0.500
    assert calcular_reputacion_bayesiana(0, 0) == Decimal("0.500")

    # (A=10, M=0) -> 12/14 = 0.85714... -> 0.857
    assert calcular_reputacion_bayesiana(10, 0) == Decimal("0.857")

    # (A=10, M=2) -> 12 / (10 + 6 + 4) = 12/20 = 0.600
    assert calcular_reputacion_bayesiana(10, 2) == Decimal("0.600")

    # (A=0, M=1) -> 2 / (0 + 3 + 4) = 2/7 = 0.28571... -> 0.286
    assert calcular_reputacion_bayesiana(0, 1) == Decimal("0.286")

    # Validar rechazo de valores negativos
    with pytest.raises(ValueError, match="negativos"):
        calcular_reputacion_bayesiana(-1, 0)


def test_parametros_dominio_desde_dict() -> None:
    """Verifica la conversion e instanciacion desde diccionario de base de datos."""
    dict_sql = {
        "precio.min_cop": 100,
        "precio.max_cop": 1500000,
        "sello.n_min_validos": 4,
    }
    p = ParametrosDominio.desde_dict(dict_sql)
    assert p.precio_min_cop == 100
    assert p.precio_max_cop == 1500000
    assert p.sello_n_min_validos == 4


def test_predicado_es_cuenta_nueva() -> None:
    """Es nueva si tiene < 7 dias O menos de 3 reportes corroborados."""
    ahora = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)

    # 2 dias y 10 corroborados -> Nueva por antiguedad
    assert es_cuenta_nueva(
        creado_en=ahora - timedelta(days=2),
        ahora=ahora,
        reportes_corroborados=10,
    )

    # 10 dias y 2 corroborados -> Nueva por falta de corroboraciones
    assert es_cuenta_nueva(
        creado_en=ahora - timedelta(days=10),
        ahora=ahora,
        reportes_corroborados=2,
    )

    # 10 dias y 3 corroborados -> Cuenta establecida (False)
    assert not es_cuenta_nueva(
        creado_en=ahora - timedelta(days=10),
        ahora=ahora,
        reportes_corroborados=3,
    )


def test_predicado_tiene_reputacion_baja() -> None:
    """Activa reputacion_baja si la reputacion es estrictamente menor a 0.350."""
    assert tiene_reputacion_baja(Decimal("0.349"))
    assert not tiene_reputacion_baja(Decimal("0.350"))
    assert not tiene_reputacion_baja(Decimal("0.500"))


def test_caso_7_usuario_nuevo_honesto_sin_foto_es_aceptado() -> None:
    """Precio normal, sin_foto (0.15) + cuenta_nueva (0.25) = 0.40 < 0.60 -> 'aceptado'."""
    params = ParametrosDominio()
    ahora = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)

    candidato = CandidatoAnomalia(precio_cop=2600, precio_por_base=Decimal("2.6"))
    niveles = NivelReferencia(presentacion_tienda=[2600, 2600, 2600, 2600, 2600])

    contexto = ContextoReporte(
        tiene_foto=False,  # sin_foto -> 0.15
        creado_en_autor=ahora - timedelta(days=2),  # cuenta_nueva -> 0.25
        reportes_corroborados=0,
        reputacion_autor=Decimal("0.500"),
        es_rafaga=False,
    )

    evaluacion = evaluar_reporte(candidato, niveles, contexto, ahora, params)
    assert evaluacion.riesgo_contexto == 0.40
    assert not evaluacion.es_anomalo
    assert evaluacion.estado == "aceptado"
    assert "sin_foto" in evaluacion.senales
    assert "cuenta_nueva" in evaluacion.senales


def test_caso_8_ataque_en_rafaga_cuentas_nuevas_es_dudoso() -> None:
    """Ataque en rafaga: cuenta_nueva (0.25) + rafaga (0.40) = 0.65 >= 0.60 -> 'dudoso'."""
    params = ParametrosDominio()
    ahora = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)

    candidato = CandidatoAnomalia(precio_cop=2600, precio_por_base=Decimal("2.6"))
    niveles = NivelReferencia(presentacion_tienda=[2600, 2600, 2600, 2600, 2600])

    contexto = ContextoReporte(
        tiene_foto=True,
        creado_en_autor=ahora - timedelta(days=1),  # cuenta_nueva -> 0.25
        reportes_corroborados=0,
        reputacion_autor=Decimal("0.500"),
        es_rafaga=True,  # rafaga -> 0.40
    )

    evaluacion = evaluar_reporte(candidato, niveles, contexto, ahora, params)
    assert evaluacion.riesgo_contexto == 0.65
    assert not evaluacion.es_anomalo
    assert evaluacion.estado == "dudoso"
    assert "rafaga" in evaluacion.senales
    assert "cuenta_nueva" in evaluacion.senales


def test_evaluar_reporte_determinismo_1000_veces() -> None:
    """1.000 evaluaciones con la misma entrada producen resultados identicos."""
    params = ParametrosDominio()
    ahora = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)
    candidato = CandidatoAnomalia(precio_cop=2600, precio_por_base=Decimal("2.6"))
    niveles = NivelReferencia(presentacion_tienda=[2600, 2600, 2600, 2600, 2600])
    contexto = ContextoReporte(
        tiene_foto=True,
        creado_en_autor=ahora - timedelta(days=20),
        reportes_corroborados=5,
        reputacion_autor=Decimal("0.800"),
        es_rafaga=False,
    )

    primero = evaluar_reporte(candidato, niveles, contexto, ahora, params)
    for _ in range(999):
        actual = evaluar_reporte(candidato, niveles, contexto, ahora, params)
        assert actual == primero
