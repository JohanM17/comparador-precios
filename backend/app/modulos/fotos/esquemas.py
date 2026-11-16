"""Esquemas de validacion para solicitud y entrega de URLs firmadas de fotos."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

TAMANO_MAXIMO_FOTO_BYTES: int = 300 * 1024  # 300 KB segun foto.max_kb


class SolicitudUrlSubida(BaseModel):
    """Cuerpo de solicitud para obtener una URL firmada de subida a Storage."""

    model_config = ConfigDict(extra="forbid")

    nombre_archivo: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Nombre original o propuesto del archivo de imagen",
    )
    tipo_mime: str = Field(
        ...,
        pattern=r"^(image/jpeg|image/webp)$",
        description="Tipo MIME de la imagen (solo image/jpeg o image/webp)",
    )
    tamano_bytes: int = Field(
        ...,
        gt=0,
        le=TAMANO_MAXIMO_FOTO_BYTES,
        description="Tamano del archivo en bytes (maximo 300 KB)",
    )


class RespuestaUrlSubida(BaseModel):
    """Respuesta con la ruta asignada y la URL firmada temporal."""

    model_config = ConfigDict(extra="forbid")

    ruta: str = Field(..., description="Ruta de destino dentro del bucket pruebas")
    url_firmada: str = Field(..., description="URL con token de subida temporal")
    expira_en: int = Field(
        300,
        description="Tiempo de expiracion de la URL en segundos (5 minutos)",
    )
