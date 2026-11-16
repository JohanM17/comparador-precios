"""Esquemas Pydantic para el modulo de establecimientos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EstablecimientoResumen(BaseModel):
    """Resumen de informacion publica de un establecimiento."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    nombre: str
    tipo: str
    cadena: str | None = None
    direccion: str
    barrio: str | None = None
    municipio: str
    departamento: str
    lat: float
    lng: float
    distancia_m: int | None = None
    estado_verificacion: str
    activo: bool = True


class ListaEstablecimientosRespuesta(BaseModel):
    """Listado paginado de establecimientos comerciales."""

    model_config = ConfigDict(extra="forbid")

    datos: list[EstablecimientoResumen]
    total: int


class PrecioVigenteResumen(BaseModel):
    """Resumen de un precio vigente en un establecimiento."""

    model_config = ConfigDict(extra="forbid")

    presentacion_id: UUID
    producto_id: UUID
    producto_nombre: str
    presentacion_etiqueta: str
    precio_cop: int
    precio_por_base: Decimal
    sello: str
    motivo_sello: str | None = None
    ultimo_reporte_en: datetime


class EstablecimientoDetalleRespuesta(BaseModel):
    """Ficha completa de un establecimiento con sus precios vigentes."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    nombre: str
    tipo: str
    cadena: str | None = None
    direccion: str
    barrio: str | None = None
    municipio: str
    departamento: str
    lat: float
    lng: float
    distancia_m: int | None = None
    estado_verificacion: str
    activo: bool
    precios_vigentes: list[PrecioVigenteResumen] = Field(default_factory=list)


class SolicitudCorreccionEntrada(BaseModel):
    """Formulario publico de solicitud de correccion de datos de tienda."""

    model_config = ConfigDict(extra="forbid")

    correo: str = Field(min_length=5, max_length=120)
    mensaje: str = Field(min_length=10, max_length=1000)
    sitio_web_trampa: str | None = Field(default=None, description="Honeypot antispam")


class SolicitudCorreccionRespuesta(BaseModel):
    """Respuesta tras procesar una solicitud de correccion."""

    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    estado: str
    mensaje: str
