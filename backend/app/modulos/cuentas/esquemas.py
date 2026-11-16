"""Esquemas Pydantic para el modulo de cuentas y cumplimiento Ley 1581 de 2012."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PATRON_ALIAS = r"^[a-zA-Z0-9_.-]+$"


class PoliticaTratamientoRespuesta(BaseModel):
    """Informacion publica de la politica de tratamiento de datos personales."""

    model_config = ConfigDict(extra="forbid")

    version: str
    texto_completo: str
    finalidades: list[str]
    contacto_legal_email: str
    derechos_arco: list[str]


class AutorizacionEntrada(BaseModel):
    """Entrada para registrar el consentimiento previo e informado del titular."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=3, max_length=30, pattern=PATRON_ALIAS)
    version_politica: str = Field(min_length=1, max_length=20)
    acepta: bool


class AutorizacionRespuesta(BaseModel):
    """Confirmacion del registro de autorizacion de datos personales."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: UUID
    alias: str
    version_politica: str
    aceptada_en: datetime
    mensaje: str


class PerfilUsuarioRespuesta(BaseModel):
    """Datos del perfil y vigencia de autorizacion del usuario."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: UUID
    alias: str
    email: str | None = None
    rol: str
    estado: str
    reputacion: Decimal
    reportes_corroborados: int
    reportes_malos_confirmados: int
    autorizacion_vigente: dict[str, Any]
    creado_en: datetime


class ActualizarAliasEntrada(BaseModel):
    """Entrada para modificar el alias publico del usuario."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=3, max_length=30, pattern=PATRON_ALIAS)


class EliminarCuentaRespuesta(BaseModel):
    """Respuesta al ejercicio del derecho de supresion y anonimizacion."""

    model_config = ConfigDict(extra="forbid")

    mensaje: str
    usuario_id: UUID
    estado: str
