"""Configuracion de OpenTelemetry para trazas, metricas y logs (Tareas T-103 y T-120).

La inicializacion aplica una politica de muestreo errores-primero: todos los
spans se crean y los errores se exportan siempre; los spans exitosos se exportan
con probabilidad `OTEL_TRACES_SAMPLER_ARG` (20 % por defecto). El apagado es
tolerante a fallos para que la observabilidad nunca tumbe la API.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from importlib import metadata
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import Meter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)
from opentelemetry.trace import Status, StatusCode, Tracer

from app.compartido.logging_cfg import redactar_texto_sensible
from app.config import Configuracion

_logger = logging.getLogger("app.telemetria")

_CLAVES_PROHIBIDAS = frozenset(
    {
        "lat",
        "lng",
        "latitude",
        "longitude",
        "reportante_id",
        "alias",
        "email",
        "ip",
        "client_ip",
        "ip_address",
        "net.peer.ip",
        "client.address",
        "huella_red",
        "foto_prueba_path",
        "body",
        "request.body",
        "response.body",
        "http.request.body",
        "http.response.body",
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "token",
        "secret",
    }
)

_FRAGMENTOS_PROHIBIDOS = (
    "authorization",
    "cookie",
    "password",
    "token",
    "secret",
)

_telemetria_activa = False
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_logger_provider: LoggerProvider | None = None

_MASCARA_TRACE_ID = (1 << 64) - 1
_ESCALA_TRACE_ID = float(1 << 64)


def _normalizar_ratio(valor: float) -> float:
    """Acota el ratio de exitos al rango [0, 1] y descarta valores no finitos."""
    if not math.isfinite(valor):
        return 0.0
    return min(max(valor, 0.0), 1.0)


class ProcesadorErroresPrimero(SpanProcessor):
    """Muestrea errores al 100 % y exitos segun `OTEL_TRACES_SAMPLER_ARG`.

    Envuelve al procesador real (normalmente un `BatchSpanProcessor`) y decide
    al cerrar el span. Los spans con estado `ERROR` o con una excepcion
    registrada se exportan siempre; el resto se exporta con probabilidad
    proporcional al ratio configurado. La decision se deriva del `trace_id`, de
    modo que todos los spans exitosos de una misma traza se conservan o se
    descartan juntos.
    """

    def __init__(self, procesador: SpanProcessor, ratio_exitos: float) -> None:
        self._procesador = procesador
        self._ratio_exitos = _normalizar_ratio(ratio_exitos)

    @property
    def ratio_exitos(self) -> float:
        """Ratio configurado para exportar spans exitosos."""
        return self._ratio_exitos

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        """Delega el inicio del span al procesador envuelto."""
        self._procesador.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        """Sanitiza el span y decide si se exporta sin propagar fallos."""
        try:
            _sanitizar_span(span)
            exportar = self._debe_exportar(span)
        except Exception as error:  # La observabilidad nunca debe tumbar la API
            _logger.warning(
                "Se descarta un span por fallo en la sanitizacion (%s)",
                type(error).__name__,
            )
            return
        if not exportar:
            return
        try:
            self._procesador.on_end(span)
        except Exception as error:  # La observabilidad nunca debe tumbar la API
            _logger.warning(
                "No fue posible exportar un span (%s)",
                type(error).__name__,
            )

    def shutdown(self) -> None:
        """Apaga el procesador envuelto."""
        self._procesador.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Fuerza el vaciado del procesador envuelto."""
        return self._procesador.force_flush(timeout_millis)

    def _debe_exportar(self, span: ReadableSpan) -> bool:
        if span.status.status_code == StatusCode.ERROR:
            return True
        if any(evento.name == "exception" for evento in span.events):
            return True
        return self._exito_muestreado(span.context.trace_id)

    def _exito_muestreado(self, trace_id: int) -> bool:
        if self._ratio_exitos <= 0.0:
            return False
        if self._ratio_exitos >= 1.0:
            return True
        proporcion = (trace_id & _MASCARA_TRACE_ID) / _ESCALA_TRACE_ID
        return proporcion < self._ratio_exitos


def parsear_headers_otlp(valor: str) -> dict[str, str]:
    """Convierte `clave=valor,clave2=valor2` en un diccionario de cabeceras.

    Los segmentos vacios o sin signo igual se ignoran. Se conserva cualquier
    signo igual adicional dentro del valor (por ejemplo `Authorization=Basic abc==`).
    El valor nunca se registra en logs.
    """
    headers: dict[str, str] = {}
    for segmento in valor.split(","):
        clave, separador, contenido = segmento.partition("=")
        clave = clave.strip()
        if not separador or not clave:
            continue
        headers[clave] = contenido.strip()
    return headers


