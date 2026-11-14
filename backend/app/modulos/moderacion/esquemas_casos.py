"""Esquemas Pydantic para casos de moderacion, sanciones, auditoria y parametros."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CrearSancionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: Literal["advertencia", "suspension", "bloqueo"]
    motivo: str = Field(min_length=5, max_length=500)
    dias_suspension: int | None = Field(default=None, ge=1, le=365)


class ResolverCasoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["confirmar", "descartar", "sancionar"]
    nota: str = Field(min_length=3, max_length=1000)
    sancion: CrearSancionEntrada | None = None


class SancionDirectaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario_id: UUID
    tipo: Literal["advertencia", "suspension", "bloqueo"]
    motivo: str = Field(min_length=5, max_length=500)
    dias_suspension: int | None = Field(default=None, ge=1, le=365)


class ApelacionSancionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    apelacion: str = Field(min_length=5, max_length=1000)


class ResolverApelacionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aprobar: bool
    nota: str | None = Field(default=None, max_length=1000)


class CasoDetalleRespuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tipo: str
    referencia_tabla: str
    referencia_id: UUID | None
    detalle: dict[str, Any]
    prioridad: int
    estado: str
    decision: str | None
    moderador_id: UUID | None
    nota: str | None
    creado_en: datetime
    resuelto_en: datetime | None
    referencia_datos: dict[str, Any] | None = None


class ListaCasosRespuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    datos: list[CasoDetalleRespuesta]
    total: int


class UsuarioModeracionRespuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    alias: str
    rol: str
    estado: str
    suspendida_hasta: datetime | None
    reputacion: float
    reportes_corroborados: int
    reportes_malos_confirmados: int
    creado_en: datetime
    sanciones: list[dict[str, Any]]
    conteo_reportes: dict[str, int]


class ItemAuditoriaRespuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    actor_id: UUID | None
    rol: str | None
    accion: str
    entidad: str
    entidad_id: str | None
    antes: dict[str, Any] | None
    despues: dict[str, Any] | None
    creado_en: datetime


class ListaAuditoriaRespuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    datos: list[ItemAuditoriaRespuesta]
    total: int


class ParametroItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clave: str
    valor: Any
    descripcion: str
    tipo: str
    rango_valido: str
    actualizado_en: datetime


class ListaParametrosRespuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    datos: list[ParametroItem]


class ActualizarParametrosEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parametros: dict[str, Any]
