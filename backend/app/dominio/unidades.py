"""Módulo puro de conversión y normalización de unidades de medida (Sección 5.1).

Reglas innegociables:
- Cero I/O, cero acceso a base de datos o llamadas de red.
- Aritmética exacta obligatoria con Decimal (prohibido float).
- Factores exactos de conversión colombianos (1 libra = 500 g).
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

# Factores exactos hacia la unidad_base ('g', 'ml', 'unidad')
FACTORES_CONVERSION: Final[dict[tuple[str, str], Decimal]] = {
    ("g", "g"): Decimal("1"),
    ("kg", "g"): Decimal("1000"),
    ("lb", "g"): Decimal("500"),
    ("ml", "ml"): Decimal("1"),
    ("l", "ml"): Decimal("1000"),
    ("unidad", "unidad"): Decimal("1"),
    ("docena", "unidad"): Decimal("12"),
}

MAPA_UNIDADES_CANONICAS: Final[dict[str, tuple[str, str]]] = {
    "g": ("g", "g"),
    "gr": ("g", "g"),
    "gramo": ("g", "g"),
    "gramos": ("g", "g"),
    "kg": ("kg", "g"),
    "kilo": ("kg", "g"),
    "kilos": ("kg", "g"),
    "kilogramo": ("kg", "g"),
    "kilogramos": ("kg", "g"),
    "lb": ("lb", "g"),
    "libra": ("lb", "g"),
    "libras": ("lb", "g"),
    "ml": ("ml", "ml"),
    "cc": ("ml", "ml"),
    "mililitro": ("ml", "ml"),
    "mililitros": ("ml", "ml"),
    "l": ("l", "ml"),
    "lt": ("l", "ml"),
    "litro": ("l", "ml"),
    "litros": ("l", "ml"),
    "unidad": ("unidad", "unidad"),
    "unidades": ("unidad", "unidad"),
    "und": ("unidad", "unidad"),
    "u": ("unidad", "unidad"),
    "docena": ("docena", "unidad"),
    "docenas": ("docena", "unidad"),
}


class ErrorUnidadesIncompatibles(ValueError):
    """Excepción lanzada cuando una unidad de entrada no corresponde a la unidad base."""

    def __init__(self, unidad_entrada: str, unidad_base: str) -> None:
        super().__init__(
            f"La unidad '{unidad_entrada}' es incompatible con la unidad base '{unidad_base}'."
        )
        self.unidad_entrada = unidad_entrada
        self.unidad_base = unidad_base


@dataclass(frozen=True)
class CantidadParseada:
    """Resultado inmutable del análisis de cantidad en texto libre."""

    valor_cantidad: Decimal
    unidad: str
    multiplicador: int
    cantidad_base: Decimal


def calcular_cantidad_base(
    valor_cantidad: Decimal,
    unidad: str,
    unidad_base: str,
    multiplicador: int = 1,
) -> Decimal:
    """Calcula la cantidad base normalizada con redondeo a 3 decimales."""
    clave = (unidad.lower(), unidad_base.lower())
    if clave not in FACTORES_CONVERSION:
        raise ErrorUnidadesIncompatibles(unidad, unidad_base)

    if multiplicador < 1:
        raise ValueError("El multiplicador debe ser mayor o igual a 1.")

    factor = FACTORES_CONVERSION[clave]
    total = valor_cantidad * factor * Decimal(multiplicador)
    return total.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def calcular_precio_por_base(precio_cop: int, cantidad_base: Decimal) -> Decimal:
    """Calcula el costo por unidad base con 6 decimales de precisión."""
    if precio_cop <= 0:
        raise ValueError("El precio en COP debe ser estrictamente mayor a 0.")
    if cantidad_base <= 0:
        raise ValueError("La cantidad base debe ser estrictamente mayor a 0.")

    return (Decimal(precio_cop) / cantidad_base).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


def calcular_precio_visualizacion(precio_por_base: Decimal, unidad_base: str) -> tuple[int, str]:
    """Calcula el precio comercial legible (por kg, litro o unidad) para la interfaz."""
    u_base = unidad_base.lower()
    if u_base == "g":
        # Multiplica por 1000 para expresar precio por kilogramo
        precio_kg = (precio_por_base * Decimal("1000")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return int(precio_kg), "kg"

    if u_base == "ml":
        # Multiplica por 1000 para expresar precio por litro
        precio_litro = (precio_por_base * Decimal("1000")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return int(precio_litro), "l"

    if u_base == "unidad":
        precio_u = precio_por_base.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(precio_u), "unidad"

    raise ErrorUnidadesIncompatibles(u_base, u_base)


def parsear_cantidad(texto: str) -> CantidadParseada | None:
    """Analiza expresiones en lenguaje natural y extrae la cantidad canónica."""
    if not texto:
        return None

    limpio = texto.strip().lower().replace("½", "1/2").replace("una ", "1 ").replace("un ", "1 ")

    # Caso especial: "medio kilo", "media libra", "medio litro"
    if "medio kilo" in limpio:
        return CantidadParseada(
            valor_cantidad=Decimal("0.5"),
            unidad="kg",
            multiplicador=1,
            cantidad_base=Decimal("500.000"),
        )
    if "media libra" in limpio:
        return CantidadParseada(
            valor_cantidad=Decimal("0.5"),
            unidad="lb",
            multiplicador=1,
            cantidad_base=Decimal("250.000"),
        )
    if "medio litro" in limpio:
        return CantidadParseada(
            valor_cantidad=Decimal("0.5"),
            unidad="l",
            multiplicador=1,
            cantidad_base=Decimal("500.000"),
        )
    if limpio in ("docena", "1 docena"):
        return CantidadParseada(
            valor_cantidad=Decimal("1"),
            unidad="docena",
            multiplicador=1,
            cantidad_base=Decimal("12.000"),
        )

    # Patrón 1: Multipacks formato "x6 330ml"
    patron_multi_prefijo = re.match(r"^x(\d+)\s+(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)$", limpio)
    if patron_multi_prefijo:
        mult = int(patron_multi_prefijo.group(1))
        val_str = patron_multi_prefijo.group(2).replace(",", ".")
        uni_raw = patron_multi_prefijo.group(3)
        return _construir_cantidad(Decimal(val_str), uni_raw, mult)

    # Patrón 2: Multipacks formato "6 x 330 ml" o "6x330ml"
    patron_multi_infijo = re.match(r"^(\d+)\s*[xX*]\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)$", limpio)
    if patron_multi_infijo:
        mult = int(patron_multi_infijo.group(1))
        val_str = patron_multi_infijo.group(2).replace(",", ".")
        uni_raw = patron_multi_infijo.group(3)
        return _construir_cantidad(Decimal(val_str), uni_raw, mult)

    # Patrón 3: Fracciones numéricas tipo "1/2 kg"
    patron_fraccion = re.match(r"^(\d+)\s*/\s*(\d+)\s*([a-zA-Z]+)$", limpio)
    if patron_fraccion:
        num = Decimal(patron_fraccion.group(1))
        den = Decimal(patron_fraccion.group(2))
        if den == 0:
            return None
        uni_raw = patron_fraccion.group(3)
        return _construir_cantidad(num / den, uni_raw, 1)

    # Patrón 4: Formato estándar "500 g", "1.5 L", "1 lb"
    patron_estandar = re.match(r"^(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)$", limpio)
    if patron_estandar:
        val_str = patron_estandar.group(1).replace(",", ".")
        uni_raw = patron_estandar.group(2)
        return _construir_cantidad(Decimal(val_str), uni_raw, 1)

    return None


def _construir_cantidad(
    valor: Decimal, unidad_raw: str, multiplicador: int
) -> CantidadParseada | None:
    """Asocia la unidad canónica y calcula la cantidad base correspondiente."""
    if unidad_raw not in MAPA_UNIDADES_CANONICAS:
        return None

    unidad_canon, u_base = MAPA_UNIDADES_CANONICAS[unidad_raw]
    cant_base = calcular_cantidad_base(valor, unidad_canon, u_base, multiplicador)
    return CantidadParseada(
        valor_cantidad=valor,
        unidad=unidad_canon,
        multiplicador=multiplicador,
        cantidad_base=cant_base,
    )
