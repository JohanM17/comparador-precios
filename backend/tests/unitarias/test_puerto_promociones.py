"""Pruebas del puerto de promociones sin base de datos (EC-06, FR-025).

Lo que se protege aqui es la frontera: la comparacion lee las promociones por un puerto,
nunca importando el modulo comercial, y todo elemento sale marcado como contenido comercial
para que ninguna capa de arriba lo pueda confundir con un resultado de la comparacion.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.puertos.promociones import (
    _SQL_PROMOCIONES_VIGENTES,
    PromocionesPublicadas,
    SinPromociones,
)

AHORA = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
_PARAMETRO = re.compile(r"(?<!:):(\w+)")


class _FilaFalsa:
    """Imita lo justo de una fila de SQLAlchemy: su mapeo a diccionario."""

    def __init__(self, datos: dict[str, Any]) -> None:
        self._mapping = datos


class _ResultadoFalso:
    def __init__(self, filas: list[_FilaFalsa]) -> None:
        self._filas = filas

    def fetchall(self) -> list[_FilaFalsa]:
        return self._filas


class _SesionFalsa:
    """Sesion que no habla con ninguna base de datos y recuerda lo que le pidieron."""

    def __init__(self, filas: list[dict[str, Any]]) -> None:
        self.filas = [_FilaFalsa(f) for f in filas]
        self.parametros: dict[str, Any] = {}

    async def execute(self, _sentencia: Any, parametros: dict[str, Any]) -> _ResultadoFalso:
        self.parametros = parametros
        return _ResultadoFalso(self.filas)


@pytest.mark.asyncio
async def test_la_etapa_1_no_devuelve_promociones() -> None:
    sesion = _SesionFalsa([{"id": uuid4(), "titulo": "No deberia salir"}])

    promos = await SinPromociones().listar_vigentes(sesion, uuid4(), AHORA)  # type: ignore[arg-type]

    assert promos == []


@pytest.mark.asyncio
async def test_toda_promocion_sale_marcada_como_contenido_comercial() -> None:
    sesion = _SesionFalsa(
        [
            {"id": uuid4(), "titulo": "20 % en arroz", "tipo": "porcentaje"},
            {"id": uuid4(), "titulo": "Pague 2 lleve 3", "tipo": "pague_x_lleve_y"},
        ]
    )

    promos = await PromocionesPublicadas().listar_vigentes(sesion, uuid4(), AHORA)  # type: ignore[arg-type]

    assert len(promos) == 2
    assert all(p["es_promocion"] is True for p in promos)


@pytest.mark.asyncio
async def test_la_consulta_filtra_por_producto_y_por_instante() -> None:
    sesion = _SesionFalsa([])
    producto_id = uuid4()

    await PromocionesPublicadas().listar_vigentes(sesion, producto_id, AHORA)  # type: ignore[arg-type]

    assert sesion.parametros["pid"] == producto_id
    assert sesion.parametros["ahora"] == AHORA
    assert sesion.parametros["limite"] > 0


def test_la_consulta_declara_exactamente_los_parametros_que_recibe() -> None:
    assert set(_PARAMETRO.findall(str(_SQL_PROMOCIONES_VIGENTES))) == {"pid", "ahora", "limite"}
