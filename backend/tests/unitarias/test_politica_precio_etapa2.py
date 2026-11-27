"""Pruebas unitarias del cableado de `OficialConContraste` en Etapa 2 (D-01).

No tocan base de datos: verifican la politica por defecto de los servicios y que la
reconstruccion conserve los pares que solo tienen precio oficial.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from app.dominio.parametros import ParametrosDominio
from app.modulos.moderacion import servicio_casos as servicio_casos_modulo
from app.modulos.moderacion.servicio_casos import ServicioCasosModeracion
from app.modulos.precios.servicio import ServicioPrecios
from app.puertos import politica_precio as politica_modulo
from app.puertos.politica_precio import OficialConContraste

PRESENTACION_OFICIAL = UUID(int=10)
ESTABLECIMIENTO_OFICIAL = UUID(int=11)
PRESENTACION_OBSOLETA = UUID(int=12)
ESTABLECIMIENTO_OBSOLETO = UUID(int=13)
PRODUCTO_OFICIAL = UUID(int=14)
CONFIRMADO_EN = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


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
    """El job y las llamadas sin politica explicita usan la ruta batch de Etapa 2."""
    capturada: dict[str, Any] = {}

    async def reconstruir_falso(
        sesion: Any,
        limite_inferior: datetime,
        instante: datetime,
        parametros: ParametrosDominio,
    ) -> int:
        capturada["ruta"] = "lote"
        return 0

    async def obtener_parametros(sesion: Any) -> ParametrosDominio:
        return ParametrosDominio()

    monkeypatch.setattr(
        politica_modulo,
        "_reconstruir_oficial_con_contraste",
        reconstruir_falso,
    )
    monkeypatch.setattr(
        politica_modulo,
        "obtener_parametros_dominio",
        obtener_parametros,
    )

    await politica_modulo.reconstruir_precio_vigente(object())  # type: ignore[arg-type]

    assert capturada["ruta"] == "lote"


class SesionFalsa:
    """Sesion que solo entiende el DELETE final de la reconstruccion."""

    def __init__(self) -> None:
        self.borrados: list[list[dict[str, str]]] = []

    async def execute(
        self,
        sentencia: Any,
        parametros: Any = None,
    ) -> None:
        assert isinstance(parametros, dict)
        self.borrados.append(json.loads(parametros["pares"]))


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
    sesion = SesionFalsa()

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
    assert sesion.borrados == [
        [{"pres_id": str(PRESENTACION_OFICIAL), "est_id": str(ESTABLECIMIENTO_OFICIAL)}]
    ]


class ResultadoConsulta:
    """Resultado de consulta con filas o con una sola fila."""

    def __init__(
        self,
        filas: list[Any] | None = None,
        fila: Any = None,
    ) -> None:
        self._filas = filas or []
        self._fila = fila

    def fetchall(self) -> list[Any]:
        return self._filas

    def fetchone(self) -> Any:
        return self._fila

    def first(self) -> Any:
        return self._fila


class SesionSoloOficial:
    """Sesion falsa que responde como una base con solo el precio oficial."""

    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.borrados: list[list[dict[str, str]]] = []

    async def execute(
        self,
        sentencia: Any,
        parametros: Any = None,
    ) -> ResultadoConsulta:
        sql = " ".join(str(sentencia).lower().split())
        if sql.startswith("insert into public.precio_vigente"):
            self.upserts.append(parametros)
            return ResultadoConsulta()
        if "from public.reporte_precio" in sql:
            return ResultadoConsulta(filas=[])
        if "max(c.resuelto_en)" in sql:
            return ResultadoConsulta(fila=SimpleNamespace(corte=None))
        if "from public.precio_oficial po" in sql:
            return ResultadoConsulta(
                fila=SimpleNamespace(
                    precio_cop=2500,
                    revalidado_en=CONFIRMADO_EN,
                    cantidad_base=Decimal("1000.000"),
                )
            )
        if "select producto_id from public.precio_oficial" in sql:
            return ResultadoConsulta(fila=SimpleNamespace(producto_id=PRODUCTO_OFICIAL))
        if sql.startswith("delete from public.precio_vigente"):
            assert isinstance(parametros, dict)
            self.borrados.append(json.loads(parametros["pares"]))
            return ResultadoConsulta()
        raise AssertionError(f"SQL inesperado: {sql}")


async def test_oficial_con_contraste_real_recalcula_y_conserva_el_par_sin_reportes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con solo `precio_oficial`, la politica real crea la proyeccion y no la borra."""
    sesion = SesionSoloOficial()

    async def listar_pares(sesion_falsa: Any, limite_inferior: datetime) -> list[tuple[UUID, UUID]]:
        return [(PRESENTACION_OFICIAL, ESTABLECIMIENTO_OFICIAL)]

    monkeypatch.setattr(politica_modulo, "listar_pares_para_recalculo", listar_pares)

    recalculados = await politica_modulo._reconstruir_con_politica_personalizada(
        sesion,  # type: ignore[arg-type]
        OficialConContraste(),
        datetime(2026, 11, 27, tzinfo=UTC),
        datetime(2026, 11, 27, tzinfo=UTC),
        ParametrosDominio(),
    )

    assert recalculados == 1
    assert len(sesion.upserts) == 1
    assert sesion.upserts[0]["precio_cop"] == 2500
    assert sesion.upserts[0]["precio_oficial_cop"] == 2500
    assert sesion.upserts[0]["sello"] == "oficial"
    assert sesion.borrados == [
        [{"pres_id": str(PRESENTACION_OFICIAL), "est_id": str(ESTABLECIMIENTO_OFICIAL)}]
    ]


class PoliticaConResultadosParciales:
    """Devuelve resultado solo para el segundo par."""

    def __init__(self) -> None:
        self.llamadas = 0

    async def recalcular_par(
        self,
        sesion: Any,
        presentacion_id: UUID,
        establecimiento_id: UUID,
        ahora: datetime | None = None,
        params: ParametrosDominio | None = None,
    ) -> object | None:
        self.llamadas += 1
        return None if self.llamadas == 1 else object()


class CacheFalsa:
    async def limpiar(self) -> None:
        return None


class SesionConFlush:
    async def flush(self) -> None:
        return None


async def test_recalculo_manual_cuenta_solo_los_resultados_no_nulos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`recalculados` refleja lo que la politica pudo resolver, no el total de pares."""
    pares = [
        (PRESENTACION_OFICIAL, ESTABLECIMIENTO_OFICIAL),
        (PRESENTACION_OBSOLETA, ESTABLECIMIENTO_OBSOLETO),
    ]

    async def obtener_parametros(sesion: Any) -> ParametrosDominio:
        return ParametrosDominio()

    async def listar_pares(sesion: Any, limite: datetime) -> list[tuple[UUID, UUID]]:
        return pares

    monkeypatch.setattr(
        servicio_casos_modulo,
        "obtener_parametros_dominio",
        obtener_parametros,
    )
    monkeypatch.setattr(
        servicio_casos_modulo,
        "listar_pares_para_recalculo",
        listar_pares,
    )
    servicio = ServicioCasosModeracion(
        sesion=SesionConFlush(),  # type: ignore[arg-type]
        cache=CacheFalsa(),  # type: ignore[arg-type]
        politica=PoliticaConResultadosParciales(),  # type: ignore[arg-type]
    )

    resultado = await servicio.recalcular_precio_vigente_manual(object())  # type: ignore[arg-type]

    assert resultado == {"recalculados": 1}
