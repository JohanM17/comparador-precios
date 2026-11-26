"""Pruebas unitarias de la configuracion de telemetria (Tarea T-100)."""

from __future__ import annotations

import pytest

from app.config import Configuracion

VARIABLES_TELEMETRIA = (
    "OTEL_SDK_DISABLED",
    "OTEL_SERVICE_NAME",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_HEADERS",
    "OTEL_TRACES_SAMPLER",
    "OTEL_TRACES_SAMPLER_ARG",
    "OTEL_METRICS_EXPORTER",
    "OTEL_LOGS_EXPORTER",
    "SIMULAR_LATENCIA_MS",
)


@pytest.fixture
def sin_variables_de_telemetria(monkeypatch: pytest.MonkeyPatch) -> None:
    """Elimina las variables de telemetria del entorno para probar los defaults."""
    for variable in VARIABLES_TELEMETRIA:
        monkeypatch.delenv(variable, raising=False)


def test_defaults_configuracion_telemetria(sin_variables_de_telemetria: None) -> None:
    """Verifica los valores por defecto de la configuracion de OpenTelemetry."""
    configuracion = Configuracion(_env_file=None)

    assert configuracion.OTEL_SDK_DISABLED is False
    assert configuracion.OTEL_SERVICE_NAME == "comparador-precios-backend"
    assert configuracion.OTEL_EXPORTER_OTLP_ENDPOINT == ""
    assert configuracion.OTEL_EXPORTER_OTLP_HEADERS == ""
    assert configuracion.OTEL_TRACES_SAMPLER == "parentbased_traceidratio"
    assert configuracion.OTEL_TRACES_SAMPLER_ARG == pytest.approx(0.2)
    assert configuracion.OTEL_METRICS_EXPORTER == "otlp"
    assert configuracion.OTEL_LOGS_EXPORTER == "otlp"
    assert configuracion.SIMULAR_LATENCIA_MS == 0


def test_otel_sdk_disabled_se_lee_desde_el_entorno(
    sin_variables_de_telemetria: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica que OTEL_SDK_DISABLED=true se interprete como booleano."""
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")

    configuracion = Configuracion(_env_file=None)

    assert configuracion.OTEL_SDK_DISABLED is True
