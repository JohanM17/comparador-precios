"""Configuracion de logging estructurado y privacidad de datos segun Ley 1581."""

from __future__ import annotations

import logging
import re
import time
import traceback
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
_PATRON_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PATRON_IPV6_LOCAL = re.compile(r"(?<![\w:])(?:\[::1\]|::1)(?![\w:])")
_PATRON_HUELLA_RED = re.compile(
    r"""["']?\bhuella_red\b["']?\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s&,;'"}\)]+)""",
    re.IGNORECASE,
)
_PATRON_HUELLA_HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", re.IGNORECASE)

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
    """Redacta correos, coordenadas, IP, huellas y tokens.

    Cubre las variantes percent-encoded de correos y coordenadas. Las
    direcciones IPv4 y el loopback IPv6 se sustituyen por `[REDACTADO_IP]`; las
    huellas de red etiquetadas o con 64 caracteres hexadecimales se sustituyen
    por `[REDACTADO_HUELLA]`.
    """
    if not texto:
        return texto
    redactado = _PATRON_EMAIL.sub("[REDACTADO_EMAIL]", texto)
    redactado = _PATRON_EMAIL_CODIFICADO.sub("[REDACTADO_EMAIL]", redactado)
    redactado = _PATRON_COORDENADAS.sub(r"\1=[REDACTADO_COORD]", redactado)
    redactado = _PATRON_COORDENADAS_CODIFICADAS.sub(r"\1%3D[REDACTADO_COORD]", redactado)
    redactado = _PATRON_BEARER.sub("Bearer [REDACTADO_TOKEN]", redactado)
    redactado = _PATRON_IPV4.sub("[REDACTADO_IP]", redactado)
    redactado = _PATRON_IPV6_LOCAL.sub("[REDACTADO_IP]", redactado)
    redactado = _PATRON_HUELLA_RED.sub("[REDACTADO_HUELLA]", redactado)
    redactado = _PATRON_HUELLA_HEX.sub("[REDACTADO_HUELLA]", redactado)
    return redactado


class FiltroPrivacidadLey1581(logging.Filter):
    """Filtro de logging que garantiza la no filtracion de datos personales.

    El mensaje se formatea antes de redactarlo para que la redaccion cubra
    tambien los argumentos y no deje placeholders sin reemplazar. Tambien
    redacta el traceback (`exc_info`/`exc_text`) y el `stack_info`.

    Contrato para handlers y logging estructurado futuro: despues del filtro
    `record.msg` contiene el mensaje final redactado, `record.args` queda vacio
    y `record.exc_text`/`record.stack_info` ya estan saneados. Los handlers deben
    formatear `%(message)s` y no depender de `record.args`.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            mensaje = record.getMessage()
        except Exception:  # Un registro mal formado nunca debe romper el logging
            mensaje = str(record.msg)
        record.msg = redactar_texto_sensible(mensaje)
        record.args = ()

        if record.exc_info:
            if record.exc_text:
                record.exc_text = redactar_texto_sensible(record.exc_text)
            else:
                try:
                    rastro = "".join(traceback.format_exception(*record.exc_info))
                except Exception:  # La redaccion nunca debe romper el logging
                    rastro = str(record.exc_info[1])
                record.exc_text = redactar_texto_sensible(rastro)
        elif record.exc_text:
            record.exc_text = redactar_texto_sensible(record.exc_text)

        if isinstance(record.stack_info, str):
            record.stack_info = redactar_texto_sensible(record.stack_info)
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
