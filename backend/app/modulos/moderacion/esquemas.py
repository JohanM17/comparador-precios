"""Esquemas Pydantic para el modulo de moderacion y sugerencias."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PATRON_UNIDADES_ENTRADA = r"^(g|kg|lb|ml|l|unidad|docena)$"
PATRON_CODIGO_BARRAS = r"^[0-9]{8,14}$"
PATRON_TIPOS_ESTABLECIMIENTO = r"^(tienda_barrio|minimercado|supermercado|cadena)$"


class ProductoCrearEntrada(BaseModel):
    """Entrada para crear un nuevo producto en el catalogo."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=2, max_length=120)
    categoria_id: int = Field(ge=1, le=10)
    unidad_base: str = Field(pattern="^(g|ml|unidad)$")
    imagen_url: str | None = Field(default=None, max_length=500)


class ProductoActualizarEntrada(BaseModel):
    """Entrada para actualizar campos de un producto."""

    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    categoria_id: int | None = Field(default=None, ge=1, le=10)
    imagen_url: str | None = Field(default=None, max_length=500)
    activo: bool | None = None


class PresentacionCrearEntrada(BaseModel):
    """Entrada para crear una presentacion comercial calculando cantidad_base."""

    model_config = ConfigDict(extra="forbid")

    producto_id: UUID
    marca: str | None = Field(default=None, max_length=80)
    valor_cantidad: Decimal = Field(gt=Decimal("0"))
    unidad: str = Field(pattern=PATRON_UNIDADES_ENTRADA)
    multiplicador: int = Field(default=1, ge=1)
    codigo_barras: str | None = Field(default=None, pattern=PATRON_CODIGO_BARRAS)
    fuente_catalogo: str = Field(default="manual", pattern="^(manual|semilla|open_food_facts)$")


class PresentacionActualizarEntrada(BaseModel):
    """Entrada para actualizar una presentacion (prohibe alterar cantidad_base)."""

    model_config = ConfigDict(extra="forbid")

    marca: str | None = Field(default=None, max_length=80)
    activa: bool | None = None
    codigo_barras: str | None = Field(default=None, pattern=PATRON_CODIGO_BARRAS)
    valor_cantidad: Decimal | None = None
    cantidad_base: Decimal | None = None


class EstablecimientoCrearEntrada(BaseModel):
    """Entrada para alta de un establecimiento georreferenciado."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=2, max_length=120)
    tipo: str = Field(pattern=PATRON_TIPOS_ESTABLECIMIENTO)
    cadena: str | None = Field(default=None, max_length=80)
    direccion: str = Field(min_length=3, max_length=200)
    barrio: str | None = Field(default=None, max_length=80)
    municipio: str = Field(default="Armenia", max_length=80)
    departamento: str = Field(default="Quindío", max_length=80)
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    activo: bool = True


class EstablecimientoActualizarEntrada(BaseModel):
    """Entrada para modificar datos de un establecimiento."""

    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    tipo: str | None = Field(default=None, pattern=PATRON_TIPOS_ESTABLECIMIENTO)
    cadena: str | None = Field(default=None, max_length=80)
    direccion: str | None = Field(default=None, min_length=3, max_length=200)
    barrio: str | None = Field(default=None, max_length=80)
    lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    lng: float | None = Field(default=None, ge=-180.0, le=180.0)
    activo: bool | None = None
    estado_verificacion: str | None = Field(
        default=None, pattern="^(sin_dueno|pendiente|verificado)$"
    )


class SugerenciaPresentacionEntrada(BaseModel):
    """Entrada para reportar una sugerencia de nueva variante comercial."""

    model_config = ConfigDict(extra="forbid")

    producto_id: UUID
    texto_libre: str = Field(min_length=3, max_length=200)
    marca: str | None = Field(default=None, max_length=80)
    valor_cantidad: Decimal | None = Field(default=None, gt=Decimal("0"))
    unidad: str | None = Field(default=None, pattern=PATRON_UNIDADES_ENTRADA)
    codigo_barras: str | None = Field(default=None, pattern=PATRON_CODIGO_BARRAS)


class AprobarSugerenciaEntrada(BaseModel):
    """Datos para que el moderador apruebe e incorpore la sugerencia al catalogo."""

    model_config = ConfigDict(extra="forbid")

    marca: str | None = Field(default=None, max_length=80)
    valor_cantidad: Decimal = Field(gt=Decimal("0"))
    unidad: str = Field(pattern=PATRON_UNIDADES_ENTRADA)
    multiplicador: int = Field(default=1, ge=1)
    codigo_barras: str | None = Field(default=None, pattern=PATRON_CODIGO_BARRAS)


class RechazarSugerenciaEntrada(BaseModel):
    """Motivo de rechazo de una sugerencia de presentacion."""

    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(min_length=5, max_length=500)


class ConsultaCatalogoExternoRespuesta(BaseModel):
    """Resultado de consultar un codigo de barras en fuentes externas."""

    model_config = ConfigDict(extra="forbid")

    encontrado: bool
    producto: dict[str, Any] | None = None
