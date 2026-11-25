"""Configuracion base de OpenTelemetry para trazas, metricas y logs (Tarea T-103).

Este modulo no instrumenta FastAPI ni los servicios de negocio; solo deja el SDK
configurado, la sanitizacion de atributos y la degradacion segura. La
instrumentacion de los flujos se realiza en T-120.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from importlib import metadata
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import Meter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)
from opentelemetry.trace import Tracer

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
        "huella_red",
        "foto_prueba_path",
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
    `authorization`, `cookie`, `password`, `token` o `secret`.
    """
    resultado: dict[str, Any] = {}
    for clave, valor in atributos.items():
        clave_normalizada = str(clave).lower()
        if clave_normalizada in _CLAVES_PROHIBIDAS:
            continue
        if any(fragmento in clave_normalizada for fragmento in _FRAGMENTOS_PROHIBIDOS):
            continue
        resultado[clave] = _sanitizar_valor(valor)
    return resultado


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

    T-120 puede envolver este sampler para muestrear los errores al 100 % sin
    alterar la configuracion base de exitos.
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


def configurar_telemetria(config: Configuracion) -> None:
    """Inicializa trazas, metricas y logs de OpenTelemetry sin afectar la API.

    `OTEL_EXPORTER_OTLP_ENDPOINT` es una URL base: a cada exportador se le
    agrega la ruta de su senal (`/v1/traces`, `/v1/metrics`, `/v1/logs`).
    Si la telemetria esta deshabilitada o no hay endpoint OTLP, la funcion
    retorna sin excepcion. Cualquier fallo de inicializacion se registra como
    advertencia generica y la aplicacion continua operativa.
    """
    global _telemetria_activa
    _telemetria_activa = False

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
            sampler=resolver_sampler(config),
        )
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{base}/v1/traces", headers=headers))
        )

        lectores_metricas: list[PeriodicExportingMetricReader] = []
        if config.OTEL_METRICS_EXPORTER.strip().lower() == "otlp":
            lectores_metricas.append(
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=f"{base}/v1/metrics", headers=headers)
                )
            )
        meter_provider = MeterProvider(resource=resource, metric_readers=lectores_metricas)

        logger_provider = LoggerProvider(resource=resource)
        if config.OTEL_LOGS_EXPORTER.strip().lower() == "otlp":
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(
                    OTLPLogExporter(endpoint=f"{base}/v1/logs", headers=headers)
                )
            )

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


def telemetria_activa() -> bool:
    """Indica si la telemetria quedo inicializada correctamente."""
    return _telemetria_activa


def obtener_tracer(nombre: str) -> Tracer:
    """Obtiene un tracer del proveedor global para instrumentar un modulo."""
    return trace.get_tracer(nombre)


def obtener_meter(nombre: str) -> Meter:
    """Obtiene un meter del proveedor global para registrar metricas."""
    return metrics.get_meter(nombre)
