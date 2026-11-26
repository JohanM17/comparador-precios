"""Pruebas de los artefactos de observabilidad versionados (Tarea T-122)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts import validar_observabilidad as validador


@pytest.fixture()
def dashboard_valido() -> dict[str, Any]:
    """Carga el tablero versionado desde disco."""
    return validador.cargar_json(validador.RUTA_DASHBOARD)


@pytest.fixture()
def reglas_validas() -> dict[str, Any]:
    """Carga las reglas versionadas desde disco."""
    return validador.cargar_yaml(validador.RUTA_REGLAS)


def _buscar_alerta(datos: dict[str, Any], nombre: str) -> dict[str, Any]:
    """Devuelve la alerta indicada o falla si no existe."""
    for grupo in datos["groups"]:
        for regla in grupo["rules"]:
            if regla.get("alert") == nombre:
                return regla
    raise AssertionError(f"No se encontro la alerta {nombre}")


def _buscar_grabacion(datos: dict[str, Any], nombre: str) -> dict[str, Any]:
    """Devuelve la regla de grabacion indicada o falla si no existe."""
    for grupo in datos["groups"]:
        for regla in grupo["rules"]:
            if regla.get("record") == nombre:
                return regla
    raise AssertionError(f"No se encontro la regla de grabacion {nombre}")


def _guardar_yaml(datos: dict[str, Any], ruta: Path) -> Path:
    """Escribe reglas temporales manteniendo el formato YAML."""
    ruta.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return ruta


def test_artefactos_versionados_pasan_la_validacion() -> None:
    """El tablero y las reglas actuales cumplen todas las comprobaciones."""
    assert validador.validar_artefactos(validador.RUTA_DASHBOARD, validador.RUTA_REGLAS) == []


def test_emision_de_resumen_es_exitosa(capsys: pytest.CaptureFixture[str]) -> None:
    """El comando principal devuelve 0 e informa el resultado."""
    assert validador.main([]) == 0
    assert "[OK]" in capsys.readouterr().out


def test_dashboard_con_uid_incorrecto_falla(dashboard_valido: dict[str, Any]) -> None:
    """El UID identifica el tablero que Grafana aprovisiona."""
    datos = copy.deepcopy(dashboard_valido)
    datos["uid"] = "otro-tablero"

    errores = validador.validar_dashboard(datos)

    assert any("uid" in error for error in errores)


def test_dashboard_requiere_diez_paneles_de_datos(dashboard_valido: dict[str, Any]) -> None:
    """El tablero debe conservar la cobertura minima de paneles."""
    datos = copy.deepcopy(dashboard_valido)
    datos["panels"] = datos["panels"][:1]

    errores = validador.validar_dashboard(datos)

    assert any("al menos 10 paneles" in error for error in errores)


def test_dashboard_requiere_titulos_minimos(dashboard_valido: dict[str, Any]) -> None:
    """Los titulos cubren trafico, latencia, errores, cache, BD, reportes y SLO."""
    datos = copy.deepcopy(dashboard_valido)
    for panel in datos["panels"]:
        panel["title"] = ""

    errores = validador.validar_dashboard(datos)

    assert any("Faltan titulos minimos" in error for error in errores)
    assert any("base de datos" in error for error in errores)


def test_dashboard_requiere_variable_datasource(dashboard_valido: dict[str, Any]) -> None:
    """Las consultas deben elegir el datasource con una variable."""
    datos = copy.deepcopy(dashboard_valido)
    datos["templating"] = {"list": []}

    errores = validador.validar_dashboard(datos)

    assert any("datasource" in error for error in errores)


def test_dashboard_rechaza_http_route(dashboard_valido: dict[str, Any]) -> None:
    """La instrumentacion actual expone http_target, no http_route."""
    datos = copy.deepcopy(dashboard_valido)
    panel = next(
        panel
        for panel in datos["panels"]
        if panel.get("targets") and "http_target" in panel["targets"][0].get("expr", "")
    )
    panel["targets"][0]["expr"] = panel["targets"][0]["expr"].replace("http_target", "http_route")

    errores = validador.validar_dashboard(datos)

    assert any("http_route" in error for error in errores)


def test_dashboard_exige_buckets_y_ventana_del_sli(dashboard_valido: dict[str, Any]) -> None:
    """El SLI debe usar los buckets de 1000/2500 ms y la ventana de 7 dias."""
    datos = copy.deepcopy(dashboard_valido)
    panel_sli = next(panel for panel in datos["panels"] if "SLI" in panel["title"])
    panel_sli["targets"][0]["expr"] = panel_sli["targets"][0]["expr"].replace(
        'le="2500"', 'le="5000"'
    )

    errores = validador.validar_dashboard(datos)

    assert any('le="2500"' in error for error in errores)


def test_reglas_sin_grupos_falla(reglas_validas: dict[str, Any]) -> None:
    """Un archivo sin grupos no puede importarse en Prometheus/Mimir."""
    datos = copy.deepcopy(reglas_validas)
    datos["groups"] = []

    errores = validador.validar_reglas(datos)

    assert any("'groups' no vacia" in error for error in errores)


def test_reglas_sin_alertas_falla(reglas_validas: dict[str, Any]) -> None:
    """El archivo debe declarar al menos una alerta."""
    datos = copy.deepcopy(reglas_validas)
    datos["groups"][0]["rules"] = [
        regla for regla in datos["groups"][0]["rules"] if "alert" not in regla
    ]

    errores = validador.validar_reglas(datos)

    assert any("ninguna regla de tipo 'alert'" in error for error in errores)


@pytest.mark.parametrize("campo", ["for", "severity", "summary"])
def test_alerta_principal_exige_campos_obligatorios(
    reglas_validas: dict[str, Any],
    campo: str,
) -> None:
    """La alerta principal necesita for, severidad y resumen."""
    datos = copy.deepcopy(reglas_validas)
    alerta = _buscar_alerta(datos, validador.ALERTA_SLO)
    if campo == "for":
        del alerta["for"]
        esperado = "'for'"
    elif campo == "severity":
        del alerta["labels"]["severity"]
        esperado = "labels.severity"
    else:
        del alerta["annotations"]["summary"]
        esperado = "annotations.summary"

    errores = validador.validar_reglas(datos)

    assert any(esperado in error for error in errores)


def test_falta_regla_de_grabacion_del_sli(reglas_validas: dict[str, Any]) -> None:
    """La serie comparador:sli_comparacion_7d debe existir como grabacion."""
    datos = copy.deepcopy(reglas_validas)
    datos["groups"][0]["rules"] = [
        regla for regla in datos["groups"][0]["rules"] if regla.get("record") != validador.REGLA_SLI
    ]

    errores = validador.validar_reglas(datos)

    assert any("Falta la regla de grabacion" in error for error in errores)


def test_regla_de_grabacion_debe_coincidir_con_el_dashboard(
    dashboard_valido: dict[str, Any],
    reglas_validas: dict[str, Any],
) -> None:
    """La grabacion no puede desviarse de la consulta SLI del tablero."""
    datos = copy.deepcopy(reglas_validas)
    grabacion = _buscar_grabacion(datos, validador.REGLA_SLI)
    grabacion["expr"] = "vector(1)"
    expresion_dashboard = validador.extraer_expresion_sli(dashboard_valido)

    errores = validador.validar_reglas(datos, expresion_dashboard)

    assert any("no coincide exactamente" in error for error in errores)


def test_alerta_principal_debe_usar_la_regla_de_grabacion(
    reglas_validas: dict[str, Any],
) -> None:
    """La alerta principal evalua la serie grabada del SLI."""
    datos = copy.deepcopy(reglas_validas)
    alerta = _buscar_alerta(datos, validador.ALERTA_SLO)
    alerta["expr"] = "vector(1) < 0.99"

    errores = validador.validar_reglas(datos)

    assert any("no usa" in error for error in errores)


def test_validar_artefactos_rechaza_secreto_en_el_dashboard(
    dashboard_valido: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Un Authorization embebido en el JSON se reporta sin revelar el valor."""
    datos = copy.deepcopy(dashboard_valido)
    datos["description"] = "Authorization: Bearer abcdef123456"
    ruta = tmp_path / "dashboard.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")

    errores = validador.validar_artefactos(ruta, validador.RUTA_REGLAS)

    assert any("authorization" in error.lower() for error in errores)
    assert all("abcdef123456" not in error for error in errores)


