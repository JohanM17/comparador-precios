"""Pruebas unitarias del cableado de `OficialConContraste` en Etapa 2 (D-01).

No tocan base de datos: verifican la politica por defecto de los servicios y que la
reconstruccion conserve los pares que solo tienen precio oficial.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import pytest

from app.dominio.parametros import ParametrosDominio
from app.modulos.moderacion.servicio_casos import ServicioCasosModeracion
from app.modulos.precios.servicio import ServicioPrecios
from app.puertos import politica_precio as politica_modulo
from app.puertos.politica_precio import OficialConContraste

PRESENTACION_OFICIAL = UUID(int=10)
ESTABLECIMIENTO_OFICIAL = UUID(int=11)
PRESENTACION_OBSOLETA = UUID(int=12)
ESTABLECIMIENTO_OBSOLETO = UUID(int=13)


def test_servicio_precios_usa_oficial_con_contraste_por_defecto() -> None:
    """Registrar un reporte comunitario debe contrastar con el precio oficial."""
    servicio = ServicioPrecios(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=object(),  # type: ignore[arg-type]
        servicio_confianza=object(),  # type: ignore[arg-type]
    )

    assert isinstance(servicio.politica, OficialConContraste)


def test_servicio_casos_usa_oficial_con_contraste_por_defecto() -> None:
    """Resolver un caso o recalcular a mano no puede volver a la politica de Etapa 1."""
    servicio = ServicioCasosModeracion(
        sesion=object(),  # type: ignore[arg-type]
        cache=object(),  # type: ignore[arg-type]
    )

    assert isinstance(servicio.politica, OficialConContraste)


async def test_reconstruccion_usa_oficial_con_contraste_por_defecto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El job y las llamadas sin politica explicita usan la regla de Etapa 2."""
    capturada: dict[str, Any] = {}

    async def reconstruir_falso(
        sesion: Any,
        pol: Any,
        limite_inferior: datetime,
        instante: datetime,
        parametros: ParametrosDominio,
    ) -> int:
        capturada["politica"] = pol
        return 0

    async def obtener_parametros(sesion: Any) -> ParametrosDominio:
        return ParametrosDominio()

    monkeypatch.setattr(
        politica_modulo,
        "_reconstruir_con_politica_personalizada",
        reconstruir_falso,
    )
    monkeypatch.setattr(
        politica_modulo,
        "obtener_parametros_dominio",
        obtener_parametros,
    )

    await politica_modulo.reconstruir_precio_vigente(object())  # type: ignore[arg-type]

    assert isinstance(capturada["politica"], OficialConContraste)


class ResultadoFalso:
    """Resultado minimo de una consulta SQL para la sesion falsa."""

    def __init__(self, filas: list[tuple[UUID, UUID]]) -> None:
        self._filas = filas

    def fetchall(self) -> list[tuple[UUID, UUID]]:
        return self._filas


class SesionFalsa:
    """Sesion que solo entiende el SELECT y el DELETE de la reconstruccion."""

    def __init__(self, filas_precio_vigente: list[tuple[UUID, UUID]]) -> None:
        self._filas_precio_vigente = filas_precio_vigente
        self.borrados: list[list[dict[str, UUID]]] = []

    async def execute(
        self,
        sentencia: Any,
        parametros: Any = None,
    ) -> ResultadoFalso | None:
        if parametros is None:
            return ResultadoFalso(self._filas_precio_vigente)
        self.borrados.append(parametros)
        return None


class PoliticaFalsa:
    """Devuelve un resultado para cada par, como una politica con datos."""

    async def recalcular_par(
        self,
        sesion: Any,
        presentacion_id: UUID,
        establecimiento_id: UUID,
        ahora: datetime | None = None,
        params: ParametrosDominio | None = None,
    ) -> object:
        return object()


async def test_reconstruccion_conserva_el_par_que_solo_tiene_precio_oficial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un par oficial sin reportes comunitarios se recalcula y no se borra."""
    sesion = SesionFalsa(
        [
            (PRESENTACION_OFICIAL, ESTABLECIMIENTO_OFICIAL),
            (PRESENTACION_OBSOLETA, ESTABLECIMIENTO_OBSOLETO),
        ]
    )

    async def listar_pares(sesion_falsa: Any, limite_inferior: datetime) -> list[tuple[UUID, UUID]]:
        return [(PRESENTACION_OFICIAL, ESTABLECIMIENTO_OFICIAL)]

    monkeypatch.setattr(politica_modulo, "listar_pares_para_recalculo", listar_pares)

    recalculados = await politica_modulo._reconstruir_con_politica_personalizada(
        sesion,  # type: ignore[arg-type]
        PoliticaFalsa(),  # type: ignore[arg-type]
        datetime(2026, 11, 27),
        datetime(2026, 11, 27),
        ParametrosDominio(),
    )

    assert recalculados == 1
    assert sesion.borrados == [[{"p": PRESENTACION_OBSOLETA, "e": ESTABLECIMIENTO_OBSOLETO}]]