def _sanitizar_valor(valor: Any) -> Any:
    """Sanitiza recursivamente un valor de atributo de telemetria."""
    if isinstance(valor, Mapping):
        return sanitizar_atributos(valor)
    if isinstance(valor, str):
        return redactar_texto_sensible(valor)
    if isinstance(valor, list):
        return [_sanitizar_valor(elemento) for elemento in valor]
    if isinstance(valor, tuple):
        return tuple(_sanitizar_valor(elemento) for elemento in valor)
    return valor


def sanitizar_atributos(atributos: Mapping[str, Any]) -> dict[str, Any]:
    """Devuelve una copia de los atributos sin claves prohibidas y sin PII.

    La comparacion de claves no distingue mayusculas. Ademas de las claves
    exactas de la lista de prohibidos, se rechaza cualquier clave que contenga
    `authorization`, `cookie`, `password`, `token` o `secret`, y cualquier clave
    que termine en `.body` (cuerpos de solicitud o respuesta).
    """
    resultado: dict[str, Any] = {}
    for clave, valor in atributos.items():
        clave_normalizada = str(clave).lower()
        if clave_normalizada in _CLAVES_PROHIBIDAS:
            continue
        if clave_normalizada.endswith(".body"):
            continue
        if any(fragmento in clave_normalizada for fragmento in _FRAGMENTOS_PROHIBIDOS):
            continue
        resultado[clave] = _sanitizar_valor(valor)
    return resultado


def _sanitizar_span(span: ReadableSpan) -> None:
    """Aplica la sanitizacion a atributos, eventos y estado de un span.

    La instrumentacion automatica de FastAPI puede capturar la URL completa con
    coordenadas en la cadena de consulta; los eventos de excepcion tambien
    pueden contener mensajes con datos personales. Este paso garantiza que
    ninguna PII llegue al colector.

    Se apoya en los campos privados de `ReadableSpan` del SDK de OpenTelemetry
    1.45.x (`_attributes`, `_events` y `_status`). `ProcesadorErroresPrimero`
    captura cualquier fallo y descarta el span, de modo que un cambio interno
    del SDK nunca afecta la peticion.
    """
    atributos = span._attributes
    if atributos:
        span._attributes = sanitizar_atributos(atributos)

    eventos_saneados: list[Event] = []
    for evento in span._events:
        atributos_evento = evento.attributes
        if atributos_evento:
            evento._attributes = sanitizar_atributos(atributos_evento)
        eventos_saneados.append(evento)
    span._events = tuple(eventos_saneados)

    descripcion = span.status.description
    if descripcion:
        span._status = Status(
            span.status.status_code,
            redactar_texto_sensible(descripcion),
        )


def _version_servicio() -> str:
    """Obtiene la version instalada del backend con un fallback seguro."""
    try:
        return metadata.version("comparador-precios-backend")
    except metadata.PackageNotFoundError:
        return "desconocida"


def _construir_resource(config: Configuracion) -> Resource:
    """Construye el recurso comun de trazas, metricas y logs."""
    return Resource.create(
        {
            "service.name": config.OTEL_SERVICE_NAME,
            "service.version": _version_servicio(),
            "deployment.environment": config.ENTORNO,
        }
    )


def resolver_sampler(config: Configuracion) -> Sampler:
    """Resuelve el sampler de trazas segun `OTEL_TRACES_SAMPLER`.

    Se conserva para configuraciones explicitas y pruebas. La inicializacion
    por defecto usa `resolver_sampler_errores_primero`, que muestrea todos los
    spans al crearlos para que el estado de error se conozca al cerrarlos.
    """
    nombre = config.OTEL_TRACES_SAMPLER.strip().lower()
    ratio = config.OTEL_TRACES_SAMPLER_ARG

    if nombre == "parentbased_traceidratio":
        return ParentBased(TraceIdRatioBased(ratio))
    if nombre == "traceidratio":
        return TraceIdRatioBased(ratio)
    if nombre == "always_on":
        return ALWAYS_ON
    if nombre == "always_off":
        return ALWAYS_OFF

    _logger.warning(
        "OTEL_TRACES_SAMPLER desconocido (%s); se usa parentbased_traceidratio",
        nombre,
    )
    return ParentBased(TraceIdRatioBased(ratio))


def resolver_sampler_errores_primero() -> Sampler:
    """Sampler de creacion para la politica errores-primero.

    `ALWAYS_ON` garantiza que ningun span se descarte antes de conocer si
    termino en error; la decision de exportar exitos se toma en
    `ProcesadorErroresPrimero` con `OTEL_TRACES_SAMPLER_ARG`.
    """
    return ALWAYS_ON


