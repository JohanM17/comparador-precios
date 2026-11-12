"""Pruebas unitarias y de propiedades del dominio de conversión de unidades."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.dominio.unidades import (
    ErrorUnidadesIncompatibles,
    calcular_cantidad_base,
    calcular_precio_por_base,
    calcular_precio_visualizacion,
    parsear_cantidad,
)


def test_parsear_cantidad_gramos() -> None:
    """Verifica variantes comunes de gramos."""
    for texto in ("500 g", "500g", "500 gr", "500GR"):
        res = parsear_cantidad(texto)
        assert res is not None
        assert res.valor_cantidad == Decimal("500")
        assert res.unidad == "g"
        assert res.multiplicador == 1
        assert res.cantidad_base == Decimal("500.000")


def test_parsear_cantidad_kilos_y_fracciones() -> None:
    """Verifica kilogramos y expresiones fraccionarias populares."""
    for texto in ("1/2 kg", "½ kg", "medio kilo", "0.5 kg", "0,5 kg"):
        res = parsear_cantidad(texto)
        assert res is not None
        assert res.valor_cantidad == Decimal("0.5")
        assert res.unidad == "kg"
        assert res.multiplicador == 1
        assert res.cantidad_base == Decimal("500.000")


def test_parsear_cantidad_libras_colombianas() -> None:
    """Verifica la libra colombiana métrica (500 g)."""
    for texto in ("1 libra", "1 lb", "1lb", "una libra"):
        res = parsear_cantidad(texto)
        assert res is not None
        assert res.valor_cantidad == Decimal("1")
        assert res.unidad == "lb"
        assert res.multiplicador == 1
        assert res.cantidad_base == Decimal("500.000")


def test_parsear_cantidad_liquidos() -> None:
    """Verifica litros con coma o punto decimal."""
    for texto in ("1,5 L", "1.5 l", "1.5L"):
        res = parsear_cantidad(texto)
        assert res is not None
        assert res.valor_cantidad == Decimal("1.5")
        assert res.unidad == "l"
        assert res.multiplicador == 1
        assert res.cantidad_base == Decimal("1500.000")


def test_parsear_cantidad_multipacks() -> None:
    """Verifica presentaciones multipack con multiplicador."""
    for texto in ("6 x 330 ml", "x6 330ml", "6x330 ml", "6 X 330 ML"):
        res = parsear_cantidad(texto)
        assert res is not None
        assert res.valor_cantidad == Decimal("330")
        assert res.unidad == "ml"
        assert res.multiplicador == 6
        assert res.cantidad_base == Decimal("1980.000")


def test_parsear_cantidad_docena() -> None:
    """Verifica la unidad especial docena (12 unidades)."""
    for texto in ("docena", "1 docena"):
        res = parsear_cantidad(texto)
        assert res is not None
        assert res.valor_cantidad == Decimal("1")
        assert res.unidad == "docena"
        assert res.multiplicador == 1
        assert res.cantidad_base == Decimal("12.000")


def test_parsear_cantidad_sin_unidad_retorna_none() -> None:
    """Verifica que un número solo no se inventa la unidad."""
    assert parsear_cantidad("500") is None
    assert parsear_cantidad("") is None
    assert parsear_cantidad("arroz blanco") is None


def test_parsear_cantidad_expresiones_adicionales() -> None:
    """Verifica media libra, medio litro, division por cero y unidades desconocidas."""
    res_libra = parsear_cantidad("media libra")
    assert res_libra is not None
    assert res_libra.cantidad_base == Decimal("250.000")

    res_litro = parsear_cantidad("medio litro")
    assert res_litro is not None
    assert res_litro.cantidad_base == Decimal("500.000")

    assert parsear_cantidad("1/0 kg") is None
    assert parsear_cantidad("500 metros") is None


def test_calcular_cantidad_base_multiplicador_invalido() -> None:
    """Verifica excepcion por multiplicador menor a 1."""
    valor = Decimal("100")
    with pytest.raises(ValueError, match="El multiplicador"):
        calcular_cantidad_base(valor, "g", "g", multiplicador=0)


def test_calcular_precio_por_base_precio_invalido() -> None:
    """Verifica excepcion por precio no positivo."""
    cant = Decimal("100.000")
    with pytest.raises(ValueError, match="El precio en COP"):
        calcular_precio_por_base(0, cant)


def test_calcular_precio_por_base_cantidad_invalida() -> None:
    """Verifica excepcion por cantidad base no positiva."""
    cant_cero = Decimal("0.000")
    with pytest.raises(ValueError, match="La cantidad base"):
        calcular_precio_por_base(1000, cant_cero)


def test_calcular_precio_visualizacion_unidad_invalida() -> None:
    """Verifica excepcion por unidad base desconocida en visualizacion."""
    precio = Decimal("5.0")
    with pytest.raises(ErrorUnidadesIncompatibles):
        calcular_precio_visualizacion(precio, "invalida")


@pytest.mark.parametrize(
    ("valor", "unidad", "unidad_base"),
    [
        (Decimal("500"), "ml", "g"),
        (Decimal("1"), "kg", "ml"),
        (Decimal("1"), "unidad", "g"),
    ],
)
def test_incompatibilidad_unidades(valor: Decimal, unidad: str, unidad_base: str) -> None:
    """Lanza ErrorUnidadesIncompatibles si se mezclan familias dimensionales."""
    with pytest.raises(ErrorUnidadesIncompatibles):
        calcular_cantidad_base(valor, unidad, unidad_base)


def test_comparacion_guia_arroz() -> None:
    """Verifica el caso de negocio: 1 kg a $5.000 vs 500 g a $2.800."""
    # Presentación A: 1 kg a $5.000
    cant_a = calcular_cantidad_base(Decimal("1"), "kg", "g")
    precio_base_a = calcular_precio_por_base(5000, cant_a)
    vis_a, unidad_a = calcular_precio_visualizacion(precio_base_a, "g")

    # Presentación B: 500 g a $2.800
    cant_b = calcular_cantidad_base(Decimal("500"), "g", "g")
    precio_base_b = calcular_precio_por_base(2800, cant_b)
    vis_b, unidad_b = calcular_precio_visualizacion(precio_base_b, "g")

    assert cant_a == Decimal("1000.000")
    assert cant_b == Decimal("500.000")
    assert precio_base_a == Decimal("5.000000")
    assert precio_base_b == Decimal("5.600000")
    assert precio_base_a < precio_base_b
    assert (vis_a, unidad_a) == (5000, "kg")
    assert (vis_b, unidad_b) == (5600, "kg")


def test_visualizacion_liquidos_y_unidades() -> None:
    """Verifica el precio de visualización para líquidos y unidades."""
    # 250 ml a $1.000 -> $4.000/litro
    cant_liq = calcular_cantidad_base(Decimal("250"), "ml", "ml")
    pb_liq = calcular_precio_por_base(1000, cant_liq)
    vis_liq, unidad_liq = calcular_precio_visualizacion(pb_liq, "ml")
    assert vis_liq == 4000
    assert unidad_liq == "l"

    # 1 unidad a $800 -> $800/unidad
    cant_u = calcular_cantidad_base(Decimal("1"), "unidad", "unidad")
    pb_u = calcular_precio_por_base(800, cant_u)
    vis_u, unidad_u = calcular_precio_visualizacion(pb_u, "unidad")
    assert vis_u == 800
    assert unidad_u == "unidad"


@given(
    precio=st.integers(min_value=100, max_value=2_000_000),
    cant_base=st.decimals(
        min_value=Decimal("10"),
        max_value=Decimal("50000"),
        places=3,
    ),
    factor_escala=st.integers(min_value=1, max_value=20),
)
def test_propiedad_invariancia_por_escala(
    precio: int, cant_base: Decimal, factor_escala: int
) -> None:
    """Demuestra que multiplicar precio y cantidad por k preserva precio_por_base."""
    precio_escalado = precio * factor_escala
    cant_escalada = (cant_base * Decimal(factor_escala)).quantize(Decimal("0.001"))

    pb_original = calcular_precio_por_base(precio, cant_base)
    pb_escalado = calcular_precio_por_base(precio_escalado, cant_escalada)

    # La diferencia debida a redondeo en Decimal(0.000001) es como máximo 0.000002
    assert abs(pb_original - pb_escalado) <= Decimal("0.000002")
