"""Esquemas Pydantic del modulo comercial (Etapa 2)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PATRON_TIPO_PROMOCION = r"^(porcentaje|precio_especial|pague_x_lleve_y)$"

LOTE_PRECIOS_MAX = 200


class ReclamoComercioEntrada(BaseModel):
    """Solicitud de un usuario para reclamar la titularidad de un establecimiento (D-09)."""

    model_config = ConfigDict(extra="forbid")

    establecimiento_id: UUID
    telefono_contacto: str = Field(min_length=7, max_length=30)
    mensaje: str = Field(min_length=5, max_length=500)


class ReclamoComercioRespuesta(BaseModel):
    """Acuse del reclamo, que queda en la cola de un moderador humano."""

    id: UUID
    establecimiento_id: UUID
    estado: str
    creado_en: datetime


class EstablecimientoComercioResumen(BaseModel):
    """Establecimiento verificado del comercio y el estado de sus precios oficiales."""

    id: UUID
    nombre: str
    tipo: str
    barrio: str | None
    direccion: str | None
    estado_verificacion: str
    n_precios_oficiales: int
    n_por_revalidar: int


class PrecioOficialEntrada(BaseModel):
    """Precio de gondola que el comercio publica para una presentacion."""

    model_config = ConfigDict(extra="forbid")

    presentacion_id: UUID
    precio_cop: int = Field(gt=0, le=2_000_000)


class PreciosLoteEntrada(BaseModel):
    """Lote de precios oficiales. El modo rapido manda entre 20 y 30 por vez."""

    model_config = ConfigDict(extra="forbid")

    precios: list[PrecioOficialEntrada] = Field(min_length=1, max_length=LOTE_PRECIOS_MAX)


class PrecioRechazado(BaseModel):
    """Precio que no se pudo publicar, con el motivo en lenguaje llano."""

    presentacion_id: UUID
    motivo: str


class PreciosLoteRespuesta(BaseModel):
    """Resultado del lote: lo que entro y lo que no, sin ocultar lo segundo."""

    actualizados: int
    rechazados: list[PrecioRechazado]


class RevalidarRespuesta(BaseModel):
    """Resultado de la accion «Todo sigue igual» (D-06)."""

    revalidados: int
    revalidado_en: datetime


class PromocionEntrada(BaseModel):
    """Promocion que publica el comercio, sujeta al articulo 33 de la Ley 1480."""

    model_config = ConfigDict(extra="forbid")

    producto_id: UUID
    presentacion_id: UUID | None = None
    titulo: str = Field(min_length=5, max_length=120)
    tipo: str = Field(pattern=PATRON_TIPO_PROMOCION)
    porcentaje_descuento: int | None = Field(default=None, ge=1, le=90)
    precio_especial_cop: int | None = Field(default=None, gt=0)
    pague_x: int | None = Field(default=None, ge=1)
    lleve_y: int | None = Field(default=None, ge=2)
    condiciones: str = Field(min_length=10, max_length=500)
    vigente_desde: datetime
    vigente_hasta: datetime | None = None
    hasta_revocar: bool = False


class PromocionRespuesta(BaseModel):
    """Promocion publicada. Viaja siempre marcada como contenido comercial."""

    id: UUID
    establecimiento_id: UUID
    producto_id: UUID
    presentacion_id: UUID | None
    titulo: str
    tipo: str
    porcentaje_descuento: int | None
    precio_especial_cop: int | None
    pague_x: int | None
    lleve_y: int | None
    condiciones: str
    vigente_desde: datetime
    vigente_hasta: datetime | None
    hasta_revocar: bool
    activa: bool
    vigente: bool
    es_promocion: bool = True


class VerificarComercioEntrada(BaseModel):
    """Decision del moderador sobre un reclamo de titularidad."""

    model_config = ConfigDict(extra="forbid")

    aprobar: bool
    nota: str | None = Field(default=None, max_length=1000)


class VerificarComercioRespuesta(BaseModel):
    """Resultado de la verificacion de un comercio."""

    solicitud_id: UUID
    establecimiento_id: UUID
    estado: str
    comercio_id: UUID | None
