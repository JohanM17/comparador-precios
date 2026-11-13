"""Esquemas Pydantic para el modulo de catalogo."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoriaRespuesta(BaseModel):
    """Representacion de una categoria de producto."""

    model_config = ConfigDict(extra="forbid")

    id: int
    nombre: str
    padre_id: int | None = None
    orden: int = 0


class PresentacionResumen(BaseModel):
    """Detalle resumido de una presentacion comercial."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    producto_id: UUID | None = None
    etiqueta: str
    marca: str | None = None
    valor_cantidad: Decimal
    unidad: str
    multiplicador: int = 1
    cantidad_base: Decimal
    codigo_barras: str | None = None
    activa: bool = True


class ProductoResumen(BaseModel):
    """Resumen de un producto para listados y busqueda."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    nombre: str
    categoria_id: int
    unidad_base: str
    unidad_visualizacion: str
    imagen_url: str | None = None
    precio_desde_por_unidad_cop: int | None = None
    n_tiendas_con_precio: int = 0
    presentaciones: list[PresentacionResumen] = Field(default_factory=list)


class ListaProductosRespuesta(BaseModel):
    """Respuesta paginada del buscador de productos."""

    model_config = ConfigDict(extra="forbid")

    datos: list[ProductoResumen]
    siguiente_cursor: str | None = None
    total_estimado: int | None = None


class ProductoDetalleRespuesta(BaseModel):
    """Ficha tecnica completa de un producto con sus presentaciones."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    nombre: str
    categoria_id: int
    unidad_base: str
    unidad_visualizacion: str
    imagen_url: str | None = None
    activo: bool
    presentaciones: list[PresentacionResumen] = Field(default_factory=list)