def test_validar_artefactos_rechaza_url_de_grafana(
    reglas_validas: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Las reglas no deben fijar endpoints de Grafana Cloud."""
    datos = copy.deepcopy(reglas_validas)
    alerta = _buscar_alerta(datos, validador.ALERTA_SLO)
    alerta["annotations"]["description"] += " https://mi-org.grafana.net/d/abc"
    ruta = _guardar_yaml(datos, tmp_path / "reglas.yml")

    errores = validador.validar_artefactos(validador.RUTA_DASHBOARD, ruta)

    assert any("URL de Grafana" in error for error in errores)


def test_validador_devuelve_uno_con_reglas_invalidas(
    reglas_validas: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """El comando principal sale con codigo 1 si las reglas no son validas."""
    datos = copy.deepcopy(reglas_validas)
    datos["groups"] = []
    ruta = _guardar_yaml(datos, tmp_path / "reglas.yml")

    codigo = validador.main(["--dashboard", str(validador.RUTA_DASHBOARD), "--reglas", str(ruta)])

    assert codigo == 1
    assert "[FALLO]" in capsys.readouterr().out


def test_archivos_inexistentes_se_reportan(tmp_path: Path) -> None:
    """La ausencia de artefactos produce errores claros y no una excepcion."""
    errores = validador.validar_artefactos(
        tmp_path / "dashboard.json",
        tmp_path / "reglas.yml",
    )

    assert len(errores) == 2
    assert any("dashboard" in error for error in errores)
    assert any("reglas" in error for error in errores)


def test_cargar_yaml_sin_pyyaml_falla_con_mensaje_claro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin PyYAML el validador explica como continuar."""
    monkeypatch.setattr(validador, "yaml", None)

    with pytest.raises(RuntimeError, match="PyYAML"):
        validador.cargar_yaml(validador.RUTA_REGLAS)
