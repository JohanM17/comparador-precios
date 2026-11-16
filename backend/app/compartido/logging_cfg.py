"""Configuracion de logging estructurado y privacidad de datos segun Ley 1581."""

from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_PATRON_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_PATRON_COORDENADAS = re.compile(r"(lat|lng|latitude|longitude)=[-+]?(\d*\.\d+|\d+)")
_PATRON_BEARER = re.compile(r"Bearer\s+[-a-z0-9._~+/]+=*", re.IGNORECASE)


def redactar_texto_sensible(texto: str) -> str:
    """Redacta correos, coordenadas lat/lng y tokens Bearer de cualquier cadena."""
    if not texto:
        return texto
    redactado = _PATRON_EMAIL.sub("[REDACTADO_EMAIL]", texto)
    redactado = _PATRON_COORDENADAS.sub(r"\1=[REDACTADO_COORD]", redactado)
    redactado = _PATRON_BEARER.sub("Bearer [REDACTADO_TOKEN]", redactado)
    return redactado


class FiltroPrivacidadLey1581(logging.Filter):
    """Filtro de logging que garantiza la no filtracion de coordenadas o emails."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redactar_texto_sensible(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (redactar_texto_sensible(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redactar_texto_sensible(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware que inyecta y propaga la cabecera X-Request-ID."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = f"req-{uuid4()}"

        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoggingAccesoMiddleware(BaseHTTPMiddleware):
    """Middleware para auditoria HTTP sin registrar datos sensibles."""

    logger = logging.getLogger("app.acceso")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inicio = time.perf_counter()
        request_id: str = getattr(request.state, "request_id", "req-desconocido")
        url_segura = redactar_texto_sensible(str(request.url))

        response = await call_next(request)

        duracion_ms = (time.perf_counter() - inicio) * 1000
        self.logger.info(
            "%s %s -> %d (%.2f ms) [req=%s]",
            request.method,
            url_segura,
            response.status_code,
            duracion_ms,
            request_id,
        )
        return response


def configurar_logging() -> None:
    """Inicializa la configuracion de logging aplicando el filtro de privacidad."""
    filtro = FiltroPrivacidadLey1581()
    logger_raiz = logging.getLogger()
    logger_raiz.setLevel(logging.INFO)

    for handler in logger_raiz.handlers:
        handler.addFilter(filtro)

    logger_app = logging.getLogger("app")
    logger_app.setLevel(logging.INFO)
    logger_app.addFilter(filtro)

    logger_acceso = logging.getLogger("app.acceso")
    logger_acceso.setLevel(logging.INFO)
    logger_acceso.addFilter(filtro)
