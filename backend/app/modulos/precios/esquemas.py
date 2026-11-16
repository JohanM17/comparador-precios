"""Esquemas Pydantic para reportes de precios, historial y comparaciones (T-23 y T-26)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CrearReporteEntrada(BaseModel):
    """Cuerpo de solicitud para registrar un nuevo reporte de precio (Flujo F2)."""

    model_config = ConfigDict(extra="forbid")

    presentacion_id: UUID
    establecimiento_id: UUID
    precio_cop: int = Field(..., description="Precio total en pesos colombianos COP")
    observado_en: datetime
    foto_ruta: str | None = Field(default=None, max_length=300)


class DatosReporteRespuesta(BaseModel):
    """Detalle visible del reporte registrado."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    estado_visible: str = Field(..., description="'recibido' o 'en_revision'")
    mensaje: str


class CrearReporteRespuesta(BaseModel):
    """Respuesta HTTP para POST /v1/reportes."""

    model_config = ConfigDict(extra="forbid")

    datos: DatosReporteRespuesta


class ElementoReportePropio(BaseModel):
    """Fila en el historial de reportes del propio usuario."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    producto_nombre: str
    presentacion_etiqueta: str
    establecimiento_nombre: str
    precio_cop: int
    observado_en: datetime
    creado_en: datetime
    estado_visible: str


class MisReportesRespuesta(BaseModel):
    """Respuesta paginada para GET /v1/mis-reportes."""

    model_config = ConfigDict(extra="forbid")

    datos: list[ElementoReportePropio]
    total: int
    pagina: int
    limite: int


class EstablecimientoComparacion(BaseModel):
    """Detalle del comercio en una fila de comparacion."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    nombre: str
    tipo: str
    barrio: str | None = None
    direccion: str | None = None
    distancia_m: int | None = None


class PresentacionComparacion(BaseModel):
    """Detalle de presentacion de producto en comparacion."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    etiqueta: str
    marca: str | None = None
    cantidad_base: float


class ProductoComparacion(BaseModel):
    """Encabezado de producto comparado."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    nombre: str
    categoria_id: int
    unidad_base: str
    unidad_visualizacion: str
    presentaciones: list[PresentacionComparacion]


class PrecioUnidad(BaseModel):
    """Precio unitario normalizado para comparacion equitativa."""

    model_config = ConfigDict(extra="forbid")

    valor_cop: int
    por: str


class ItemResultadoComparacion(BaseModel):
    """Fila del comparador de precios (Bloque 1 o Bloque 2)."""

    model_config = ConfigDict(extra="forbid")

    establecimiento: EstablecimientoComparacion
    presentacion: PresentacionComparacion
    precio_cop: int
    precio_oficial_cop: int | None = None
    precio_por_unidad: PrecioUnidad
    sello: str
    motivo_sello: str | None = None
    n_reportes_validos: int
    n_fuentes: int
    ultimo_reporte_en: datetime
    con_foto_prueba: bool = False
    es_bloque_secundario: bool = False


class MetaComparacion(BaseModel):
    """Metadatos de ordenamiento, frescura y neutralidad comercial (EC-06)."""

    model_config = ConfigDict(extra="forbid")

    criterio_orden: str
    texto_neutralidad: str
    bloques: list[str]
    generado_en: str
    datos_de_demostracion: bool = False


class DatosComparacion(BaseModel):
    """Cuerpo de datos del comparador neutral."""

    model_config = ConfigDict(extra="forbid")

    producto: ProductoComparacion
    resultados: list[ItemResultadoComparacion]
    promociones: list[dict[str, Any]] = Field(default_factory=list)
    meta: MetaComparacion


class RespuestaComparacion(BaseModel):
    """Respuesta completa de GET /v1/productos/{id}/comparacion."""

    model_config = ConfigDict(extra="forbid")

    datos: DatosComparacion
