"""Pruebas unitarias de la configuracion de telemetria (Tareas T-103, T-120 y T-124)."""

from __future__ import annotations

import io
import logging
import re
import sys
from collections.abc import Iterator, Mapping
from importlib import metadata
from typing import Any

import pytest
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode

from app.compartido import telemetria
from app.compartido.logging_cfg import (
    _NOMBRE_HANDLER_ADVERTENCIAS,
    FORMATO_LOG_CORRELACION,
    FiltroCorrelacionTrazas,
    FiltroPrivacidadLey1581,
    configurar_logging,
    redactar_texto_sensible,
)
from app.config import Configuracion
from app.modulos.precios.servicio import _normalizar_estado_telemetria


@pytest.fixture(autouse=True)
def reiniciar_estado_telemetria(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Aisla el estado global del modulo entre pruebas."""
    telemetria._quitar_handler_logs()
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    monkeypatch.setattr(telemetria, "_telemetria_activa", False)
    monkeypatch.setattr(telemetria, "_tracer_provider", None)
    monkeypatch.setattr(telemetria, "_meter_provider", None)
    monkeypatch.setattr(telemetria, "_logger_provider", None)
    try:
        yield
    finally:
        telemetria._quitar_handler_logs()


def _configuracion(**cambios: Any) -> Configuracion:
    """Construye una configuracion sin leer el archivo .env real."""
    return Configuracion(_env_file=None, **cambios)


@pytest.fixture
def estado_logging() -> Iterator[None]:
    """Deja `app` y los loggers de Uvicorn sin handlers y restaura su estado.

    Los handlers de la raiz se gestionan dentro de cada prueba: pytest instala
    y retira los suyos en cada fase. Los de `app` y de Uvicorn son propios de la
    aplicacion, asi que la fixture los retira al empezar y restaura los previos
    al terminar, junto con niveles, `disabled`, `propagate` y filtros.
    """
    logger_raiz = logging.getLogger()
    logger_app = logging.getLogger("app")
    logger_uvicorn = logging.getLogger("uvicorn")
    logger_uvicorn_error = logging.getLogger("uvicorn.error")
    loggers = (
        logger_raiz,
        logger_app,
        logging.getLogger("app.acceso"),
        logger_uvicorn,
        logger_uvicorn_error,
        logging.getLogger("uvicorn.access"),
    )
    estado_loggers = [
        (logger, logger.level, logger.disabled, logger.propagate, list(logger.filters))
        for logger in loggers
    ]
    handlers_app = list(logger_app.handlers)
    for handler in handlers_app:
        logger_app.removeHandler(handler)
    handlers_uvicorn = list(logger_uvicorn.handlers)
    for handler in handlers_uvicorn:
        logger_uvicorn.removeHandler(handler)
    handlers_uvicorn_error = list(logger_uvicorn_error.handlers)
    for handler in handlers_uvicorn_error:
        logger_uvicorn_error.removeHandler(handler)
    handlers_advertencias = [
        handler
        for handler in logger_raiz.handlers
        if getattr(handler, "_nombre_handler", None) == _NOMBRE_HANDLER_ADVERTENCIAS
    ]
    for handler in handlers_advertencias:
        logger_raiz.removeHandler(handler)

    try:
        yield
    finally:
        for handler in list(logger_app.handlers):
            logger_app.removeHandler(handler)
            if handler not in handlers_app:
                handler.close()
        for handler in list(logger_raiz.handlers):
            if getattr(handler, "_nombre_handler", None) != _NOMBRE_HANDLER_ADVERTENCIAS:
                continue
            logger_raiz.removeHandler(handler)
            if handler not in handlers_advertencias:
                handler.close()
        for handler in handlers_advertencias:
            logger_raiz.addHandler(handler)
        for handler in handlers_app:
            logger_app.addHandler(handler)
        for logger, handlers_previos in (
            (logger_uvicorn, handlers_uvicorn),
            (logger_uvicorn_error, handlers_uvicorn_error),
        ):
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                if handler not in handlers_previos:
                    handler.close()
            for handler in handlers_previos:
                logger.addHandler(handler)
        for logger, nivel, deshabilitado, propagar, filtros in estado_loggers:
            logger.setLevel(nivel)
            logger.disabled = deshabilitado
            logger.propagate = propagar
            logger.filters[:] = filtros


class _ExportadorFalso:
    """Exportador OTLP de prueba que solo registra sus argumentos."""

    def __init__(
        self,
        endpoint: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.headers = dict(headers or {})


class _ProcesadorFalso:
    """Procesador de prueba que conserva el exportador recibido."""

    def __init__(self, exportador: Any) -> None:
        self.exportador = exportador


class _ProveedorTrazasFalso:
    """Proveedor de trazas de prueba."""

    def __init__(self, resource: Any = None, sampler: Any = None) -> None:
        self.resource = resource
        self.sampler = sampler
        self.procesadores: list[Any] = []

    def add_span_processor(self, procesador: Any) -> None:
        self.procesadores.append(procesador)


class _ProveedorMetricasFalso:
    """Proveedor de metricas de prueba."""

    def __init__(self, resource: Any = None, metric_readers: Any = None) -> None:
        self.resource = resource
        self.lectores = list(metric_readers or [])


class _LoggerLogsFalso:
    """Logger OTel de prueba que conserva los registros emitidos."""

    def __init__(self) -> None:
        self.registros: list[Any] = []

    def emit(self, registro: Any) -> None:
        self.registros.append(registro)


class _ProveedorLogsFalso:
    """Proveedor de logs de prueba."""

    def __init__(self, resource: Any = None) -> None:
        self.resource = resource
        self.procesadores: list[Any] = []
        self.logger = _LoggerLogsFalso()

    def add_log_record_processor(self, procesador: Any) -> None:
        self.procesadores.append(procesador)

    def get_logger(
        self,
        instrumenting_module_name: str,
        instrumenting_library_version: str = "",
        schema_url: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> _LoggerLogsFalso:
        return self.logger


def _instalar_dobles_otel(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, list[_ExportadorFalso]], dict[str, Any]]:
    """Reemplaza exportadores, procesadores y providers por dobles de prueba."""
    creados: dict[str, list[_ExportadorFalso]] = {"trazas": [], "metricas": [], "logs": []}
    registrados: dict[str, Any] = {}

    def crear_exportador(nombre: str) -> Any:
        def fabricar(
            endpoint: str | None = None,
            headers: Mapping[str, str] | None = None,
        ) -> _ExportadorFalso:
            exportador = _ExportadorFalso(endpoint=endpoint, headers=headers)
            creados[nombre].append(exportador)
            return exportador

        return fabricar

    monkeypatch.setattr(telemetria, "OTLPSpanExporter", crear_exportador("trazas"))
    monkeypatch.setattr(telemetria, "OTLPMetricExporter", crear_exportador("metricas"))
    monkeypatch.setattr(telemetria, "OTLPLogExporter", crear_exportador("logs"))
    monkeypatch.setattr(telemetria, "BatchSpanProcessor", _ProcesadorFalso)
    monkeypatch.setattr(telemetria, "PeriodicExportingMetricReader", _ProcesadorFalso)
    monkeypatch.setattr(telemetria, "BatchLogRecordProcessor", _ProcesadorFalso)
    monkeypatch.setattr(telemetria, "TracerProvider", _ProveedorTrazasFalso)
    monkeypatch.setattr(telemetria, "MeterProvider", _ProveedorMetricasFalso)
    monkeypatch.setattr(telemetria, "LoggerProvider", _ProveedorLogsFalso)
    monkeypatch.setattr(
        telemetria.trace,
        "set_tracer_provider",
        lambda proveedor: registrados.__setitem__("trazas", proveedor),
    )
    monkeypatch.setattr(
        telemetria.metrics,
        "set_meter_provider",
        lambda proveedor: registrados.__setitem__("metricas", proveedor),
    )
    monkeypatch.setattr(
        telemetria,
        "set_logger_provider",
        lambda proveedor: registrados.__setitem__("logs", proveedor),
    )
    return creados, registrados


def test_sanitizar_atributos_elimina_prohibidas_y_conserva_permitidas() -> None:
    """Elimina claves prohibidas sin distinguir mayusculas y conserva el resto."""
    atributos: dict[str, Any] = {
        "lat": 4.53,
        "LATITUDE": 4.53,
        "Lng": -75.68,
        "longitude": -75.68,
        "reportante_id": "usuario-123",
        "Alias": "ana",
        "email": "ana@example.com",
        "IP": "192.168.1.10",
        "huella_red": "huella",
        "foto_prueba_path": "fotos/prueba.jpg",
        "authorization": "Bearer abc",
        "Cookie": "sesion=1",
        "Set-Cookie": "sesion=1",
        "password": "clave",
        "token": "token",
        "SECRET": "secreto",
        "ruta": "/v1/reportes",
        "metodo": "POST",
        "status_code": 201,
        "latencia_ms": 12.5,
    }

    resultado = telemetria.sanitizar_atributos(atributos)

    assert resultado == {
        "ruta": "/v1/reportes",
        "metodo": "POST",
        "status_code": 201,
        "latencia_ms": 12.5,
    }
    assert atributos["email"] == "ana@example.com"
    assert resultado is not atributos


def test_sanitizar_atributos_rechaza_fragmentos_sensibles_en_claves() -> None:
    """Rechaza claves compuestas que contienen fragmentos sensibles."""
    atributos = {
        "http.request.header.authorization": "Bearer abc",
        "user_token": "abc",
        "cookie_sesion": "abc",
        "mi_password": "abc",
        "client_secret": "abc",
        "ruta_segura": "/v1/salud",
    }

    resultado = telemetria.sanitizar_atributos(atributos)

    assert resultado == {"ruta_segura": "/v1/salud"}


def test_sanitizar_atributos_recursivo_redacta_pii_y_no_muta_la_entrada() -> None:
    """Sanitiza diccionarios anidados y redacta correos, coordenadas y Bearer."""
    atributos: dict[str, Any] = {
        "ruta": "/v1/reportes",
        "usuario": {
            "email": "ana@example.com",
            "alias": "ana",
            "nombre": "Ana",
            "ubicacion": "lat=4.53,lng=-75.68",
            "cabecera": "Bearer abc.def==",
        },
        "etiquetas": ["correo ana@example.com", {"token": "secreto", "visible": "ok"}],
    }

    resultado = telemetria.sanitizar_atributos(atributos)

    assert resultado == {
        "ruta": "/v1/reportes",
        "usuario": {
            "nombre": "Ana",
            "ubicacion": "lat=[REDACTADO_COORD],lng=[REDACTADO_COORD]",
            "cabecera": "Bearer [REDACTADO_TOKEN]",
        },
        "etiquetas": ["correo [REDACTADO_EMAIL]", {"visible": "ok"}],
    }
    assert atributos["usuario"]["email"] == "ana@example.com"
    assert atributos["usuario"]["alias"] == "ana"
    assert atributos["etiquetas"][1]["visible"] == "ok"
    assert resultado["etiquetas"][1] is not atributos["etiquetas"][1]
    assert resultado["usuario"] is not atributos["usuario"]


def test_sanitizar_atributos_redacta_ip_y_huella_en_valores() -> None:
    """La redaccion de valores cubre IP y huellas ademas de correos y coordenadas."""
    huella = "a" * 64

    resultado = telemetria.sanitizar_atributos(
        {"detalle": f"cliente 190.1.2.3 huella_red={huella}"}
    )

    assert resultado == {"detalle": "cliente [REDACTADO_IP] [REDACTADO_HUELLA]"}


def test_sanitizar_atributos_bloquea_telefono_y_mensaje_de_reclamo() -> None:
    """Los datos de contacto de un reclamo de comercio nunca se exportan."""
    atributos = {
        "telefono_contacto": "3001234567",
        "mensaje": "Soy el dueno, atiendo de 7 a 8.",
        "Telefono_Contacto": "3007654321",
        "detalle": {"mensaje": "Confirmar por telefono", "estado": "pendiente"},
        "ruta": "/v1/moderacion/comercios",
    }

    resultado = telemetria.sanitizar_atributos(atributos)

    assert resultado == {
        "detalle": {"estado": "pendiente"},
        "ruta": "/v1/moderacion/comercios",
    }


def test_parsear_headers_otlp_conserva_iguales_y_limpia_espacios() -> None:
    """Parsea cabeceras con valores que contienen iguales y segmentos vacios."""
    valor = "Authorization=Basic abc==, ,X-Entorno = pruebas,,sin-igual,=valor,Clave="

    resultado = telemetria.parsear_headers_otlp(valor)

    assert resultado == {
        "Authorization": "Basic abc==",
        "X-Entorno": "pruebas",
        "Clave": "",
    }


def test_parsear_headers_otlp_vacio_devuelve_diccionario_vacio() -> None:
    """Un valor vacio no produce cabeceras."""
    assert telemetria.parsear_headers_otlp("") == {}
    assert telemetria.parsear_headers_otlp(" , , ") == {}


def test_configurar_telemetria_deshabilitada_no_inicializa_exportadores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con OTEL_SDK_DISABLED=True no se construye ningun exportador."""
    llamadas: list[tuple[Any, ...]] = []

    def exportador_prohibido(*args: Any, **kwargs: Any) -> None:
        llamadas.append(args)
        raise RuntimeError("no deberia construirse")

    monkeypatch.setattr(telemetria, "OTLPSpanExporter", exportador_prohibido)
    monkeypatch.setattr(telemetria, "OTLPMetricExporter", exportador_prohibido)
    monkeypatch.setattr(telemetria, "OTLPLogExporter", exportador_prohibido)

    configuracion = _configuracion(
        OTEL_SDK_DISABLED=True,
        OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318",
    )

    telemetria.configurar_telemetria(configuracion)

    assert llamadas == []
    assert telemetria.telemetria_activa() is False
    assert telemetria._handler_logs is None


def test_configurar_telemetria_sin_endpoint_queda_inactiva(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin endpoint OTLP la telemetria queda inactiva en modo local."""
    llamadas: list[tuple[Any, ...]] = []

    def exportador_prohibido(*args: Any, **kwargs: Any) -> None:
        llamadas.append(args)
        raise RuntimeError("no deberia construirse")

    monkeypatch.setattr(telemetria, "OTLPSpanExporter", exportador_prohibido)

    configuracion = _configuracion(OTEL_EXPORTER_OTLP_ENDPOINT="   ")

    telemetria.configurar_telemetria(configuracion)

    assert llamadas == []
    assert telemetria.telemetria_activa() is False
    assert telemetria._handler_logs is None


def test_configurar_telemetria_falla_sin_propagrar_y_no_filtra_secretos(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Un exportador caido deja la API operativa y no registra secretos."""

    def exportador_roto(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("colector caido: Authorization=Basic super-secreto")

    monkeypatch.setattr(telemetria, "OTLPSpanExporter", exportador_roto)

    configuracion = _configuracion(
        OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318",
        OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic super-secreto",
    )

    with caplog.at_level(logging.WARNING, logger="app.telemetria"):
        telemetria.configurar_telemetria(configuracion)

    assert telemetria.telemetria_activa() is False
    assert "No fue posible inicializar la telemetria" in caplog.text
    assert "super-secreto" not in caplog.text
    assert "Authorization" not in caplog.text


@pytest.mark.parametrize(
    "endpoint",
    ["http://127.0.0.1:4318", "http://127.0.0.1:4318/"],
)
def test_configurar_telemetria_inicializa_trazas_metricas_y_logs(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    """Con endpoint base configura las rutas de senal de los tres providers."""
    creados, registrados = _instalar_dobles_otel(monkeypatch)
    configuracion = _configuracion(
        OTEL_SERVICE_NAME="comparador-pruebas",
        ENTORNO="pruebas",
        OTEL_EXPORTER_OTLP_ENDPOINT=endpoint,
        OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic abc==,X-Entorno=pruebas",
        OTEL_TRACES_SAMPLER="always_on",
        OTEL_METRICS_EXPORTER="otlp",
        OTEL_LOGS_EXPORTER="otlp",
    )

    telemetria.configurar_telemetria(configuracion)

    assert telemetria.telemetria_activa() is True
    assert len(creados["trazas"]) == 1
    assert len(creados["metricas"]) == 1
    assert len(creados["logs"]) == 1

    proveedor_trazas = registrados["trazas"]
    assert proveedor_trazas.resource.attributes["service.name"] == "comparador-pruebas"
    assert proveedor_trazas.resource.attributes["deployment.environment"] == "pruebas"
    assert proveedor_trazas.resource.attributes["service.version"] == metadata.version(
        "comparador-precios-backend"
    )
    assert proveedor_trazas.sampler is telemetria.ALWAYS_ON
    assert len(proveedor_trazas.procesadores) == 1
    procesador_trazas = proveedor_trazas.procesadores[0]
    assert isinstance(procesador_trazas, telemetria.ProcesadorErroresPrimero)
    assert procesador_trazas.ratio_exitos == pytest.approx(0.2)
    assert isinstance(procesador_trazas._procesador, _ProcesadorFalso)

    rutas_senal = {
        "trazas": "/v1/traces",
        "metricas": "/v1/metrics",
        "logs": "/v1/logs",
    }
    for nombre, ruta_senal in rutas_senal.items():
        assert creados[nombre][0].endpoint == f"http://127.0.0.1:4318{ruta_senal}"
        assert creados[nombre][0].headers == {
            "Authorization": "Basic abc==",
            "X-Entorno": "pruebas",
        }

    assert len(registrados["metricas"].lectores) == 1
    assert len(registrados["logs"].procesadores) == 1
    handler_logs = telemetria._handler_logs
    assert isinstance(handler_logs, LoggingHandler)
    assert handler_logs._logger_provider is registrados["logs"]


def test_configurar_telemetria_omite_metricas_y_logs_con_exportador_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con OTEL_*_EXPORTER=none solo se inicializan las trazas."""
    creados, registrados = _instalar_dobles_otel(monkeypatch)
    configuracion = _configuracion(
        OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318",
        OTEL_METRICS_EXPORTER="none",
        OTEL_LOGS_EXPORTER="none",
    )

    telemetria.configurar_telemetria(configuracion)

    assert telemetria.telemetria_activa() is True
    assert len(creados["trazas"]) == 1
    assert creados["metricas"] == []
    assert creados["logs"] == []

    assert registrados["metricas"].lectores == []
    assert registrados["logs"].procesadores == []
    assert telemetria._handler_logs is None


def test_resolver_sampler_parentbased_traceidratio() -> None:
    """El sampler por defecto envuelve un TraceIdRatioBased con el ratio dado."""
    configuracion = _configuracion(
        OTEL_TRACES_SAMPLER="parentbased_traceidratio",
        OTEL_TRACES_SAMPLER_ARG=0.35,
    )

    sampler = telemetria.resolver_sampler(configuracion)

    assert isinstance(sampler, telemetria.ParentBased)
    assert isinstance(sampler._root, telemetria.TraceIdRatioBased)
    assert sampler._root.rate == pytest.approx(0.35)


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("traceidratio", "traceidratio"),
        ("always_on", "always_on"),
        ("always_off", "always_off"),
    ],
)
def test_resolver_sampler_variantes(nombre: str, esperado: str) -> None:
    """Resuelve las variantes simples del sampler configurado."""
    configuracion = _configuracion(
        OTEL_TRACES_SAMPLER=nombre,
        OTEL_TRACES_SAMPLER_ARG=0.35,
    )

    sampler = telemetria.resolver_sampler(configuracion)

    if esperado == "traceidratio":
        assert isinstance(sampler, telemetria.TraceIdRatioBased)
        assert sampler.rate == pytest.approx(0.35)
    elif esperado == "always_on":
        assert sampler is telemetria.ALWAYS_ON
    else:
        assert sampler is telemetria.ALWAYS_OFF


def test_resolver_sampler_desconocido_advierte_y_usa_parentbased(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Un sampler desconocido advierte y cae en parentbased_traceidratio."""
    configuracion = _configuracion(
        OTEL_TRACES_SAMPLER="sampler-inventado",
        OTEL_TRACES_SAMPLER_ARG=0.5,
    )

    with caplog.at_level(logging.WARNING, logger="app.telemetria"):
        sampler = telemetria.resolver_sampler(configuracion)

    assert isinstance(sampler, telemetria.ParentBased)
    assert isinstance(sampler._root, telemetria.TraceIdRatioBased)
    assert sampler._root.rate == pytest.approx(0.5)
    assert "OTEL_TRACES_SAMPLER desconocido" in caplog.text


class _ProcesadorDestino:
    """Procesador de destino que conserva los spans que recibe."""

    def __init__(self) -> None:
        self.spans: list[Any] = []
        self.vaciado = False
        self.apagado = False

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        """Registra el inicio sin hacer nada."""

    def on_end(self, span: Any) -> None:
        """Conserva el span terminado."""
        self.spans.append(span)

    def shutdown(self) -> None:
        """Marca el procesador como apagado."""
        self.apagado = True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Marca el procesador como vaciado."""
        self.vaciado = True
        return True


def _emitir_span(
    proveedor: TracerProvider,
    nombre: str,
    *,
    error: bool = False,
    excepcion: bool = False,
) -> None:
    """Emite un span de prueba con el estado o la excepcion indicados."""
    tracer = proveedor.get_tracer("pruebas.telemetria")
    span = tracer.start_span(nombre)
    if error:
        span.set_status(StatusCode.ERROR, "fallo simulado")
    if excepcion:
        span.record_exception(RuntimeError("excepcion simulada"))
    span.end()


def test_procesador_errores_primero_exporta_errores_con_ratio_cero() -> None:
    """Con ratio 0.0 los errores y las excepciones se exportan, los exitos no."""
    destino = _ProcesadorDestino()
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    proveedor.add_span_processor(telemetria.ProcesadorErroresPrimero(destino, 0.0))

    try:
        _emitir_span(proveedor, "exito")
        _emitir_span(proveedor, "error", error=True)
        _emitir_span(proveedor, "excepcion", excepcion=True)
    finally:
        proveedor.shutdown()

    assert [span.name for span in destino.spans] == ["error", "excepcion"]
    assert destino.spans[0].status.status_code == StatusCode.ERROR


def test_procesador_errores_primero_exporta_todo_con_ratio_uno() -> None:
    """Con ratio 1.0 se exportan tanto los exitos como los errores."""
    destino = _ProcesadorDestino()
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    proveedor.add_span_processor(telemetria.ProcesadorErroresPrimero(destino, 1.0))

    try:
        _emitir_span(proveedor, "exito")
        _emitir_span(proveedor, "error", error=True)
    finally:
        proveedor.shutdown()

    assert [span.name for span in destino.spans] == ["exito", "error"]


@pytest.mark.parametrize(("entrada", "esperado"), [(-1.0, 0.0), (2.0, 1.0), (0.35, 0.35)])
def test_procesador_errores_primero_acota_el_ratio(entrada: float, esperado: float) -> None:
    """El ratio de exitos se acota al rango [0, 1]."""
    procesador = telemetria.ProcesadorErroresPrimero(_ProcesadorDestino(), entrada)

    assert procesador.ratio_exitos == pytest.approx(esperado)


def test_procesador_errores_primero_delega_vaciado_y_apagado() -> None:
    """force_flush y shutdown se delegan al procesador envuelto."""
    destino = _ProcesadorDestino()
    procesador = telemetria.ProcesadorErroresPrimero(destino, 0.2)

    assert procesador.force_flush() is True
    procesador.shutdown()

    assert destino.vaciado is True
    assert destino.apagado is True


def test_procesador_errores_primero_sanitiza_atributos_eventos_y_estado() -> None:
    """Cuerpos, coordenadas, correos y mensajes de excepcion se redactan al cerrar."""
    destino = _ProcesadorDestino()
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    proveedor.add_span_processor(telemetria.ProcesadorErroresPrimero(destino, 1.0))
    tracer = proveedor.get_tracer("pruebas.telemetria")

    try:
        with tracer.start_as_current_span("exito") as span:
            span.set_attribute("precios.estado", "aceptado")
            span.set_attribute("lat", 4.53)
            span.set_attribute("request.body", '{"lng": -75.68}')
            span.set_attribute(
                "url.query",
                "email=persona%40example.com&orden=lat%3D4.53&lng%3D-75.68",
            )
            span.record_exception(RuntimeError("correo persona%40example.com con lat%3D4.53"))
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "fallo con persona@example.com y lng=-75.68",
                )
            )
    finally:
        proveedor.shutdown()

    assert len(destino.spans) == 1
    span_exportado = destino.spans[0]
    atributos = dict(span_exportado.attributes or {})
    assert atributos["precios.estado"] == "aceptado"
    assert "lat" not in atributos
    assert "request.body" not in atributos
    assert atributos["url.query"] == (
        "email=[REDACTADO_EMAIL]&orden=lat%3D[REDACTADO_COORD]&lng%3D[REDACTADO_COORD]"
    )

    assert span_exportado.status.description == (
        "fallo con [REDACTADO_EMAIL] y lng=[REDACTADO_COORD]"
    )
    evento = next(evento for evento in span_exportado.events if evento.name == "exception")
    mensaje = dict(evento.attributes or {})["exception.message"]
    assert mensaje == "correo [REDACTADO_EMAIL] con lat%3D[REDACTADO_COORD]"


def test_procesador_errores_primero_redacta_pii_cruda_en_evento_y_estado() -> None:
    """El correo y las coordenadas crudos se redactan en eventos y descripcion."""
    destino = _ProcesadorDestino()
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    proveedor.add_span_processor(telemetria.ProcesadorErroresPrimero(destino, 1.0))
    tracer = proveedor.get_tracer("pruebas.telemetria")

    try:
        with tracer.start_as_current_span("error") as span:
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "fallo con persona@example.com lat=4.53 lng=-75.68",
                )
            )
            span.record_exception(ValueError("orden=persona@example.com&lat=4.53&lng=-75.68"))
    finally:
        proveedor.shutdown()

    assert len(destino.spans) == 1
    span_exportado = destino.spans[0]
    assert span_exportado.status.description == (
        "fallo con [REDACTADO_EMAIL] lat=[REDACTADO_COORD] lng=[REDACTADO_COORD]"
    )
    evento = next(evento for evento in span_exportado.events if evento.name == "exception")
    atributos_evento = dict(evento.attributes or {})
    assert atributos_evento["exception.message"] == (
        "orden=[REDACTADO_EMAIL]&lat=[REDACTADO_COORD]&lng=[REDACTADO_COORD]"
    )
    rastro = str(atributos_evento["exception.stacktrace"])
    assert "persona@example.com" not in rastro
    assert "4.53" not in rastro
    assert "-75.68" not in rastro


def test_procesador_errores_primero_no_propaga_fallo_de_sanitizacion(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Un fallo de sanitizacion descarta el span y no tumba la peticion."""
    destino = _ProcesadorDestino()
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    proveedor.add_span_processor(telemetria.ProcesadorErroresPrimero(destino, 0.0))

    def sanitizar_con_error(span: Any) -> None:
        raise RuntimeError("fallo de sanitizacion")

    monkeypatch.setattr(telemetria, "_sanitizar_span", sanitizar_con_error)
    with caplog.at_level(logging.WARNING, logger="app.telemetria"):
        try:
            _emitir_span(proveedor, "error", error=True)
        finally:
            proveedor.shutdown()

    assert destino.spans == []
    assert "Se descarta un span por fallo en la sanitizacion" in caplog.text


def test_procesador_errores_primero_no_propaga_fallo_de_exportacion(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Un fallo del procesador destino no se propaga al cerrar el span."""

    class _ProcesadorRoto(_ProcesadorDestino):
        def on_end(self, span: Any) -> None:
            raise RuntimeError("exportador caido")

    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    proveedor.add_span_processor(telemetria.ProcesadorErroresPrimero(_ProcesadorRoto(), 1.0))

    with caplog.at_level(logging.WARNING, logger="app.telemetria"):
        try:
            _emitir_span(proveedor, "exito")
        finally:
            proveedor.shutdown()

    assert "No fue posible exportar un span" in caplog.text


def test_redactar_texto_sensible_cubre_percent_encoding() -> None:
    """Los correos y coordenadas percent-encoded tambien se redactan."""
    texto = "email=persona%40example.com&orden=lat%3D4.53&lng%3D-75.68"

    redactado = redactar_texto_sensible(texto)

    assert redactado == (
        "email=[REDACTADO_EMAIL]&orden=lat%3D[REDACTADO_COORD]&lng%3D[REDACTADO_COORD]"
    )


def test_redactar_texto_sensible_redacta_telefonos_colombianos() -> None:
    """Los telefonos moviles y fijos no sobreviven, con o sin +57."""
    texto = (
        "telefono=3001234567; contacto +57 310 555 7788; "
        "fijo (606) 123-4567; mensaje='Llame al 320 444 5566'; "
        "precio_cop=3050; uuid=57355671-5518-4abc-9159-050bc91cacfc; "
        "fecha=2026-11-27 uuid2=123e4567-e89b-12d3-a456-426614174000"
    )

    redactado = redactar_texto_sensible(texto)

    assert "3001234567" not in redactado
    assert "310 555 7788" not in redactado
    assert "123-4567" not in redactado
    assert "320 444 5566" not in redactado
    assert redactado.count("[REDACTADO_TELEFONO]") == 4
    # Un patron demasiado amplio romperia precios, fechas, UUID e identificadores.
    assert "precio_cop=3050" in redactado
    assert "2026-11-27" in redactado
    assert "57355671-5518-4abc-9159-050bc91cacfc" in redactado
    assert "123e4567-e89b-12d3-a456-426614174000" in redactado


def test_redactar_texto_sensible_telefonos_percent_encoded() -> None:
    """Las variantes URL-encoded de telefono tambien se redactan."""
    texto = (
        "tel=%2B573001234567; tel2=300%201234567; "
        "tel3=%2B57%20300%20123%204567; "
        "uuid=57355671-5518-4abc-9159-050bc91cacfc"
    )

    redactado = redactar_texto_sensible(texto)

    assert "%2B573001234567" not in redactado
    assert "300%201234567" not in redactado
    assert "%2B57%20300%20123%204567" not in redactado
    assert redactado.count("[REDACTADO_TELEFONO]") == 3
    assert "57355671-5518-4abc-9159-050bc91cacfc" in redactado


def test_redactar_texto_sensible_protege_uuid_percent_encoded() -> None:
    """Un UUID codificado no se confunde con un telefono."""
    uuid_encoded = "57355671%2D5518%2D4abc%2D9159%2D050bc91cacfc"

    redactado = redactar_texto_sensible(f"caso={uuid_encoded}")

    assert redactado == f"caso={uuid_encoded}"
    assert "[REDACTADO_TELEFONO]" not in redactado


def test_redactar_texto_sensible_redacta_telefonos_adyacentes_a_guion() -> None:
    """Un guion separador no impide redactar el telefono."""
    texto = "telefonos:3001234567-3009998888; contacto=3001234567-casa; tel=%2B57-300-123-4567"

    redactado = redactar_texto_sensible(texto)

    assert "3001234567" not in redactado
    assert "3009998888" not in redactado
    assert "300-123-4567" not in redactado
    assert redactado.count("[REDACTADO_TELEFONO]") == 4


def test_filtro_privacidad_redacta_telefono_en_logs() -> None:
    """El filtro de Ley 1581 tambien sanea el telefono de un reclamo."""
    filtro = FiltroPrivacidadLey1581()
    record = logging.LogRecord(
        "app.comercial",
        logging.INFO,
        __file__,
        10,
        "reclamo telefono=%s mensaje=%s",
        ("3001234567", "Llame al 300 123 4567"),
        None,
    )

    filtro.filter(record)
    mensaje = record.getMessage()

    assert "3001234567" not in mensaje
    assert "300 123 4567" not in mensaje
    assert mensaje.count("[REDACTADO_TELEFONO]") == 2


def test_redactar_texto_sensible_redacta_ip_y_huella_red() -> None:
    """Las IP y las huellas de red tampoco sobreviven a la redaccion."""
    huella = "0123456789abcdef" * 4
    texto = (
        "cliente 190.1.2.3 desde [::1] e ip=10.0.0.1; "
        f"huella_red={huella}; hash={huella}; huella_red=huella-corta"
    )

    redactado = redactar_texto_sensible(texto)

    assert "190.1.2.3" not in redactado
    assert "10.0.0.1" not in redactado
    assert "::1" not in redactado
    assert huella not in redactado
    assert "huella-corta" not in redactado
    assert "huella_red" not in redactado
    assert redactado.count("[REDACTADO_IP]") == 3
    assert redactado.count("[REDACTADO_HUELLA]") == 3


def test_redactar_texto_sensible_huella_entre_comillas_y_query() -> None:
    """La huella se redacta en JSON/dict y no consume el resto de una query."""
    huella = "0123456789abcdef" * 4
    texto = (
        f'{{"huella_red": "{huella}", "otro": 1}}|'
        f"{{'huella_red': '{huella}'}}|"
        "huella_red=abc&correo=persona@example.com|"
        f"huella_red={huella}&otro=1"
    )

    redactado = redactar_texto_sensible(texto)

    assert huella not in redactado
    assert "huella_red" not in redactado
    assert '"huella_red"' not in redactado
    assert "'huella_red'" not in redactado
    assert "&correo=[REDACTADO_EMAIL]" in redactado
    assert "&otro=1" in redactado
    assert redactado.count("[REDACTADO_HUELLA]") == 4


def test_redactar_texto_sensible_huella_hex_usa_lookarounds_hex() -> None:
    """Una huella de 64 hex no se confunde con un prefijo de otra cadena hex."""
    huella = "a" * 64
    texto = f"_{huella}_ {huella}a {huella}b"

    redactado = redactar_texto_sensible(texto)

    assert redactado.count("[REDACTADO_HUELLA]") == 1
    assert f"{huella}a" in redactado
    assert f"{huella}b" in redactado


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [
        ("aceptado", "aceptado"),
        ("dudoso", "dudoso"),
        ("rechazado", "otro"),
        ("desconocido", "otro"),
    ],
)
def test_normalizar_estado_telemetria(estado: str, esperado: str) -> None:
    """El estado de telemetria se limita a etiquetas de baja cardinalidad."""
    assert _normalizar_estado_telemetria(estado) == esperado


class _ProviderApagable:
    """Provider de prueba que registra las llamadas de apagado."""

    def __init__(self, falla_vaciado: bool = False, falla_apagado: bool = False) -> None:
        self.llamadas: list[str] = []
        self.falla_vaciado = falla_vaciado
        self.falla_apagado = falla_apagado

    def force_flush(self) -> None:
        """Registra el vaciado y falla si la prueba lo indica."""
        self.llamadas.append("force_flush")
        if self.falla_vaciado:
            raise RuntimeError("fallo de vaciado")

    def shutdown(self) -> None:
        """Registra el apagado y falla si la prueba lo indica."""
        self.llamadas.append("shutdown")
        if self.falla_apagado:
            raise RuntimeError("fallo de apagado")


def test_apagar_telemetria_vacia_y_apaga_los_tres_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apaga trazas, metricas y logs en orden y deja la telemetria inactiva."""
    proveedor_trazas = _ProviderApagable()
    proveedor_metricas = _ProviderApagable()
    proveedor_logs = _ProviderApagable()
    monkeypatch.setattr(telemetria, "_tracer_provider", proveedor_trazas)
    monkeypatch.setattr(telemetria, "_meter_provider", proveedor_metricas)
    monkeypatch.setattr(telemetria, "_logger_provider", proveedor_logs)
    monkeypatch.setattr(telemetria, "_telemetria_activa", True)

    telemetria.apagar_telemetria()

    for proveedor in (proveedor_trazas, proveedor_metricas, proveedor_logs):
        assert proveedor.llamadas == ["force_flush", "shutdown"]
    assert telemetria.telemetria_activa() is False


def test_apagar_telemetria_no_lanza_si_los_providers_fallan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los fallos de force_flush o shutdown no impiden apagar el resto."""
    proveedor_trazas = _ProviderApagable(falla_vaciado=True)
    proveedor_metricas = _ProviderApagable(falla_apagado=True)
    proveedor_logs = _ProviderApagable()
    monkeypatch.setattr(telemetria, "_tracer_provider", proveedor_trazas)
    monkeypatch.setattr(telemetria, "_meter_provider", proveedor_metricas)
    monkeypatch.setattr(telemetria, "_logger_provider", proveedor_logs)

    telemetria.apagar_telemetria()

    assert proveedor_trazas.llamadas == ["force_flush", "shutdown"]
    assert proveedor_metricas.llamadas == ["force_flush", "shutdown"]
    assert proveedor_logs.llamadas == ["force_flush", "shutdown"]


def test_apagar_telemetria_sin_providers_no_lanza(monkeypatch: pytest.MonkeyPatch) -> None:
    """Llamar el apagado sin inicializacion previa es seguro e idempotente."""
    monkeypatch.setattr(telemetria, "_tracer_provider", None)
    monkeypatch.setattr(telemetria, "_meter_provider", None)
    monkeypatch.setattr(telemetria, "_logger_provider", None)

    telemetria.apagar_telemetria()
    telemetria.apagar_telemetria()

    assert telemetria.telemetria_activa() is False


def test_apagar_telemetria_es_idempotente_con_providers_que_fallan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dos apagados con providers defectuosos no lanzan ni repiten el cierre."""
    proveedor_trazas = _ProviderApagable(falla_vaciado=True, falla_apagado=True)
    proveedor_metricas = _ProviderApagable(falla_vaciado=True, falla_apagado=True)
    proveedor_logs = _ProviderApagable(falla_vaciado=True, falla_apagado=True)
    monkeypatch.setattr(telemetria, "_tracer_provider", proveedor_trazas)
    monkeypatch.setattr(telemetria, "_meter_provider", proveedor_metricas)
    monkeypatch.setattr(telemetria, "_logger_provider", proveedor_logs)

    telemetria.apagar_telemetria()
    telemetria.apagar_telemetria()

    for proveedor in (proveedor_trazas, proveedor_metricas, proveedor_logs):
        assert proveedor.llamadas == ["force_flush", "shutdown"]
    assert telemetria.telemetria_activa() is False


def test_sanitizar_atributos_bloquea_cuerpos_y_alias_de_ip() -> None:
    """Los cuerpos de solicitud/respuesta y los alias de IP nunca se exportan."""
    atributos = {
        "request.body": '{"lat": 4.53}',
        "response.body": "{}",
        "http.request.body": '{"lng": -75.68}',
        "http.response.body": "{}",
        "cuerpo.body": "contenido",
        "body": "contenido",
        "client_ip": "192.168.1.10",
        "ip_address": "192.168.1.10",
        "net.peer.ip": "192.168.1.10",
        "client.address": "192.168.1.10",
        "http.route": "/v1/reportes",
        "precios.estado": "aceptado",
    }

    resultado = telemetria.sanitizar_atributos(atributos)

    assert resultado == {
        "http.route": "/v1/reportes",
        "precios.estado": "aceptado",
    }


def _registro_de_prueba(mensaje: str = "hola") -> logging.LogRecord:
    """Crea un registro de log independiente de la configuracion global."""
    return logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=mensaje,
        args=(),
        exc_info=None,
    )


def test_filtro_correlacion_inyecta_ids_dentro_de_un_span() -> None:
    """Dentro de un span valido el filtro copia trace_id y span_id en hex."""
    filtro = FiltroCorrelacionTrazas()
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    tracer = proveedor.get_tracer("pruebas.logging")

    try:
        registro_fuera = _registro_de_prueba()
        assert filtro.filter(registro_fuera) is True
        assert registro_fuera.__dict__["trace_id"] == ""
        assert registro_fuera.__dict__["span_id"] == ""

        with tracer.start_as_current_span("prueba") as span:
            contexto = span.get_span_context()
            registro_dentro = _registro_de_prueba()
            assert filtro.filter(registro_dentro) is True
            assert registro_dentro.__dict__["trace_id"] == f"{contexto.trace_id:032x}"
            assert registro_dentro.__dict__["span_id"] == f"{contexto.span_id:016x}"
            assert len(registro_dentro.__dict__["trace_id"]) == 32
            assert len(registro_dentro.__dict__["span_id"]) == 16
    finally:
        proveedor.shutdown()


def test_filtro_privacidad_formatea_antes_de_redactar_sin_romper_placeholders() -> None:
    """Un placeholder con huella o IP se redacta sin dejar argumentos colgados."""
    registro = _registro_de_prueba()
    registro.msg = "huella_red=%s ip=%s"
    registro.args = ("a" * 64, "190.1.2.3")

    assert FiltroPrivacidadLey1581().filter(registro) is True

    mensaje = registro.getMessage()
    assert mensaje == "[REDACTADO_HUELLA] ip=[REDACTADO_IP]"
    assert "huella_red" not in mensaje
    assert "190.1.2.3" not in mensaje


def test_filtro_privacidad_no_lanza_con_registro_mal_formado() -> None:
    """Un registro con formato invalido se conserva sin propagar PII."""
    registro = _registro_de_prueba()
    registro.msg = "valor=%d persona@example.com lat=4.53"
    registro.args = ("no-numero",)

    assert FiltroPrivacidadLey1581().filter(registro) is True

    mensaje = registro.getMessage()
    assert mensaje == "valor=%d [REDACTADO_EMAIL] lat=[REDACTADO_COORD]"


def test_filtro_privacidad_redacta_traceback_y_stack_info() -> None:
    """`logger.exception` y `stack_info` tampoco exponen PII formateada."""
    logger = logging.getLogger("app.pruebas.traceback")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    salida = io.StringIO()
    manejador = logging.StreamHandler(salida)
    manejador.setFormatter(logging.Formatter("%(message)s"))
    manejador.addFilter(FiltroPrivacidadLey1581())
    logger.addHandler(manejador)

    try:
        try:
            raise ValueError("fallo con persona@example.com lat=4.53 ip=190.1.2.3")
        except ValueError:
            logger.exception(
                "reporte de persona@example.com con lat=4.53",
                stack_info=True,
            )
    finally:
        logger.removeHandler(manejador)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
        manejador.close()

    texto = salida.getvalue()
    assert "Traceback (most recent call last)" in texto
    assert "Stack (most recent call last)" in texto
    assert "persona@example.com" not in texto
    assert "lat=4.53" not in texto
    assert "190.1.2.3" not in texto
    assert "[REDACTADO_EMAIL]" in texto
    assert "[REDACTADO_COORD]" in texto
    assert "[REDACTADO_IP]" in texto


def test_filtro_correlacion_y_privacidad_coexisten() -> None:
    """La correlacion de trazas no impide redactar coordenadas y correos."""
    registro = _registro_de_prueba("lat=4.53,lng=-75.68 contacto@example.com")

    assert FiltroCorrelacionTrazas().filter(registro) is True
    assert FiltroPrivacidadLey1581().filter(registro) is True

    assert registro.getMessage() == (
        "lat=[REDACTADO_COORD],lng=[REDACTADO_COORD] [REDACTADO_EMAIL]"
    )
    assert registro.__dict__["trace_id"] == ""


def test_filtro_correlacion_publica_alias_otel() -> None:
    """Ademas de trace_id/span_id se publican otelTraceID/otelSpanID."""
    filtro = FiltroCorrelacionTrazas()
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    tracer = proveedor.get_tracer("pruebas.logging")

    try:
        registro_fuera = _registro_de_prueba()
        assert filtro.filter(registro_fuera) is True
        assert registro_fuera.__dict__["otelTraceID"] == ""
        assert registro_fuera.__dict__["otelSpanID"] == ""

        with tracer.start_as_current_span("prueba") as span:
            contexto = span.get_span_context()
            registro_dentro = _registro_de_prueba()
            assert filtro.filter(registro_dentro) is True
            assert registro_dentro.__dict__["otelTraceID"] == (registro_dentro.__dict__["trace_id"])
            assert registro_dentro.__dict__["otelSpanID"] == registro_dentro.__dict__["span_id"]
            assert registro_dentro.__dict__["otelTraceID"] == f"{contexto.trace_id:032x}"
            assert registro_dentro.__dict__["otelSpanID"] == f"{contexto.span_id:016x}"
    finally:
        proveedor.shutdown()


def _vaciar_handlers_raiz() -> None:
    """Retira los handlers de la raiz para simular un proceso sin logging.

    No se readjuntan: son capturadores que pytest instala y retira en cada fase.
    """
    logger_raiz = logging.getLogger()
    for handler in list(logger_raiz.handlers):
        logger_raiz.removeHandler(handler)


def test_configurar_logging_instala_handler_en_app_idempotente_y_emite_info(
    estado_logging: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Sin handlers previos instala la consola en `app` y el INFO sale por stdout."""
    logger_raiz = logging.getLogger()
    logger_app = logging.getLogger("app")
    _vaciar_handlers_raiz()

    configurar_logging()
    handlers_instalados = list(logger_app.handlers)
    assert len(handlers_instalados) == 1
    handler = handlers_instalados[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout
    assert handler.formatter is not None
    assert handler.formatter._fmt == FORMATO_LOG_CORRELACION
    tipos = {type(filtro) for filtro in handler.filters}
    assert FiltroPrivacidadLey1581 in tipos
    assert FiltroCorrelacionTrazas in tipos

    handlers_advertencias = list(logger_raiz.handlers)
    assert len(handlers_advertencias) == 1
    handler_advertencias = handlers_advertencias[0]
    assert isinstance(handler_advertencias, logging.StreamHandler)
    assert handler_advertencias.stream is sys.stderr
    assert handler_advertencias.level == logging.WARNING
    assert handler_advertencias.formatter is not None
    assert handler_advertencias.formatter._fmt == FORMATO_LOG_CORRELACION
    assert getattr(handler_advertencias, "_nombre_handler", None) == (_NOMBRE_HANDLER_ADVERTENCIAS)
    tipos_advertencias = {type(filtro) for filtro in handler_advertencias.filters}
    assert FiltroPrivacidadLey1581 in tipos_advertencias
    assert FiltroCorrelacionTrazas in tipos_advertencias
    assert logger_app.propagate is False

    configurar_logging()
    assert logger_app.handlers == handlers_instalados
    assert logger_raiz.handlers == handlers_advertencias

    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    tracer = proveedor.get_tracer("pruebas.logging")
    try:
        with tracer.start_as_current_span("prueba"):
            logger_app.info("mensaje de prueba")
    finally:
        proveedor.shutdown()

    salida = capsys.readouterr()
    assert re.search(
        r"INFO app \[trace_id=[0-9a-f]{32} span_id=[0-9a-f]{16}\] mensaje de prueba",
        salida.out,
    )
    assert salida.err == ""


def test_configurar_logging_no_instala_consola_si_la_raiz_ya_tiene_handler(
    estado_logging: None,
) -> None:
    """Con la raiz ya configurada no se duplica la salida en `app`."""
    logger_raiz = logging.getLogger()
    logger_app = logging.getLogger("app")
    handler_raiz = logging.NullHandler()
    logger_raiz.addHandler(handler_raiz)

    try:
        configurar_logging()
        assert logger_app.handlers == []
        assert logger_app.propagate is True
        tipos = {type(filtro) for filtro in handler_raiz.filters}
        assert FiltroPrivacidadLey1581 in tipos
        assert FiltroCorrelacionTrazas in tipos
    finally:
        logger_raiz.removeHandler(handler_raiz)


def test_configurar_logging_desactiva_el_access_log_de_uvicorn(estado_logging: None) -> None:
    """El access log nativo se desactiva para no registrar IP ni query string."""
    logger_uvicorn = logging.getLogger("uvicorn.access")
    logger_uvicorn.disabled = False

    configurar_logging()

    assert logger_uvicorn.disabled is True


def test_filtro_privacidad_sanea_un_access_log_nativo_de_uvicorn() -> None:
    """Un registro con placeholders y PII en los argumentos queda saneado."""
    registro = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=(
            "190.1.2.3",
            "GET",
            "/v1/productos/x/comparacion?lat=4.53&lng=-75.68&correo=persona@example.com",
            "1.1",
            200,
        ),
        exc_info=None,
    )

    assert FiltroPrivacidadLey1581().filter(registro) is True

    mensaje = registro.getMessage()
    assert registro.args == ()
    assert "190.1.2.3" not in mensaje
    assert "lat=4.53" not in mensaje
    assert "lng=-75.68" not in mensaje
    assert "persona@example.com" not in mensaje
    assert "/v1/productos/x/comparacion?lat=[REDACTADO_COORD]" in mensaje
    assert "[REDACTADO_IP]" in mensaje
    assert "[REDACTADO_EMAIL]" in mensaje


class _HandlerCaptura(logging.Handler):
    """Handler de prueba que conserva los registros ya filtrados."""

    def __init__(self) -> None:
        super().__init__()
        self.registros: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.registros.append(record)


def test_filtro_privacidad_anula_exc_info_y_conserva_traceback_redactado() -> None:
    """`logger.exception` deja trazado redactado en exc_text y exc_info en None."""
    logger = logging.getLogger("app.pruebas.exc_info")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    capturador = _HandlerCaptura()
    logger.addFilter(FiltroPrivacidadLey1581())
    logger.addHandler(capturador)

    try:
        try:
            raise ValueError("fallo con persona@example.com lat=4.53 ip=190.1.2.3")
        except ValueError:
            logger.exception("reporte de persona@example.com con lat=4.53")
    finally:
        logger.removeHandler(capturador)
        logger.filters[:] = [
            filtro for filtro in logger.filters if not isinstance(filtro, FiltroPrivacidadLey1581)
        ]
        logger.setLevel(logging.NOTSET)
        logger.propagate = True

    assert len(capturador.registros) == 1
    registro = capturador.registros[0]
    assert registro.exc_info is None
    assert registro.exc_text is not None
    assert "persona@example.com" not in registro.exc_text
    assert "lat=4.53" not in registro.exc_text
    assert "190.1.2.3" not in registro.exc_text

    texto = logging.Formatter("%(message)s").format(registro)
    assert "Traceback (most recent call last)" in texto
    assert "ValueError" in texto
    assert "[REDACTADO_EMAIL]" in texto
    assert "[REDACTADO_COORD]" in texto
    assert "[REDACTADO_IP]" in texto
    assert "persona@example.com" not in texto


def test_adjuntar_handler_logs_exporta_cuerpo_redactado_con_contexto() -> None:
    """El puente OTLP exporta el mensaje saneado y los ids del span actual."""
    exportador = InMemoryLogRecordExporter()
    proveedor_logs = LoggerProvider()
    proveedor_logs.add_log_record_processor(SimpleLogRecordProcessor(exportador))
    proveedor_trazas = TracerProvider(sampler=telemetria.ALWAYS_ON)
    tracer = proveedor_trazas.get_tracer("pruebas.logging")
    logger = logging.getLogger("app.pruebas.otlp")
    logger.setLevel(logging.INFO)

    try:
        telemetria._adjuntar_handler_logs(proveedor_logs)
        with tracer.start_as_current_span("prueba") as span:
            contexto = span.get_span_context()
            logger.info(
                "evento correo=persona@example.com lat=4.53 lng=-75.68 ip=190.1.2.3 huella_red=%s",
                "a" * 64,
            )
        registros = exportador.get_finished_logs()
    finally:
        telemetria._quitar_handler_logs()
        logger.setLevel(logging.NOTSET)
        proveedor_trazas.shutdown()
        proveedor_logs.shutdown()

    assert len(registros) == 1
    registro = registros[0].log_record
    cuerpo = str(registro.body)
    assert "persona@example.com" not in cuerpo
    assert "lat=4.53" not in cuerpo
    assert "lng=-75.68" not in cuerpo
    assert "190.1.2.3" not in cuerpo
    assert "a" * 64 not in cuerpo
    assert "huella_red" not in cuerpo
    assert "[REDACTADO_EMAIL]" in cuerpo
    assert "[REDACTADO_COORD]" in cuerpo
    assert "[REDACTADO_IP]" in cuerpo
    assert "[REDACTADO_HUELLA]" in cuerpo
    texto_atributos = str(dict(registro.attributes or {}))
    assert "persona@example.com" not in texto_atributos
    assert "4.53" not in texto_atributos
    assert "190.1.2.3" not in texto_atributos
    assert "a" * 64 not in texto_atributos
    assert registro.trace_id == contexto.trace_id
    assert registro.span_id == contexto.span_id


def test_adjuntar_handler_logs_exporta_excepcion_redactada() -> None:
    """El cuerpo OTLP incluye el traceback redactado y sin atributos crudos."""
    exportador = InMemoryLogRecordExporter()
    proveedor_logs = LoggerProvider()
    proveedor_logs.add_log_record_processor(SimpleLogRecordProcessor(exportador))
    logger = logging.getLogger("app.pruebas.otlp.excepcion")
    logger.setLevel(logging.INFO)

    try:
        telemetria._adjuntar_handler_logs(proveedor_logs)
        try:
            raise ValueError("fallo con persona@example.com lat=4.53 ip=190.1.2.3")
        except ValueError:
            logger.exception("reporte de persona@example.com con lat=4.53")
        registros = exportador.get_finished_logs()
    finally:
        telemetria._quitar_handler_logs()
        logger.setLevel(logging.NOTSET)
        proveedor_logs.shutdown()

    assert len(registros) == 1
    registro = registros[0].log_record
    cuerpo = str(registro.body)
    assert "reporte de [REDACTADO_EMAIL] con lat=[REDACTADO_COORD]" in cuerpo
    assert "Traceback (most recent call last)" in cuerpo
    assert "ValueError" in cuerpo
    assert "persona@example.com" not in cuerpo
    assert "lat=4.53" not in cuerpo
    assert "190.1.2.3" not in cuerpo
    assert "[REDACTADO_EMAIL]" in cuerpo
    assert "[REDACTADO_COORD]" in cuerpo
    assert "[REDACTADO_IP]" in cuerpo
    atributos = registro.attributes or {}
    texto_atributos = str(dict(atributos))
    assert "persona@example.com" not in texto_atributos
    assert "4.53" not in texto_atributos
    assert "190.1.2.3" not in texto_atributos
    assert "exception.stacktrace" not in atributos


def test_adjuntar_handler_logs_es_idempotente(estado_logging: None) -> None:
    """Dos adjuntos dejan un solo handler del SDK en `app`."""
    logger_app = logging.getLogger("app")
    proveedor = LoggerProvider()

    try:
        telemetria._adjuntar_handler_logs(proveedor)
        primero = telemetria._handler_logs
        telemetria._adjuntar_handler_logs(proveedor)
        segundo = telemetria._handler_logs
        adjuntos = [
            handler for handler in logger_app.handlers if isinstance(handler, LoggingHandler)
        ]
        assert adjuntos == [segundo]
    finally:
        telemetria._quitar_handler_logs()
        proveedor.shutdown()

    assert primero is not None
    assert segundo is not None
    assert primero is not segundo


def test_quitar_handler_logs_retira_y_es_idempotente(estado_logging: None) -> None:
    """El handler se retira de `app` y quitarlo de nuevo no lanza."""
    logger_app = logging.getLogger("app")
    proveedor = LoggerProvider()
    telemetria._adjuntar_handler_logs(proveedor)
    handler = telemetria._handler_logs
    assert handler is not None
    assert handler in logger_app.handlers

    try:
        telemetria._quitar_handler_logs()
        assert telemetria._handler_logs is None
        assert handler not in logger_app.handlers
        telemetria._quitar_handler_logs()
        assert telemetria._handler_logs is None
    finally:
        proveedor.shutdown()


class _ProviderEspia:
    """Provider que registra si el handler sigue en `app` al cerrarse."""

    def __init__(self) -> None:
        self.handler_presente: list[bool] = []

    def _estado(self) -> bool:
        handler = telemetria._handler_logs
        return handler is not None and handler in logging.getLogger("app").handlers

    def force_flush(self) -> None:
        """Registra el estado del handler durante el vaciado."""
        self.handler_presente.append(self._estado())

    def shutdown(self) -> None:
        """Registra el estado del handler durante el apagado."""
        self.handler_presente.append(self._estado())


def test_apagar_telemetria_retira_el_handler_antes_de_cerrar_provider(
    estado_logging: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El handler ya no esta en `app` cuando el provider se vacia y se apaga."""
    proveedor_logs = LoggerProvider()
    telemetria._adjuntar_handler_logs(proveedor_logs)
    handler = telemetria._handler_logs
    espia = _ProviderEspia()
    monkeypatch.setattr(telemetria, "_logger_provider", espia)

    try:
        telemetria.apagar_telemetria()
    finally:
        proveedor_logs.shutdown()

    assert handler is not None
    assert handler not in logging.getLogger("app").handlers
    assert espia.handler_presente == [False, False]


def test_adjuntar_handler_logs_sin_sdk_advierte_y_no_lanza(
    estado_logging: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Si el SDK no expone LoggingHandler se advierte de forma generica."""
    proveedor = LoggerProvider()
    monkeypatch.setattr(telemetria, "_FABRICA_HANDLER_LOGS", None)

    try:
        with caplog.at_level(logging.WARNING, logger="app.telemetria"):
            telemetria._adjuntar_handler_logs(proveedor)
    finally:
        proveedor.shutdown()

    assert telemetria._handler_logs is None
    assert logging.getLogger("app").handlers == []
    assert "No fue posible habilitar la exportacion de logs" in caplog.text


def test_logs_de_terceros_no_pasan_por_handlers_de_app(
    estado_logging: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Un INFO de httpx con UUID y archivo no se emite ni se exporta."""
    _vaciar_handlers_raiz()
    exportador = InMemoryLogRecordExporter()
    proveedor_logs = LoggerProvider()
    proveedor_logs.add_log_record_processor(SimpleLogRecordProcessor(exportador))
    logger_httpx = logging.getLogger("httpx")
    nivel_previo = logger_httpx.level
    logger_httpx.setLevel(logging.INFO)

    try:
        configurar_logging()
        telemetria._adjuntar_handler_logs(proveedor_logs)
        logger_httpx.info(
            'HTTP Request: GET https://storage.example/%s/%s "HTTP/1.1 200 OK"',
            "550e8400-e29b-41d4-a716-446655440000",
            "foto_cedula_juan.jpg",
        )
        salida = capsys.readouterr()
        registros = exportador.get_finished_logs()
    finally:
        logger_httpx.setLevel(nivel_previo)
        telemetria._quitar_handler_logs()
        proveedor_logs.shutdown()

    assert registros == ()
    assert salida.out == ""
    assert salida.err == ""
    assert "550e8400-e29b-41d4-a716-446655440000" not in salida.out
    assert "foto_cedula_juan.jpg" not in salida.out


def test_logs_de_terceros_warning_se_redactan_en_stderr(
    estado_logging: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Un WARNING de httpx con PII sale una vez por stderr y redactado."""
    _vaciar_handlers_raiz()
    logger_httpx = logging.getLogger("httpx")
    nivel_previo = logger_httpx.level
    logger_httpx.setLevel(logging.INFO)

    try:
        configurar_logging()
        logger_httpx.info("INFO_TERCEROS_NO_DEBE_SALIR")
        logger_httpx.warning("fallo correo=persona@example.com lat=4.53 lng=-75.68 ip=190.1.2.3")
        salida = capsys.readouterr()
    finally:
        logger_httpx.setLevel(nivel_previo)

    texto = salida.err
    assert "INFO_TERCEROS_NO_DEBE_SALIR" not in texto
    assert "persona@example.com" not in texto
    assert "lat=4.53" not in texto
    assert "lng=-75.68" not in texto
    assert "190.1.2.3" not in texto
    assert "[REDACTADO_EMAIL]" in texto
    assert "[REDACTADO_COORD]" in texto
    assert "[REDACTADO_IP]" in texto
    assert "WARNING httpx" in texto
    assert salida.out == ""


def test_warning_de_app_se_emite_una_sola_vez(
    estado_logging: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Con `app.propagate=False` el WARNING no se duplica en el handler raiz."""
    _vaciar_handlers_raiz()
    configurar_logging()

    logging.getLogger("app").warning("advertencia unica de app")
    salida = capsys.readouterr()

    assert salida.out.count("advertencia unica de app") == 1
    assert "WARNING app" in salida.out
    assert salida.err == ""


def test_configurar_logging_filtra_handlers_de_uvicorn_error(
    estado_logging: None,
) -> None:
    """Los handlers de uvicorn.error reciben el filtro de privacidad."""
    logger_uvicorn = logging.getLogger("uvicorn.error")
    salida = io.StringIO()
    handler = logging.StreamHandler(salida)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger_uvicorn.addHandler(handler)

    try:
        configurar_logging()
        tipos = {type(filtro) for filtro in handler.filters}
        assert FiltroPrivacidadLey1581 in tipos
        logger_uvicorn.error("fallo con persona@example.com lat=4.53 ip=190.1.2.3")
        texto = salida.getvalue()
    finally:
        logger_uvicorn.removeHandler(handler)
        handler.close()

    assert "persona@example.com" not in texto
    assert "lat=4.53" not in texto
    assert "190.1.2.3" not in texto
    assert "[REDACTADO_EMAIL]" in texto
    assert "[REDACTADO_COORD]" in texto
    assert "[REDACTADO_IP]" in texto


def test_configurar_logging_filtra_el_handler_real_de_uvicorn(
    estado_logging: None,
) -> None:
    """Con el handler en `uvicorn`, un ERROR de uvicorn.error sale redactado."""
    logger_uvicorn = logging.getLogger("uvicorn")
    logger_uvicorn_error = logging.getLogger("uvicorn.error")
    salida = io.StringIO()
    handler = logging.StreamHandler(salida)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger_uvicorn.addHandler(handler)
    logger_uvicorn.propagate = False

    try:
        configurar_logging()
        tipos = {type(filtro) for filtro in handler.filters}
        assert FiltroPrivacidadLey1581 in tipos
        logger_uvicorn_error.error("fallo con persona@example.com lat=4.53 ip=190.1.2.3")
        texto = salida.getvalue()
    finally:
        logger_uvicorn.removeHandler(handler)
        handler.close()

    assert "persona@example.com" not in texto
    assert "lat=4.53" not in texto
    assert "190.1.2.3" not in texto
    assert "[REDACTADO_EMAIL]" in texto
    assert "[REDACTADO_COORD]" in texto
    assert "[REDACTADO_IP]" in texto
