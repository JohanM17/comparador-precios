"""Configuracion de logging estructurado y privacidad de datos segun Ley 1581."""

from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_PATRON_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_PATRON_EMAIL_CODIFICADO = re.compile(
    r"\b[a-zA-Z0-9._%+-]+%40[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", re.IGNORECASE
)
_PATRON_COORDENADAS = re.compile(r"(lat|lng|latitude|longitude)=[-+]?(\d*\.\d+|\d+)")
_PATRON_COORDENADAS_CODIFICADAS = re.compile(
    r"(lat|lng|latitude|longitude)%3D[-+]?(\d*\.\d+|\d+)", re.IGNORECASE
)
_PATRON_BEARER = re.compile(r"Bearer\s+[-a-z0-9._~+/]+=*", re.IGNORECASE)

FORMATO_LOG_CORRELACION = (
    "%(asctime)s %(levelname)s %(name)s [trace_id=%(trace_id)s span_id=%(span_id)s] %(message)s"
)


def _ids_traza_actuales() -> tuple[str, str]:
    """Devuelve `trace_id` y `span_id` del span actual, o cadenas vacias."""
    contexto = trace.get_current_span().get_span_context()
    if not contexto.is_valid:
        return "", ""
    return f"{contexto.trace_id:032x}", f"{contexto.span_id:016x}"


def redactar_texto_sensible(texto: str) -> str:
    """Redacta correos, coordenadas y tokens, incluidas variantes percent-encoded."""
    if not texto:
        return texto
    redactado = _PATRON_EMAIL.sub("[REDACTADO_EMAIL]", texto)
    redactado = _PATRON_EMAIL_CODIFICADO.sub("[REDACTADO_EMAIL]", redactado)
    redactado = _PATRON_COORDENADAS.sub(r"\1=[REDACTADO_COORD]", redactado)
    redactado = _PATRON_COORDENADAS_CODIFICADAS.sub(r"\1%3D[REDACTADO_COORD]", redactado)
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


class FiltroCorrelacionTrazas(logging.Filter):
    """Inyecta `trace_id` y `span_id` del span actual en cada registro de log.

    Fuera de un span valido los atributos quedan como cadenas vacias, de modo
    que los formateadores pueden referenciarlos sin errores.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        trace_id, span_id = _ids_traza_actuales()
        record.__dict__["trace_id"] = trace_id
        record.__dict__["span_id"] = span_id
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
        trace_id, span_id = _ids_traza_actuales()
        self.logger.info(
            "%s %s -> %d (%.2f ms) [req=%s] [trace=%s span=%s]",
            request.method,
            url_segura,
            response.status_code,
            duracion_ms,
            request_id,
            trace_id or "-",
            span_id or "-",
        )
        return response


def _agregar_filtro_si_falta(
    destino: logging.Logger | logging.Handler,
    filtro: logging.Filter,
) -> None:
    """Evita duplicar filtros cuando la configuracion se aplica varias veces."""
    if not any(isinstance(actual, type(filtro)) for actual in destino.filters):
        destino.addFilter(filtro)


def configurar_logging() -> None:
    """Inicializa el logging con privacidad y correlacion de trazas."""
    filtro_privacidad = FiltroPrivacidadLey1581()
    filtro_correlacion = FiltroCorrelacionTrazas()
    logger_raiz = logging.getLogger()
    logger_raiz.setLevel(logging.INFO)

    for handler in logger_raiz.handlers:
        _agregar_filtro_si_falta(handler, filtro_privacidad)
        _agregar_filtro_si_falta(handler, filtro_correlacion)
        if handler.formatter is None:
            handler.setFormatter(logging.Formatter(FORMATO_LOG_CORRELACION))

    logger_app = logging.getLogger("app")
    logger_app.setLevel(logging.INFO)
    _agregar_filtro_si_falta(logger_app, filtro_privacidad)
    _agregar_filtro_si_falta(logger_app, filtro_correlacion)

    logger_acceso = logging.getLogger("app.acceso")
    logger_acceso.setLevel(logging.INFO)
    _agregar_filtro_si_falta(logger_acceso, filtro_privacidad)
    _agregar_filtro_si_falta(logger_acceso, filtro_correlacion)

    _agregar_filtro_si_falta(logger_raiz, filtro_privacidad)
    _agregar_filtro_si_falta(logger_raiz, filtro_correlacion)
