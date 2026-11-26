#!/usr/bin/env python3
"""Valida los artefactos de observabilidad versionados (Tarea T-122).

Comprueba, sin red y sin credenciales:

- El JSON del tablero de Grafana: UID, paneles minimos, variable de datasource,
  uso de la etiqueta http_target y ausencia de secretos.
- El YAML de reglas de Prometheus/Mimir: grupos, regla de grabacion del SLI,
  alertas con for/labels/annotations, coincidencia con la consulta del tablero
  y ausencia de secretos o URLs de Grafana.

Solo usa la biblioteca estandar y PyYAML. Si PyYAML no esta disponible, termina
con un mensaje claro en lugar de un rastro de importacion.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - depende del entorno de ejecucion
    yaml = None  # type: ignore[assignment]

RAIZ_REPOSITORIO = Path(__file__).resolve().parent.parent
RUTA_DASHBOARD = (
    RAIZ_REPOSITORIO
    / "infra"
    / "observabilidad"
    / "grafana"
    / "dashboards"
    / "observabilidad-comparador.json"
)
RUTA_REGLAS = (
    RAIZ_REPOSITORIO / "infra" / "observabilidad" / "grafana" / "alertas" / "slo-comparador.yml"
)

UID_DASHBOARD = "comparador-observabilidad"
MINIMO_PANELES_DATOS = 10
REGLA_SLI = "comparador:sli_comparacion_7d"
ALERTA_SLO = "ComparadorSLOComparacionIncumplido"

TITULOS_MINIMOS: dict[str, tuple[str, ...]] = {
    "trafico": ("trafico", "solicitud"),
    "latencia": ("latencia",),
    "errores": ("error",),
    "cache": ("cache",),
    "base de datos": ("base de datos", "bd"),
    "reportes": ("reporte",),
    "slo": ("slo", "sli"),
    "presupuesto": ("presupuesto",),
    "alertas": ("alerta",),
}

FRAGMENTOS_SLI = (
    "http_target",
    'le="1000"',
    'le="2500"',
    "[7d]",
    'http_status_code!~"5.."',
)

PATRONES_SECRETO: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("authorization", re.compile(r"authorization\s*[:=]", re.IGNORECASE)),
    ("bearer", re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)),
    ("basic", re.compile(r"\bbasic\s+[A-Za-z0-9+/=]{8,}", re.IGNORECASE)),
    (
        "token",
        re.compile(r"\b(?:access[_-]?|refresh[_-]?|id[_-]?)?token\s*[:=]", re.IGNORECASE),
    ),
    ("password", re.compile(r"\b(?:password|passwd|contrasena)\s*[:=]", re.IGNORECASE)),
    ("api key", re.compile(r"\bapi[_-]?key\s*[:=]", re.IGNORECASE)),
    ("secret", re.compile(r"\b(?:client[_-]?)?secret\s*[:=]", re.IGNORECASE)),
    ("credenciales en URL", re.compile(r"://[^/\s:@]+:[^/\s@]+@")),
)

PATRONES_URL_GRAFANA: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("grafana.com", re.compile(r"grafana\.com", re.IGNORECASE)),
    ("grafana.net", re.compile(r"grafana\.net", re.IGNORECASE)),
    ("GRAFANA_", re.compile(r"\bGRAFANA_[A-Z_]+\b")),
)


def normalizar_texto(texto: str) -> str:
    """Quita tildes y pasa a minusculas para comparar titulos y etiquetas."""
    sin_tildes = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caracter)
    )
    return sin_tildes.casefold()


def normalizar_expresion(expresion: str) -> str:
    """Colapsa espacios para comparar PromQL escrita con saltos de linea."""
    return " ".join(expresion.split())


def cargar_json(ruta: Path) -> dict[str, Any]:
    """Carga un objeto JSON desde disco."""
    with ruta.open(encoding="utf-8") as archivo:
        datos = json.load(archivo)
    if not isinstance(datos, dict):
        raise ValueError(f"El JSON de {ruta} debe ser un objeto.")
    return datos


def cargar_yaml(ruta: Path) -> dict[str, Any]:
    """Carga un objeto YAML desde disco usando el parser seguro."""
    if yaml is None:
        raise RuntimeError(
            "PyYAML no esta instalado. Ejecuta el validador con el entorno de "
            "desarrollo del backend o instala las dependencias de desarrollo."
        )
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML invalido en {ruta}: {exc}") from exc
    if not isinstance(datos, dict):
        raise ValueError(f"El YAML de {ruta} debe ser un objeto con 'groups'.")
    return datos


def _aplanar_paneles(paneles: list[Any]) -> list[dict[str, Any]]:
    """Devuelve los paneles y sus hijos anidados en orden de aparicion."""
    aplanados: list[dict[str, Any]] = []
    for panel in paneles:
        if not isinstance(panel, dict):
            continue
        aplanados.append(panel)
        hijos = panel.get("panels")
        if isinstance(hijos, list):
            aplanados.extend(_aplanar_paneles(hijos))
    return aplanados


def _expresiones_panel(panel: dict[str, Any]) -> list[str]:
    """Extrae las expresiones PromQL no vacias de los targets de un panel."""
    objetivos = panel.get("targets")
    if not isinstance(objetivos, list):
        return []
    expresiones: list[str] = []
    for objetivo in objetivos:
        if not isinstance(objetivo, dict):
            continue
        expresion = objetivo.get("expr")
        if isinstance(expresion, str) and expresion.strip():
            expresiones.append(expresion)
    return expresiones


def _paneles(datos: dict[str, Any]) -> list[dict[str, Any]]:
    """Devuelve todos los paneles del tablero o una lista vacia si no hay."""
    paneles = datos.get("panels")
    if not isinstance(paneles, list):
        return []
    return _aplanar_paneles(paneles)


def _pares_expresion(
    paneles: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], str]]:
    """Empareja cada panel con cada una de sus expresiones PromQL."""
    pares: list[tuple[dict[str, Any], str]] = []
    for panel in paneles:
        for expresion in _expresiones_panel(panel):
            pares.append((panel, expresion))
    return pares


def extraer_expresion_sli(datos: dict[str, Any]) -> str | None:
    """Devuelve la consulta del panel cuyo titulo identifica al SLI."""
    for panel in _paneles(datos):
        titulo = normalizar_texto(str(panel.get("title", "")))
        if "sli" not in titulo:
            continue
        expresiones = _expresiones_panel(panel)
        if expresiones:
            return expresiones[0]
    return None


def validar_dashboard(datos: dict[str, Any]) -> list[str]:
    """Valida la estructura, las consultas y los titulos del tablero."""
    errores: list[str] = []

    if datos.get("uid") != UID_DASHBOARD:
        errores.append(f'El dashboard debe tener uid "{UID_DASHBOARD}".')

    paneles = _paneles(datos)
    paneles_datos = [panel for panel in paneles if panel.get("type") != "row"]
    if len(paneles_datos) < MINIMO_PANELES_DATOS:
        errores.append(
            "El dashboard debe tener al menos "
            f"{MINIMO_PANELES_DATOS} paneles de datos; tiene {len(paneles_datos)}."
        )

    titulos = " | ".join(normalizar_texto(str(panel.get("title", ""))) for panel in paneles)
    faltantes = [
        nombre
        for nombre, alternativas in TITULOS_MINIMOS.items()
        if not any(alternativa in titulos for alternativa in alternativas)
    ]
    if faltantes:
        errores.append("Faltan titulos minimos en el dashboard: " + ", ".join(faltantes) + ".")

    templating = datos.get("templating")
    variables = templating.get("list") if isinstance(templating, dict) else None
    if not isinstance(variables, list) or not any(
        isinstance(variable, dict)
        and variable.get("name") == "datasource"
        and variable.get("type") == "datasource"
        for variable in variables
    ):
        errores.append("Falta la variable de plantilla 'datasource' de tipo datasource.")

    pares = _pares_expresion(paneles)
    if not any("http_target" in expresion for _, expresion in pares):
        errores.append("Ninguna consulta HTTP usa la etiqueta http_target.")
    for panel, expresion in pares:
        if "http_route" in expresion:
            titulo = panel.get("title", "sin titulo")
            errores.append(
                f"La consulta del panel '{titulo}' usa http_route en vez de http_target."
            )

    expresion_sli = extraer_expresion_sli(datos)
    if expresion_sli is None:
        errores.append("Falta el panel del SLI con una consulta PromQL.")
    else:
        for fragmento in FRAGMENTOS_SLI:
            if fragmento not in expresion_sli:
                errores.append(f"La consulta SLI no contiene el fragmento obligatorio {fragmento}.")

    return errores


def _reglas_de_grupos(datos: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Aplana las reglas de todos los grupos y valida la estructura basica."""
    errores: list[str] = []
    grupos = datos.get("groups")
    if not isinstance(grupos, list) or not grupos:
        return [], ["Las reglas deben tener una lista 'groups' no vacia."]

    reglas: list[dict[str, Any]] = []
    for indice, grupo in enumerate(grupos):
        if not isinstance(grupo, dict):
            errores.append(f"El grupo {indice} de reglas no es un objeto YAML.")
            continue
        if not grupo.get("name"):
            errores.append(f"El grupo {indice} de reglas no tiene 'name'.")
        lista_reglas = grupo.get("rules")
        if not isinstance(lista_reglas, list) or not lista_reglas:
            errores.append(f"El grupo {indice} de reglas no tiene una lista 'rules' no vacia.")
            continue
        for regla in lista_reglas:
            if not isinstance(regla, dict):
                errores.append(f"El grupo {indice} contiene una regla que no es un objeto YAML.")
                continue
            if ("record" in regla) == ("alert" in regla):
                errores.append("Cada regla debe declarar exactamente uno de 'record' o 'alert'.")
                continue
            reglas.append(regla)
    return reglas, errores


