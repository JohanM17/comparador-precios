"""Pruebas unitarias de la configuracion base de telemetria (Tarea T-103)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from importlib import metadata
from typing import Any

import pytest

from app.compartido import telemetria
from app.config import Configuracion


@pytest.fixture(autouse=True)
def reiniciar_estado_telemetria(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aisla el estado global del modulo entre pruebas."""
    monkeypatch.setattr(telemetria, "_telemetria_activa", False)


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


def test_configurar_telemetria_inicializa_trazas_metricas_y_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con endpoint y exportadores habilitados configura los tres providers."""
    creados, registrados = _instalar_dobles_otel(monkeypatch)
    configuracion = _configuracion(
        OTEL_SERVICE_NAME="comparador-pruebas",
        ENTORNO="pruebas",
        OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318",
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

    for nombre in ("trazas", "metricas", "logs"):
        assert creados[nombre][0].endpoint == "http://127.0.0.1:4318"
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
