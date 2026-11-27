"""Pruebas unitarias TDD de las reglas de promocion comercial (FR-024, FR-025, tarea T-65).

Lo que se verifica viene de dos sitios:

- Ley 1480 de 2011, articulo 33: toda promocion debe informar sus condiciones y su
  duracion. Una promocion sin condiciones o sin vigencia no se publica.
- ADR-022: el ahorro de una promocion es informativo. Nunca entra en el total ni en el
  orden de la comparacion, y cuando depende de cantidades se declara el supuesto.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.dominio.promocion import (
    ReglaPromocion,
    calcular_ahorro_informativo,
    esta_vigente,
    validar_promocion,
)

AHORA = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
CONDICIONES = "Valido en la sede del centro, hasta agotar diez unidades por cliente."


def _regla(
    tipo: str = "porcentaje",
    porcentaje_descuento: int | None = 20,
    precio_especial_cop: int | None = None,
    pague_x: int | None = None,
    lleve_y: int | None = None,
    condiciones: str = CONDICIONES,
    desde_dias: int = -1,
    hasta_dias: int | None = 7,
    hasta_revocar: bool = False,
) -> ReglaPromocion:
    return ReglaPromocion(
        tipo=tipo,
        porcentaje_descuento=porcentaje_descuento,
        precio_especial_cop=precio_especial_cop,
        pague_x=pague_x,
        lleve_y=lleve_y,
        condiciones=condiciones,
        vigente_desde=AHORA + timedelta(days=desde_dias),
        vigente_hasta=None if hasta_dias is None else AHORA + timedelta(days=hasta_dias),
        hasta_revocar=hasta_revocar,
    )


def test_promocion_por_porcentaje_bien_formada_es_valida() -> None:
    assert validar_promocion(_regla()) == []


def test_promocion_sin_condiciones_se_rechaza() -> None:
    motivos = validar_promocion(_regla(condiciones="   "))
    assert any("condiciones" in m.lower() for m in motivos)


def test_promocion_con_condiciones_demasiado_cortas_se_rechaza() -> None:
    # "Solo hoy" no informa modo ni lugar: no cumple el articulo 33.
    motivos = validar_promocion(_regla(condiciones="Solo hoy"))
    assert any("condiciones" in m.lower() for m in motivos)


def test_promocion_sin_vigencia_se_rechaza() -> None:
    motivos = validar_promocion(_regla(hasta_dias=None, hasta_revocar=False))
    assert any("vigencia" in m.lower() for m in motivos)


def test_promocion_con_fecha_final_y_hasta_revocar_a_la_vez_se_rechaza() -> None:
    motivos = validar_promocion(_regla(hasta_dias=7, hasta_revocar=True))
    assert any("vigencia" in m.lower() for m in motivos)


def test_promocion_hasta_revocar_sin_fecha_final_es_valida() -> None:
    assert validar_promocion(_regla(hasta_dias=None, hasta_revocar=True)) == []


def test_fecha_final_anterior_a_la_inicial_se_rechaza() -> None:
    motivos = validar_promocion(_regla(desde_dias=5, hasta_dias=1))
    assert any("posterior" in m.lower() for m in motivos)


def test_porcentaje_fuera_del_rango_permitido_se_rechaza() -> None:
    assert validar_promocion(_regla(porcentaje_descuento=0)) != []
    assert validar_promocion(_regla(porcentaje_descuento=95)) != []


def test_cada_tipo_exige_sus_campos_y_prohibe_los_ajenos() -> None:
    # Un tipo porcentaje que ademas trae precio especial miente sobre lo que es.
    motivos = validar_promocion(_regla(precio_especial_cop=2000))
    assert any("tipo" in m.lower() for m in motivos)

    faltante = validar_promocion(_regla(tipo="precio_especial", porcentaje_descuento=None))
    assert any("tipo" in m.lower() for m in faltante)


def test_pague_x_lleve_y_exige_llevar_mas_de_lo_que_se_paga() -> None:
    valida = _regla(tipo="pague_x_lleve_y", porcentaje_descuento=None, pague_x=2, lleve_y=3)
    assert validar_promocion(valida) == []

    invalida = _regla(tipo="pague_x_lleve_y", porcentaje_descuento=None, pague_x=3, lleve_y=3)
    assert validar_promocion(invalida) != []


def test_vigencia_por_fechas() -> None:
    assert esta_vigente(_regla(), AHORA) is True
    assert esta_vigente(_regla(desde_dias=2, hasta_dias=9), AHORA) is False
    assert esta_vigente(_regla(desde_dias=-9, hasta_dias=-2), AHORA) is False
    assert esta_vigente(_regla(hasta_dias=None, hasta_revocar=True), AHORA) is True


def test_ahorro_por_porcentaje_es_directo_y_no_es_estimacion() -> None:
    ahorro = calcular_ahorro_informativo(_regla(porcentaje_descuento=20), 3000)

    assert ahorro is not None
    assert ahorro.ahorro_cop == 600
    assert ahorro.unidades_supuestas == 1
    assert ahorro.es_estimacion is False


def test_ahorro_por_precio_especial_es_la_diferencia() -> None:
    regla = _regla(tipo="precio_especial", porcentaje_descuento=None, precio_especial_cop=2400)
    ahorro = calcular_ahorro_informativo(regla, 3000)

    assert ahorro is not None
    assert ahorro.ahorro_cop == 600
    assert ahorro.es_estimacion is False


def test_precio_especial_que_no_rebaja_nada_no_produce_ahorro() -> None:
    regla = _regla(tipo="precio_especial", porcentaje_descuento=None, precio_especial_cop=3200)
    assert calcular_ahorro_informativo(regla, 3000) is None


def test_pague_x_lleve_y_declara_el_supuesto_y_se_marca_como_estimacion() -> None:
    # ADR-022: el ahorro depende de cuantas unidades compre el usuario, dato que no tenemos.
    regla = _regla(tipo="pague_x_lleve_y", porcentaje_descuento=None, pague_x=2, lleve_y=3)
    ahorro = calcular_ahorro_informativo(regla, 3000)

    assert ahorro is not None
    assert ahorro.unidades_supuestas == 3
    assert ahorro.ahorro_cop == 3000
    assert ahorro.es_estimacion is True


def test_una_promocion_invalida_no_calcula_ahorro() -> None:
    assert calcular_ahorro_informativo(_regla(condiciones="   "), 3000) is None