def _validar_alerta(regla: dict[str, Any]) -> list[str]:
    """Valida los campos obligatorios de una alerta."""
    nombre = regla.get("alert", "sin nombre")
    errores: list[str] = []

    expresion = regla.get("expr")
    if not isinstance(expresion, str) or not expresion.strip():
        errores.append(f"La alerta '{nombre}' no tiene una expresion 'expr'.")
    if not regla.get("for"):
        errores.append(f"La alerta '{nombre}' no declara 'for'.")

    labels = regla.get("labels")
    if not isinstance(labels, dict) or not labels.get("severity"):
        errores.append(f"La alerta '{nombre}' no declara labels.severity.")

    annotations = regla.get("annotations")
    if not isinstance(annotations, dict):
        errores.append(
            f"La alerta '{nombre}' no declara annotations.summary ni annotations.description."
        )
        return errores
    if not annotations.get("summary"):
        errores.append(f"La alerta '{nombre}' no declara annotations.summary.")
    if not annotations.get("description"):
        errores.append(f"La alerta '{nombre}' no declara annotations.description.")
    return errores


def validar_reglas(
    datos: dict[str, Any],
    expresion_sli_dashboard: str | None = None,
) -> list[str]:
    """Valida la regla de grabacion del SLI y las alertas versionadas."""
    reglas, errores = _reglas_de_grupos(datos)

    grabaciones = [regla for regla in reglas if "record" in regla]
    alertas = [regla for regla in reglas if "alert" in regla]
    if not alertas:
        errores.append("No hay ninguna regla de tipo 'alert'.")

    grabacion_sli = next(
        (regla for regla in grabaciones if regla.get("record") == REGLA_SLI),
        None,
    )
    if grabacion_sli is None:
        errores.append(f"Falta la regla de grabacion '{REGLA_SLI}'.")
    else:
        expresion = grabacion_sli.get("expr")
        if not isinstance(expresion, str) or not expresion.strip():
            errores.append(f"La regla de grabacion '{REGLA_SLI}' no tiene una expresion.")
        elif expresion_sli_dashboard is not None and normalizar_expresion(
            expresion
        ) != normalizar_expresion(expresion_sli_dashboard):
            errores.append(
                f"La regla de grabacion '{REGLA_SLI}' no coincide exactamente con "
                "la consulta SLI del dashboard."
            )

    for alerta in alertas:
        errores.extend(_validar_alerta(alerta))

    alerta_slo = next((alerta for alerta in alertas if alerta.get("alert") == ALERTA_SLO), None)
    if alerta_slo is None:
        errores.append(f"Falta la alerta principal '{ALERTA_SLO}'.")
    elif REGLA_SLI not in str(alerta_slo.get("expr", "")):
        errores.append(f"La alerta principal '{ALERTA_SLO}' no usa '{REGLA_SLI}'.")

    return errores


