"""Reglas de las promociones comerciales (FR-024, FR-025, ADR-022).

Modulo de dominio puro. Resuelve dos cosas y ninguna mas:

1. Si una promocion se puede publicar. La Ley 1480 de 2011, articulo 33, exige que toda
   promocion informe sus condiciones y su duracion. Aqui eso se traduce en reglas concretas
   y comprobables, no en un parrafo de buena voluntad.
2. Cuanto ahorra, a titulo informativo. El ahorro nunca entra en el total de la comparacion
   ni en su orden: eso lo prohibe ADR-022, porque publicar promociones es una accion que
   solo puede ejecutar un comercio y no puede comprar posiciones.

Cuando el ahorro depende de cuantas unidades compre el usuario, dato que la plataforma no
tiene, se declara el supuesto y se marca como estimacion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

TIPOS_VALIDOS = ("porcentaje", "precio_especial", "pague_x_lleve_y")

CONDICIONES_MIN = 10
CONDICIONES_MAX = 500
PORCENTAJE_MIN = 1
PORCENTAJE_MAX = 90


@dataclass(frozen=True)
class ReglaPromocion:
    """Promocion tal como el comercio la declara, antes de confiar en ella."""

    tipo: str
    porcentaje_descuento: int | None
    precio_especial_cop: int | None
    pague_x: int | None
    lleve_y: int | None
    condiciones: str
    vigente_desde: datetime
    vigente_hasta: datetime | None
    hasta_revocar: bool


@dataclass(frozen=True)
class AhorroEstimado:
    """Ahorro informativo de una promocion. No participa del total ni del orden."""

    ahorro_cop: int
    unidades_supuestas: int
    es_estimacion: bool


def _validar_condiciones(regla: ReglaPromocion) -> list[str]:
    texto = regla.condiciones.strip()
    if len(texto) < CONDICIONES_MIN:
        return [
            "Las condiciones deben informar tiempo, modo y lugar "
            f"(minimo {CONDICIONES_MIN} caracteres)."
        ]
    if len(texto) > CONDICIONES_MAX:
        return [f"Las condiciones no pueden exceder {CONDICIONES_MAX} caracteres."]
    return []


def _validar_vigencia(regla: ReglaPromocion) -> list[str]:
    motivos: list[str] = []
    tiene_fin = regla.vigente_hasta is not None

    if tiene_fin == regla.hasta_revocar:
        motivos.append(
            "La vigencia debe declarar una fecha final o marcarse como vigente hasta revocar, "
            "pero no las dos ni ninguna."
        )
    if regla.vigente_hasta is not None and regla.vigente_hasta <= regla.vigente_desde:
        motivos.append("La fecha final debe ser posterior a la inicial.")
    return motivos


def _validar_campos_por_tipo(regla: ReglaPromocion) -> list[str]:
    """Cada tipo exige sus campos y prohibe los ajenos: el tipo y los datos no pueden mentir."""
    if regla.tipo not in TIPOS_VALIDOS:
        return [f"Tipo de promocion desconocido: {regla.tipo}."]

    esperados = {
        "porcentaje": ("porcentaje_descuento",),
        "precio_especial": ("precio_especial_cop",),
        "pague_x_lleve_y": ("pague_x", "lleve_y"),
    }[regla.tipo]
    todos = ("porcentaje_descuento", "precio_especial_cop", "pague_x", "lleve_y")

    motivos: list[str] = []
    for campo in todos:
        valor = getattr(regla, campo)
        if campo in esperados and valor is None:
            motivos.append(f"El tipo {regla.tipo} exige el campo {campo}.")
        if campo not in esperados and valor is not None:
            motivos.append(f"El tipo {regla.tipo} no admite el campo {campo}.")
    return motivos


def _validar_valores(regla: ReglaPromocion) -> list[str]:
    motivos: list[str] = []

    if regla.porcentaje_descuento is not None and not (
        PORCENTAJE_MIN <= regla.porcentaje_descuento <= PORCENTAJE_MAX
    ):
        motivos.append(
            f"El descuento debe estar entre {PORCENTAJE_MIN} y {PORCENTAJE_MAX} por ciento."
        )
    if regla.precio_especial_cop is not None and regla.precio_especial_cop <= 0:
        motivos.append("El precio especial debe ser mayor que cero.")
    if regla.pague_x is not None and regla.pague_x < 1:
        motivos.append("El numero de unidades pagadas debe ser al menos uno.")
    if regla.lleve_y is not None and regla.pague_x is not None and regla.lleve_y <= regla.pague_x:
        motivos.append("La promocion debe permitir llevar mas unidades de las que se pagan.")
    return motivos


def validar_promocion(regla: ReglaPromocion) -> list[str]:
    """Motivos por los que la promocion no se puede publicar. Lista vacia: se puede."""
    return [
        *_validar_condiciones(regla),
        *_validar_vigencia(regla),
        *_validar_campos_por_tipo(regla),
        *_validar_valores(regla),
    ]


def esta_vigente(regla: ReglaPromocion, ahora: datetime) -> bool:
    """Indica si la promocion esta dentro de su ventana de vigencia declarada."""
    if ahora < regla.vigente_desde:
        return False
    if regla.vigente_hasta is not None and ahora > regla.vigente_hasta:
        return False
    return True


def calcular_ahorro_informativo(
    regla: ReglaPromocion,
    precio_base_cop: int,
) -> AhorroEstimado | None:
    """Ahorro que la promocion representa frente al precio de gondola.

    Devuelve None cuando la promocion no es valida o cuando no rebaja nada. El resultado es
    informativo: ADR-022 prohibe que participe del total de la canasta o del orden.
    """
    if validar_promocion(regla) or precio_base_cop <= 0:
        return None

    if regla.tipo == "porcentaje" and regla.porcentaje_descuento is not None:
        ahorro = precio_base_cop * regla.porcentaje_descuento // 100
        return AhorroEstimado(ahorro, 1, False) if ahorro > 0 else None

    if regla.tipo == "precio_especial" and regla.precio_especial_cop is not None:
        ahorro = precio_base_cop - regla.precio_especial_cop
        return AhorroEstimado(ahorro, 1, False) if ahorro > 0 else None

    if regla.tipo == "pague_x_lleve_y" and regla.pague_x is not None and regla.lleve_y is not None:
        # Se supone que el usuario lleva exactamente las unidades de la promocion. Es el
        # supuesto mas conservador y se declara en pantalla junto al valor.
        unidades = regla.lleve_y
        ahorro = (regla.lleve_y - regla.pague_x) * precio_base_cop
        return AhorroEstimado(ahorro, unidades, True) if ahorro > 0 else None

    return None
