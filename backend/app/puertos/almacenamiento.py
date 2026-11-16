"""Puerto abstracto para gestion de fotos de prueba y almacenamiento seguro."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class UrlSubidaFirmada:
    """Informacion para que el cliente suba directamente el archivo al bucket."""

    ruta: str
    url_firmada: str
    expira_en_segundos: int


class PuertoAlmacenamientoFotos(Protocol):
    """Protocolo de almacenamiento seguro de fotos de evidencia."""

    async def generar_url_subida(
        self,
        usuario_id: UUID,
        nombre_archivo: str,
        tipo_mime: str,
        tamano_bytes: int,
    ) -> UrlSubidaFirmada:
        """Genera una URL firmada de subida temporal con validaciones de tipo y tamano."""
        ...

    async def eliminar_fotos(self, rutas: list[str]) -> int:
        """Elimina de forma permanente una lista de rutas de fotos del bucket."""
        ...