def validar_texto_sin_secretos(texto: str, nombre_artefacto: str) -> list[str]:
    """Detecta patrones de credenciales sin revelar el valor encontrado."""
    return [
        f"Posible secreto detectado en {nombre_artefacto} (patron: {nombre})."
        for nombre, patron in PATRONES_SECRETO
        if patron.search(texto)
    ]


def validar_sin_urls_grafana(texto: str, nombre_artefacto: str) -> list[str]:
    """Detecta endpoints de Grafana Cloud en las reglas versionadas."""
    return [
        f"URL de Grafana detectada en {nombre_artefacto} (patron: {nombre})."
        for nombre, patron in PATRONES_URL_GRAFANA
        if patron.search(texto)
    ]


def validar_artefactos(ruta_dashboard: Path, ruta_reglas: Path) -> list[str]:
    """Valida ambos artefactos y devuelve la lista de problemas encontrados."""
    errores: list[str] = []
    dashboard: dict[str, Any] | None = None
    reglas: dict[str, Any] | None = None
    texto_dashboard = ""
    texto_reglas = ""

    try:
        dashboard = cargar_json(ruta_dashboard)
        texto_dashboard = ruta_dashboard.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        errores.append(f"No se pudo cargar el dashboard {ruta_dashboard}: {exc}")

    try:
        reglas = cargar_yaml(ruta_reglas)
        texto_reglas = ruta_reglas.read_text(encoding="utf-8")
    except (OSError, ValueError, RuntimeError) as exc:
        errores.append(f"No se pudieron cargar las reglas {ruta_reglas}: {exc}")

    if dashboard is not None:
        errores.extend(validar_dashboard(dashboard))
        errores.extend(validar_texto_sin_secretos(texto_dashboard, "el dashboard"))

    if reglas is not None:
        expresion_sli = extraer_expresion_sli(dashboard) if dashboard is not None else None
        errores.extend(validar_reglas(reglas, expresion_sli))
        errores.extend(validar_texto_sin_secretos(texto_reglas, "las reglas"))
        errores.extend(validar_sin_urls_grafana(texto_reglas, "las reglas"))

    return errores


def main(argv: list[str] | None = None) -> int:
    """Ejecuta la validacion y devuelve 0 si todo es correcto o 1 si falla."""
    parser = argparse.ArgumentParser(description="Valida los artefactos de observabilidad.")
    parser.add_argument(
        "--dashboard",
        type=Path,
        default=RUTA_DASHBOARD,
        help="Ruta del JSON del tablero de Grafana.",
    )
    parser.add_argument(
        "--reglas",
        type=Path,
        default=RUTA_REGLAS,
        help="Ruta del YAML de reglas de Prometheus/Mimir.",
    )
    argumentos = parser.parse_args(argv)

    errores = validar_artefactos(argumentos.dashboard, argumentos.reglas)
    print("Validacion de artefactos de observabilidad (T-122)")
    print(f"  Dashboard: {argumentos.dashboard}")
    print(f"  Reglas:    {argumentos.reglas}")

    if errores:
        for error in errores:
            print(f"[ERROR] {error}")
        print(f"[FALLO] {len(errores)} problema(s) detectado(s).")
        return 1

    print("[OK] Dashboard valido, reglas de SLO/alertas validas y sin secretos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