def configurar_telemetria(config: Configuracion) -> None:
    """Inicializa trazas, metricas y logs de OpenTelemetry sin afectar la API.

    `OTEL_EXPORTER_OTLP_ENDPOINT` es una URL base: a cada exportador se le
    agrega la ruta de su senal (`/v1/traces`, `/v1/metrics`, `/v1/logs`).
    La creacion de spans no muestrea (`ALWAYS_ON`); `ProcesadorErroresPrimero`
    exporta todos los errores y muestrea los exitos con
    `OTEL_TRACES_SAMPLER_ARG` (20 % por defecto).

    Si la telemetria esta deshabilitada o no hay endpoint OTLP, la funcion
    retorna sin excepcion. Cualquier fallo de inicializacion se registra como
    advertencia generica y la aplicacion continua operativa.
    """
    global _logger_provider, _meter_provider, _telemetria_activa, _tracer_provider
    _telemetria_activa = False
    _tracer_provider = None
    _meter_provider = None
    _logger_provider = None

    if config.OTEL_SDK_DISABLED:
        _logger.info("Telemetria deshabilitada por OTEL_SDK_DISABLED")
        return

    endpoint = config.OTEL_EXPORTER_OTLP_ENDPOINT.strip()
    if not endpoint:
        _logger.info("Telemetria inactiva: OTEL_EXPORTER_OTLP_ENDPOINT esta vacio")
        return

    try:
        resource = _construir_resource(config)
        headers = parsear_headers_otlp(config.OTEL_EXPORTER_OTLP_HEADERS)
        base = endpoint.rstrip("/")

        tracer_provider = TracerProvider(
            resource=resource,
            sampler=resolver_sampler_errores_primero(),
        )
        procesador_trazas = BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{base}/v1/traces", headers=headers)
        )
        tracer_provider.add_span_processor(
            ProcesadorErroresPrimero(
                procesador_trazas,
                ratio_exitos=config.OTEL_TRACES_SAMPLER_ARG,
            )
        )
        _tracer_provider = tracer_provider

        lectores_metricas: list[PeriodicExportingMetricReader] = []
        if config.OTEL_METRICS_EXPORTER.strip().lower() == "otlp":
            lectores_metricas.append(
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=f"{base}/v1/metrics", headers=headers)
                )
            )
        meter_provider = MeterProvider(resource=resource, metric_readers=lectores_metricas)
        _meter_provider = meter_provider

        logger_provider = LoggerProvider(resource=resource)
        if config.OTEL_LOGS_EXPORTER.strip().lower() == "otlp":
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(
                    OTLPLogExporter(endpoint=f"{base}/v1/logs", headers=headers)
                )
            )
        _logger_provider = logger_provider

        trace.set_tracer_provider(tracer_provider)
        metrics.set_meter_provider(meter_provider)
        set_logger_provider(logger_provider)
        _telemetria_activa = True
        _logger.info("Telemetria OpenTelemetry inicializada")
    except Exception as error:  # La observabilidad nunca debe tumbar la API
        _telemetria_activa = False
        _logger.warning(
            "No fue posible inicializar la telemetria (%s); la API continua operativa",
            type(error).__name__,
        )
        apagar_telemetria()


def _cerrar_provider(nombre: str, provider: Any) -> None:
    """Hace force_flush y shutdown de un provider sin propagar fallos."""
    if provider is None:
        return
    try:
        provider.force_flush()
    except Exception as error:  # El apagado nunca debe tumbar la API
        _logger.warning(
            "No fue posible vaciar la telemetria de %s (%s)", nombre, type(error).__name__
        )
    try:
        provider.shutdown()
    except Exception as error:  # El apagado nunca debe tumbar la API
        _logger.warning(
            "No fue posible apagar la telemetria de %s (%s)", nombre, type(error).__name__
        )


def apagar_telemetria() -> None:
    """Apaga ordenadamente los providers de trazas, metricas y logs.

    Es seguro llamarla varias veces o cuando la telemetria nunca se inicializo.
    Los errores de `force_flush` o `shutdown` se registran de forma generica y
    no se propagan.
    """
    global _logger_provider, _meter_provider, _telemetria_activa, _tracer_provider
    tracer_provider = _tracer_provider
    meter_provider = _meter_provider
    logger_provider = _logger_provider
    _tracer_provider = None
    _meter_provider = None
    _logger_provider = None
    _telemetria_activa = False

    _cerrar_provider("trazas", tracer_provider)
    _cerrar_provider("metricas", meter_provider)
    _cerrar_provider("logs", logger_provider)


def telemetria_activa() -> bool:
    """Indica si la telemetria quedo inicializada correctamente."""
    return _telemetria_activa


def obtener_tracer(nombre: str) -> Tracer:
    """Obtiene un tracer del proveedor global para instrumentar un modulo."""
    return trace.get_tracer(nombre)


def obtener_meter(nombre: str) -> Meter:
    """Obtiene un meter del proveedor global para registrar metricas."""
    return metrics.get_meter(nombre)
