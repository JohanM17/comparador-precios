"""Coherencia entre el SQL compartido y los diccionarios de parametros (T-64).

Al unificar el UPSERT de `precio_vigente` en una sola sentencia para las dos politicas
(`SoloUsuarios` y `OficialConContraste`) aparece un riesgo concreto: que el SQL espere un
parametro con un nombre y el constructor de la fila entregue otro. Ese desajuste no lo detecta
ni mypy ni ruff, y solo se manifiesta contra una base de datos real.

Estas pruebas comparan los nombres de los parametros declarados en cada sentencia con las
claves que arma el codigo, sin necesidad de base de datos.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.sql.elements import TextClause

from app.dominio.contraste import ResultadoContraste
from app.dominio.sello import ResultadoSelloYPrecio
from app.puertos.politica_precio import (
    _SQL_DELETE_PV,
    _SQL_DELETE_PV_FUERA_DE,
    _SQL_PARES_RECALCULO,
    _SQL_PRECIO_OFICIAL_PAR,
    _SQL_REPORTES_PAR,
    _SQL_UPSERT_PV,
    _fila_precio_vigente,
)

# Un solo dos puntos introduce un parametro; dos seguidos son un cast de PostgreSQL.
_PARAMETRO = re.compile(r"(?<!:):(\w+)")


def _parametros(sentencia: TextClause) -> set[str]:
    """Nombres de los parametros declarados en una sentencia de texto."""
    return set(_PARAMETRO.findall(str(sentencia)))


def _sql_compacto(sentencia: TextClause) -> str:
    """Normaliza espacios y mayusculas para comparar fragmentos del SQL."""
    return " ".join(str(sentencia).lower().split())


def _resultado_ejemplo() -> ResultadoSelloYPrecio:
    return ResultadoSelloYPrecio(
        sello="confiable",
        motivo_sello=None,
        precio_cop=2600,
        precio_por_base=Decimal("2.600000"),
        cantidad_base=Decimal("1000.000"),
        n_reportes_validos=4,
        n_fuentes=3,
        dispersion=0.02,
        ultimo_reporte_en=datetime(2026, 11, 26, tzinfo=UTC),
        reporte_origen_id=uuid4(),
    )


def test_el_upsert_recibe_exactamente_los_parametros_que_declara() -> None:
    fila = _fila_precio_vigente(uuid4(), uuid4(), uuid4(), _resultado_ejemplo())

    assert _parametros(_SQL_UPSERT_PV) == set(fila.keys())


def test_el_upsert_tambien_cuadra_cuando_viene_el_contraste_comercial() -> None:
    contraste = ResultadoContraste(
        resultado=_resultado_ejemplo(),
        precio_oficial_cop=3050,
        diferencia_pct=Decimal("0.1475"),
        requiere_revalidacion=False,
        hay_disputa=True,
    )
    fila = _fila_precio_vigente(uuid4(), uuid4(), uuid4(), contraste.resultado, contraste)

    assert _parametros(_SQL_UPSERT_PV) == set(fila.keys())
    assert fila["precio_oficial_cop"] == 3050
    assert fila["diferencia_pct"] == Decimal("0.1475")
    assert fila["requiere_revalidacion"] is False


def test_sin_contraste_las_columnas_comerciales_quedan_vacias() -> None:
    fila = _fila_precio_vigente(uuid4(), uuid4(), uuid4(), _resultado_ejemplo())

    assert fila["precio_oficial_cop"] is None
    assert fila["diferencia_pct"] is None
    assert fila["requiere_revalidacion"] is False


def test_las_sentencias_auxiliares_declaran_los_parametros_esperados() -> None:
    assert _parametros(_SQL_DELETE_PV) == {"pres_id", "est_id"}
    assert _parametros(_SQL_DELETE_PV_FUERA_DE) == {"pares"}
    assert _parametros(_SQL_REPORTES_PAR) == {"pres_id", "est_id", "limite"}
    assert _parametros(_SQL_PRECIO_OFICIAL_PAR) == {"pres_id", "est_id"}
    assert _parametros(_SQL_PARES_RECALCULO) == {"limite"}


def test_las_consultas_comunitarias_excluyen_el_historial_oficial() -> None:
    """La fila `fuente='comercio'` de ADR-0019 no puede contar como voto comunitario."""
    assert "fuente <> 'comercio'" in _sql_compacto(_SQL_REPORTES_PAR)
    assert "fuente <> 'comercio'" in _sql_compacto(_SQL_PARES_RECALCULO)


def test_los_pares_de_reconstruccion_incluyen_el_precio_oficial_activo() -> None:
    """Reconstruir no puede olvidar un par que solo tiene precio del comercio."""
    sql = _sql_compacto(_SQL_PARES_RECALCULO)

    assert "union" in sql
    assert "from public.precio_oficial" in sql
    assert "where activo = true" in sql
