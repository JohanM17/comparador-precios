"""Pruebas unitarias de la configuracion de telemetria (Tareas T-103 y T-120)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from importlib import metadata
from typing import Any

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import StatusCode

from app.compartido import telemetria
from app.compartido.logging_cfg import FiltroCorrelacionTrazas, FiltroPrivacidadLey1581
from app.config import Configuracion


@pytest.fixture(autouse=True)
def reiniciar_estado_telemetria(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aisla el estado global del modulo entre pruebas."""
    monkeypatch.setattr(telemetria, "_telemetria_activa", False)
    monkeypatch.setattr(telemetria, "_tracer_provider", None)
    monkeypatch.setattr(telemetria, "_meter_provider", None)
    monkeypatch.setattr(telemetria, "_logger_provider", None)


def _configuracion(**cambios: Any) -> Configuracion:
    """Construye una configuracion sin leer el archivo .env real."""
    return Configuracion(_env_file=None, **cambios)


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


class _ProveedorLogsFalso:
    """Proveedor de logs de prueba."""

    def __init__(self, resource: Any = None) -> None:
        self.resource = resource
        self.procesadores: list[Any] = []

    def add_log_record_processor(self, procesador: Any) -> None:
        self.procesadores.append(procesador)


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


def test_procesador_errores_primero_sanitiza_atributos_antes_de_exportar() -> None:
    """Los cuerpos, coordenadas y correos se eliminan o redactan al cerrar el span."""
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
                "url.full", "https://app.example.com/v1?lat=4.53&lng=-75.68&email=a@b.co"
            )
    finally:
        proveedor.shutdown()

    assert len(destino.spans) == 1
    atributos = dict(destino.spans[0].attributes or {})
    assert atributos["precios.estado"] == "aceptado"
    assert "lat" not in atributos
    assert "request.body" not in atributos
    assert atributos["url.full"] == (
        "https://app.example.com/v1?lat=[REDACTADO_COORD]&lng=[REDACTADO_COORD]"
        "&email=[REDACTADO_EMAIL]"
    )


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


def test_filtro_correlacion_y_privacidad_coexisten() -> None:
    """La correlacion de trazas no impide redactar coordenadas y correos."""
    registro = _registro_de_prueba("lat=4.53,lng=-75.68 contacto@example.com")

    assert FiltroCorrelacionTrazas().filter(registro) is True
    assert FiltroPrivacidadLey1581().filter(registro) is True

    assert registro.getMessage() == (
        "lat=[REDACTADO_COORD],lng=[REDACTADO_COORD] [REDACTADO_EMAIL]"
    )
    assert registro.__dict__["trace_id"] == ""
