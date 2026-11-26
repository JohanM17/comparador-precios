"""Middleware de latencia artificial para el simulacro EC-11.

La espera solo se aplica fuera de produccion, con un valor positivo y sobre las
rutas configuradas. No registra peticiones, coordenadas, IPs ni datos
personales: su unico efecto es dormir antes de procesar la solicitud.
"""

from __future__ import annotations

import asyncio

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

RUTAS_POR_DEFECTO: tuple[str, ...] = ("/v1/",)


class LatenciaSimuladaMiddleware(BaseHTTPMiddleware):
    """Inyecta una espera controlada en entornos de prueba (Tarea T-123)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        milisegundos: int,
        entorno: str,
        rutas: tuple[str, ...] = RUTAS_POR_DEFECTO,
    ) -> None:
        super().__init__(app)
        self.milisegundos = max(0, milisegundos)
        self.entorno = entorno.strip().lower()
        self.rutas = tuple(rutas)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._debe_simular(request.url.path):
            await asyncio.sleep(self.milisegundos / 1000)
        return await call_next(request)

    def _debe_simular(self, ruta: str) -> bool:
        """Indica si la peticion debe esperar antes de llegar al endpoint."""
        if self.entorno == "production" or self.milisegundos <= 0:
            return False
        return any(_coincide_prefijo(ruta, prefijo) for prefijo in self.rutas)


def _coincide_prefijo(ruta: str, prefijo: str) -> bool:
    """Compara por segmentos para no confundir `/v1/productos` con `/v1/productos-x`."""
    base = prefijo.rstrip("/")
    if not base:
        return False
    return ruta == base or ruta.startswith(f"{base}/")
