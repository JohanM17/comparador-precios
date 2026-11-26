"""Pruebas unitarias del generador de historial demo (Tarea T-118)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

import pytest

from scripts.semilla_historial import (
    DIAS_HISTORIAL,
    PERFIL_VECINO_CENTENARIO,
    PuntoDemo,
    generar_puntos_demo,
)

AHORA = datetime(2026, 11, 25, 12, 0, 0, tzinfo=UTC)
PRODUCTO_ID = uuid4()
PRESENTACION_ID = uuid4()
ESTABLECIMIENTO_ID = uuid4()
CANTIDAD_BASE = Decimal("1000.000")
PRECIO_BASE_COP = 5000


def _generar(
    *,
    cantidad_base: Decimal = CANTIDAD_BASE,
    precio_base_cop: int = PRECIO_BASE_COP,
    ahora: datetime = AHORA,
) -> list[PuntoDemo]:
    """Invoca el generador con los datos de prueba de la tarea."""
    return generar_puntos_demo(
        producto_id=PRODUCTO_ID,
        presentacion_id=PRESENTACION_ID,
        establecimiento_id=ESTABLECIMIENTO_ID,
        cantidad_base=cantidad_base,
        precio_base_cop=precio_base_cop,
        ahora=ahora,
    )


def test_ids_deterministas_entre_llamadas_iguales() -> None:
    """Dos llamadas con los mismos argumentos producen los mismos IDs."""
    primero = _generar()
    segundo = _generar()

    assert [punto["id"] for punto in primero] == [punto["id"] for punto in segundo]
    assert primero == segundo


def test_ids_siguen_la_formula_uuid5_documentada() -> None:
    """Cada ID se deriva con uuid5 del namespace DNS y el indice del punto."""
    puntos = _generar()

    for indice, punto in enumerate(puntos):
        esperado = uuid5(
            NAMESPACE_DNS,
            f"demo-historial:{PRODUCTO_ID}:{PRESENTACION_ID}:{ESTABLECIMIENTO_ID}:{indice}",
        )
        assert punto["id"] == esperado
        assert isinstance(punto["id"], UUID)


def test_cantidad_y_ventana_de_90_dias() -> None:
    """Genera al menos 6 puntos, todos dentro de los ultimos 90 dias."""
    puntos = _generar()

    assert len(puntos) == len(DIAS_HISTORIAL)
    assert len(puntos) >= 6

    for punto in puntos:
        observado_en = punto["observado_en"]
        assert isinstance(observado_en, datetime)
        antiguedad = AHORA - observado_en
        assert timedelta(0) < antiguedad <= timedelta(days=90)
        assert observado_en.utcoffset() == timedelta(0)

    fechas = [punto["observado_en"] for punto in puntos]
    assert fechas == sorted(fechas), "La serie debe quedar ordenada del mas viejo al mas nuevo."


def test_estados_y_origenes_variados() -> None:
    """Hay al menos un punto dudoso y al menos dos origenes distintos."""
    puntos = _generar()

    estados = {punto["estado"] for punto in puntos}
    fuentes = {punto["fuente"] for punto in puntos}

    assert "dudoso" in estados
    assert len(fuentes) >= 2
    assert fuentes <= {"usuario", "comercio", "semilla"}

    for punto in puntos:
        if punto["estado"] == "aceptado":
            assert punto["conjunto_referencia"] == "presentacion_tienda"
        else:
            assert punto["estado"] == "dudoso"
            assert punto["conjunto_referencia"] == "sin_referencia"


def test_reportante_solo_para_origen_usuario() -> None:
    """Los reportes de usuario usan el perfil semilla; comercio y semilla van sin autor."""
    for punto in _generar():
        if punto["fuente"] == "usuario":
            assert punto["reportante_id"] == PERFIL_VECINO_CENTENARIO
        else:
            assert punto["reportante_id"] is None


def test_precio_por_base_usa_decimal_y_es_correcto() -> None:
    """El precio unitario se calcula con Decimal y seis decimales."""
    puntos = _generar()

    for punto in puntos:
        precio_cop = punto["precio_cop"]
        precio_por_base = punto["precio_por_base"]

        assert isinstance(precio_cop, int)
        assert precio_cop > 0
        assert isinstance(precio_por_base, Decimal)
        esperado = (Decimal(precio_cop) / CANTIDAD_BASE).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        assert precio_por_base == esperado


def test_precio_base_determinista_y_creciente() -> None:
    """El precio sigue la formula documentada: base mas 100 COP por indice."""
    puntos = _generar()

    precios = [punto["precio_cop"] for punto in puntos]
    esperados = [PRECIO_BASE_COP + indice * 100 for indice in range(len(puntos))]
    assert precios == esperados


def test_todos_los_puntos_son_demo() -> None:
    """Todos los puntos quedan marcados con es_demo=True."""
    puntos = _generar()

    assert puntos
    assert all(punto["es_demo"] is True for punto in puntos)


def test_ahora_naive_se_interpreta_como_utc() -> None:
    """Un instante sin zona horaria se asume UTC para no emitir fechas ambiguas."""
    puntos = _generar(ahora=datetime(2026, 11, 25, 12, 0, 0))

    assert puntos
    assert all(punto["observado_en"].utcoffset() == timedelta(0) for punto in puntos)


def test_no_muta_la_entrada_y_devuelve_listas_nuevas() -> None:
    """Modificar el resultado no altera el original ni las llamadas posteriores."""
    ahora_local = AHORA.astimezone(timezone(timedelta(hours=-5)))
    primero = _generar(ahora=ahora_local)

    assert ahora_local.utcoffset() == timedelta(hours=-5)

    primero.clear()

    segundo = _generar(ahora=ahora_local)
    assert len(segundo) == len(DIAS_HISTORIAL)
    assert segundo[0]["precio_cop"] == PRECIO_BASE_COP
    assert all(punto["observado_en"].utcoffset() == timedelta(0) for punto in segundo)


@pytest.mark.parametrize("cantidad_base", [Decimal("0"), Decimal("-1")])
def test_rechaza_cantidad_base_no_positiva(cantidad_base: Decimal) -> None:
    """Una cantidad base invalida falla antes de generar puntos."""
    with pytest.raises(ValueError):
        _generar(cantidad_base=cantidad_base)


@pytest.mark.parametrize("precio_base_cop", [0, -100])
def test_rechaza_precio_base_no_positivo(precio_base_cop: int) -> None:
    """Un precio base invalido falla antes de generar puntos."""
    with pytest.raises(ValueError):
        _generar(precio_base_cop=precio_base_cop)
