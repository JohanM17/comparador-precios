"""Pruebas unitarias del script de integracion aislada.

No tocan base de datos: verifican la construccion del comando de pytest, la
validacion del cluster Supabase y las decisiones puras de seguridad.
"""

from __future__ import annotations

import sys

import pytest

from scripts.integracion_aislada import (
    _ref_de_supabase,
    _ref_del_usuario_bd,
    construir_comando_pytest,
    validar_cluster,
)

URL_BD = (
    "postgresql://postgres.dohoqojhrxlduswekkwn:secreto"
    "@aws-1-us-east-2.pooler.supabase.com:5432/postgres"
)
URL_SUPABASE = "https://dohoqojhrxlduswekkwn.supabase.co"


def test_sin_target_ejecuta_toda_la_suite() -> None:
    """Sin archivo ni node id, el target por defecto sigue siendo la suite entera."""
    comando = construir_comando_pytest(["--maxfail=1"])

    assert comando == [
        sys.executable,
        "-m",
        "pytest",
        "tests/integracion",
        "-q",
        "--maxfail=1",
    ]


def test_con_archivo_no_antepone_el_directorio() -> None:
    """Un archivo explicito ejecuta solo ese archivo, no toda la suite."""
    comando = construir_comando_pytest(["-q", "tests/integracion/test_x.py"])

    assert "tests/integracion" not in comando
    assert comando[-1] == "tests/integracion/test_x.py"
    assert "-q" in comando


def test_con_node_id_no_antepone_el_directorio() -> None:
    """Un node id conserva la seleccion exacta de la prueba."""
    comando = construir_comando_pytest(["tests/integracion/test_x.py::test_y"])

    assert "tests/integracion" not in comando
    assert comando[-1] == "tests/integracion/test_x.py::test_y"


def test_con_k_sin_target_ejecuta_la_suite_completa() -> None:
    """El valor de `-k` no es un target: se sigue filtrando sobre toda la suite."""
    comando = construir_comando_pytest(["-k", "disputa"])

    assert comando == [
        sys.executable,
        "-m",
        "pytest",
        "tests/integracion",
        "-q",
        "-k",
        "disputa",
    ]


def test_el_separador_doble_no_llega_a_pytest() -> None:
    """El `--` del script es un separador, no un argumento de pytest."""
    comando = construir_comando_pytest(["--", "-q", "tests/integracion/test_x.py"])

    assert "--" not in comando
    assert comando[-1] == "tests/integracion/test_x.py"


def test_extrae_el_project_ref_de_supabase_y_de_la_url_de_bd() -> None:
    assert _ref_de_supabase(URL_SUPABASE) == "dohoqojhrxlduswekkwn"
    assert _ref_del_usuario_bd(URL_BD) == "dohoqojhrxlduswekkwn"


def test_valida_el_cluster_y_no_expone_la_contrasena(capsys: pytest.CaptureFixture[str]) -> None:
    """La validacion muestra el host ofuscado, nunca la contrasena."""
    ref = validar_cluster(URL_BD, URL_SUPABASE)

    assert ref == "dohoqojhrxlduswekkwn"
    salida = capsys.readouterr().out
    assert "dohoqojhrxlduswekkwn" in salida
    assert "secreto" not in salida


def test_aborta_si_el_cluster_de_la_bd_no_coincide() -> None:
    with pytest.raises(SystemExit):
        validar_cluster(URL_BD, "https://otro.supabase.co")


def test_aborta_si_falta_supabase_url() -> None:
    with pytest.raises(SystemExit):
        validar_cluster(URL_BD, None)


def test_aborta_si_la_url_de_bd_no_usa_postgres_ref() -> None:
    with pytest.raises(SystemExit):
        validar_cluster(
            "postgresql://postgres:secreto@db.example.com:5432/postgres",
            URL_SUPABASE,
        )
