"""Puerto abstracto para la gestion de cache de comparaciones de precios (T-25)."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class PuertoCache(Protocol):
    """Protocolo de cache para respuestas del comparador de precios."""

    async def obtener(
        self,
        producto_id: UUID | str,
        subllave: str,
    ) -> dict[str, Any] | None:
        """Obtiene una respuesta cacheada validando frescura (ahora - generado_en <= 60s)."""
        ...

    async def guardar(
        self,
        producto_id: UUID | str,
        subllave: str,
        datos: dict[str, Any],
        ttl_segundos: int = 60,
    ) -> None:
        """Almacena la respuesta en los niveles de cache activos."""
        ...

    async def invalidar_producto(self, producto_id: UUID | str) -> None:
        """Invalida inmediatamente el cache de un producto tras un nuevo reporte."""
        ...

    async def limpiar(self) -> None:
        """Limpia todo el cache en memoria y conexiones."""
        ...
