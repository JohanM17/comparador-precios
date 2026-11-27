"""Pruebas unitarias de la reconstruccion por lotes de `precio_vigente` (rendimiento).

La ruta batch de `OficialConContraste` lee reportes, oficiales y cortes en tres
consultas, decide en memoria y escribe todo con un unico UPSERT. Estas pruebas no
tocan base de datos: usan una sesion falsa que responde a cada sentencia y registra
cuantas veces se ejecuta el UPSERT. El objetivo es que el lote siga produciendo
exactamente las mismas filas que la ruta par a par, pero sin pagar el costo de
consulta por cada par.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from app.dominio.parametros import ParametrosDominio
from app.puertos import politica_precio as politica_modulo
from app.puertos.politica_precio import (
    _SQL_CORTES_CONFIRMADOS_LOTE,
    _SQL_DELETE_PV_FUERA_DE,
    _SQL_OFICIALES_LOTE,
    _SQL_REPORTES_LOTE,
    _SQL_REPORTES_PAR,
    OficialConContraste,
    SoloUsuarios,
    _serializar_pares_activos,
    reconstruir_precio_vigente,
)

AHORA = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
LIMITE = AHORA - timedelta(days=30)
PRODUCTO = UUID(int=100)

PAR_SOLO_OFICIAL = (UUID(int=1), UUID(int=2))
PAR_SOLO_COMUNIDAD = (UUID(int=3), UUID(int=4))
PAR_MIXTO = (UUID(int=5), UUID(int=6))
PAR_SIN_CONTRASTE = (UUID(int=7), UUID(int=8))


class ResultadoConsulta:
    """Resultado minimo de una sentencia para la sesion falsa."""

    def __init__(self, filas: list[Any] | None = None) -> None:
        self._filas = filas or []

    def fetchall(self) -> list[Any]:
        return self._filas

    def fetchone(self) -> Any:
        return None

    def first(self) -> Any:
        return None


class _SavepointFalso:
    """Context manager que imita `AsyncSession.begin_nested()`."""

    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion

    async def __aenter__(self) -> Any:
        return self._sesion

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _reporte(
    par: tuple[UUID, UUID],
    precio_cop: int,
    *,
    observado_en: datetime | None = None,
    estado: str = "aceptado",
    fuente: str = "usuario",
    autor_id: UUID | None = None,
) -> Any:
    """Fila de `reporte_precio` con la forma que devuelve `_SQL_REPORTES_LOTE`."""
    return SimpleNamespace(
        id=uuid4(),
        presentacion_id=par[0],
        establecimiento_id=par[1],
        producto_id=PRODUCTO,
        precio_cop=precio_cop,
        cantidad_base_snapshot=Decimal("1000.000"),
        observado_en=observado_en if observado_en is not None else AHORA - timedelta(hours=1),
        reportante_id=autor_id if autor_id is not None else uuid4(),
        fuente=fuente,
        foto_prueba_path=None,
        estado=estado,
    )


def _oficial(
    par: tuple[UUID, UUID],
    precio_cop: int = 3000,
    *,
    confirmado_en: datetime | None = None,
) -> Any:
    """Fila de `precio_oficial` activo con la forma que devuelve `_SQL_OFICIALES_LOTE`."""
    return SimpleNamespace(
        presentacion_id=par[0],
        establecimiento_id=par[1],
        producto_id=PRODUCTO,
        precio_cop=precio_cop,
        revalidado_en=(confirmado_en if confirmado_en is not None else AHORA - timedelta(days=1)),
        cantidad_base=Decimal("1000.000"),
    )


def _corte(par: tuple[UUID, UUID], corte: datetime) -> Any:
    """Fila agregada por par de `_SQL_CORTES_CONFIRMADOS_LOTE`."""
    return SimpleNamespace(referencia_id=par[0], est_id_txt=str(par[1]), corte=corte)


class SesionLoteFalsa:
    """Sesion que responde a las tres consultas del lote y registra las escrituras."""

    def __init__(
        self,
        *,
        reportes: list[Any] | None = None,
        oficiales: list[Any] | None = None,
        cortes: list[Any] | None = None,
    ) -> None:
        self.reportes = reportes or []
        self.oficiales = oficiales or []
        self.cortes = cortes or []
        self.consultas: list[str] = []
        self.upserts: list[list[dict[str, Any]]] = []
        self.casos: list[dict[str, Any]] = []
        self.borrados: list[list[dict[str, str]]] = []

    def begin_nested(self) -> _SavepointFalso:
        return _SavepointFalso(self)

    async def execute(self, sentencia: Any, parametros: Any = None) -> ResultadoConsulta:
        sql = " ".join(str(sentencia).lower().split())
        if sql.startswith("insert into public.precio_vigente"):
            assert isinstance(parametros, dict), "el lote debe escribirse en un solo INSERT"
            assert isinstance(parametros["lote"], str)
            self.upserts.append(json.loads(parametros["lote"]))
            return ResultadoConsulta()
        if sql.startswith("insert into public.caso_moderacion"):
            assert isinstance(parametros, dict)
            self.casos.append(parametros)
            return ResultadoConsulta()
        if "from public.reporte_precio" in sql:
            self.consultas.append("reportes")
            return ResultadoConsulta(filas=self.reportes)
        if "from public.precio_oficial po" in sql:
            self.consultas.append("oficiales")
            return ResultadoConsulta(filas=self.oficiales)
        if "max(c.resuelto_en)" in sql:
            self.consultas.append("cortes")
            return ResultadoConsulta(filas=self.cortes)
        if sql.startswith("delete from public.precio_vigente"):
            assert isinstance(parametros, dict), "el borrado debe ser una sola sentencia"
            assert isinstance(parametros["pares"], str)
            self.borrados.append(json.loads(parametros["pares"]))
            return ResultadoConsulta()
        raise AssertionError(f"SQL inesperado: {sql}")


def _fila_por_par(lote: list[dict[str, Any]], par: tuple[UUID, UUID]) -> dict[str, Any]:
    """Busca la fila del par en el lote JSON enviado al UPSERT."""
    return next(f for f in lote if UUID(f["pres_id"]) == par[0] and UUID(f["est_id"]) == par[1])


async def test_el_lote_incluye_oficial_comunidad_y_mixto_en_un_solo_upsert() -> None:
    """El universo de pares es la union de reportes y oficiales, sin duplicarlos."""
    sesion = SesionLoteFalsa(
        reportes=[
            _reporte(PAR_SOLO_COMUNIDAD, 2500),
            _reporte(PAR_MIXTO, 2800),
        ],
        oficiales=[
            _oficial(PAR_SOLO_OFICIAL),
            _oficial(PAR_MIXTO),
        ],
    )

    reconstruidos = await politica_modulo._reconstruir_oficial_con_contraste(
        sesion,  # type: ignore[arg-type]
        LIMITE,
        AHORA,
        ParametrosDominio(),
    )

    assert reconstruidos == 3
    assert sesion.consultas == ["reportes", "oficiales", "cortes"]
    assert len(sesion.upserts) == 1
    lote = sesion.upserts[0]
    assert len(lote) == 3

    solo_oficial = _fila_por_par(lote, PAR_SOLO_OFICIAL)
    assert solo_oficial["precio_cop"] == 3000
    assert solo_oficial["sello"] == "oficial"
    assert solo_oficial["precio_oficial_cop"] == 3000
    assert UUID(solo_oficial["prod_id"]) == PRODUCTO

    solo_comunidad = _fila_por_par(lote, PAR_SOLO_COMUNIDAD)
    assert solo_comunidad["precio_cop"] == 2500
    assert solo_comunidad["sello"] == "pocos_datos"
    assert solo_comunidad["precio_oficial_cop"] is None

    mixto = _fila_por_par(lote, PAR_MIXTO)
    assert mixto["precio_cop"] == 3000
    assert mixto["sello"] == "oficial"
    assert mixto["precio_oficial_cop"] == 3000
    assert Decimal(mixto["diferencia_pct"]) == Decimal("0.0667")

    assert sesion.casos == []


async def test_el_corte_confirmado_impide_que_reportes_previos_reabran_la_disputa() -> None:
    """Los tres reportes anteriores al corte no alimentan la ventana de contradiccion."""
    autores = [uuid4(), uuid4(), uuid4()]
    reportes = [
        _reporte(PAR_MIXTO, 2600, autor_id=autor, observado_en=AHORA - timedelta(hours=2))
        for autor in autores
    ]
    sesion = SesionLoteFalsa(
        reportes=reportes,
        oficiales=[_oficial(PAR_MIXTO, precio_cop=3050)],
        cortes=[_corte(PAR_MIXTO, AHORA - timedelta(hours=1))],
    )

    reconstruidos = await politica_modulo._reconstruir_oficial_con_contraste(
        sesion,  # type: ignore[arg-type]
        LIMITE,
        AHORA,
        ParametrosDominio(),
    )

    assert reconstruidos == 1
    fila = sesion.upserts[0][0]
    assert fila["sello"] == "oficial"
    assert fila["precio_cop"] == 3050
    assert fila["precio_oficial_cop"] == 3050
    assert sesion.casos == []


async def test_el_lote_abre_un_solo_caso_para_el_par_en_disputa() -> None:
    """La comunidad contradice al comercio y el lote levanta la mano una sola vez."""
    autores = [uuid4(), uuid4(), uuid4()]
    reportes = [
        _reporte(PAR_MIXTO, 2600, autor_id=autor, observado_en=AHORA - timedelta(hours=2))
        for autor in autores
    ]
    sesion = SesionLoteFalsa(
        reportes=reportes,
        oficiales=[_oficial(PAR_MIXTO, precio_cop=3050)],
    )

    reconstruidos = await politica_modulo._reconstruir_oficial_con_contraste(
        sesion,  # type: ignore[arg-type]
        LIMITE,
        AHORA,
        ParametrosDominio(),
    )

    assert reconstruidos == 1
    fila = sesion.upserts[0][0]
    assert fila["sello"] == "en_disputa"
    assert fila["precio_cop"] == 2600
    assert len(sesion.casos) == 1
    assert sesion.casos[0]["pres_id"] == PAR_MIXTO[0]
    assert sesion.casos[0]["est_id_txt"] == str(PAR_MIXTO[1])


async def test_un_par_sin_contraste_no_queda_activo_y_se_borra_su_proyeccion() -> None:
    """Un reporte dudoso fuera de la vigencia no crea precio ni conserva la fila vieja."""
    sesion = SesionLoteFalsa(
        reportes=[
            _reporte(PAR_SOLO_COMUNIDAD, 2500),
            _reporte(
                PAR_SIN_CONTRASTE,
                2000,
                estado="dudoso",
                observado_en=AHORA - timedelta(days=10),
            ),
        ],
    )

    reconstruidos = await politica_modulo._reconstruir_oficial_con_contraste(
        sesion,  # type: ignore[arg-type]
        LIMITE,
        AHORA,
        ParametrosDominio(),
    )

    assert reconstruidos == 1
    assert len(sesion.upserts) == 1
    assert sesion.borrados == [
        [{"pres_id": str(PAR_SOLO_COMUNIDAD[0]), "est_id": str(PAR_SOLO_COMUNIDAD[1])}]
    ]


# Un solo dos puntos introduce un parametro; dos seguidos son un cast de PostgreSQL.
_PARAMETRO = re.compile(r"(?<!:):(\w+)")


def _sql_compacto(sentencia: TextClause) -> str:
    """Normaliza espacios y mayusculas para comparar fragmentos del SQL."""
    return " ".join(str(sentencia).lower().split())


def test_las_consultas_del_lote_excluyen_demo_comercio_y_oficiales_inactivos() -> None:
    """El filtro vive en el SQL: la ruta batch no puede recibir filas que no cuentan."""
    reportes = _sql_compacto(_SQL_REPORTES_LOTE)
    assert _PARAMETRO.findall(str(_SQL_REPORTES_LOTE)) == ["limite"]
    assert "observado_en >= :limite" in reportes
    assert "estado in ('aceptado', 'dudoso')" in reportes
    assert "es_demo = false" in reportes
    assert "fuente <> 'comercio'" in reportes
    assert "order by observado_en desc" in reportes

    oficiales = _sql_compacto(_SQL_OFICIALES_LOTE)
    assert "from public.precio_oficial po" in oficiales
    assert "po.activo = true" in oficiales
    assert "pr.cantidad_base" in oficiales

    cortes = _sql_compacto(_SQL_CORTES_CONFIRMADOS_LOTE)
    assert "max(c.resuelto_en)" in cortes
    assert "cast('confirmar' as decision_caso)" in cortes
    assert "group by c.referencia_id" in cortes


def test_las_consultas_de_reportes_desempatan_por_id() -> None:
    """Dos reportes con el mismo `observado_en` no pueden depender del orden fisico."""
    for sentencia in (_SQL_REPORTES_PAR, _SQL_REPORTES_LOTE):
        assert "order by observado_en desc, id desc" in _sql_compacto(sentencia)


def test_el_borrado_fuera_del_conjunto_activo_es_una_sola_sentencia() -> None:
    """El barrido final no puede volver a hacer un DELETE por par."""
    sql = _sql_compacto(_SQL_DELETE_PV_FUERA_DE)

    assert _PARAMETRO.findall(str(_SQL_DELETE_PV_FUERA_DE)) == ["pares"]
    assert "delete from public.precio_vigente pv" in sql
    assert "not exists" in sql
    assert "jsonb_to_recordset(cast(:pares as jsonb))" in sql
    assert json.loads(_serializar_pares_activos({PAR_MIXTO})) == [
        {"pres_id": str(PAR_MIXTO[0]), "est_id": str(PAR_MIXTO[1])}
    ]
    assert json.loads(_serializar_pares_activos(set())) == []


class _PoliticaPersonalizada:
    """Politica ajena a las dos de produccion; debe conservar la ruta par a par."""

    async def recalcular_par(
        self,
        sesion: Any,
        presentacion_id: UUID,
        establecimiento_id: UUID,
        ahora: datetime | None = None,
        params: ParametrosDominio | None = None,
    ) -> object | None:
        return object()


async def test_reconstruir_despacha_oficial_con_contraste_a_la_ruta_por_lotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin politica explicita, la reconstruccion usa la ruta batch, no la par a par."""
    capturada: dict[str, Any] = {}

    async def reconstruir_lote(
        sesion: Any,
        limite_inferior: datetime,
        instante: datetime,
        parametros: ParametrosDominio,
    ) -> int:
        capturada["ruta"] = "lote"
        capturada["limite"] = limite_inferior
        capturada["instante"] = instante
        return 7

    async def reconstruir_par_a_par(*args: Any, **kwargs: Any) -> int:
        capturada["ruta"] = "par_a_par"
        return 0

    async def obtener_parametros(sesion: Any) -> ParametrosDominio:
        return ParametrosDominio()

    monkeypatch.setattr(politica_modulo, "_reconstruir_oficial_con_contraste", reconstruir_lote)
    monkeypatch.setattr(
        politica_modulo, "_reconstruir_con_politica_personalizada", reconstruir_par_a_par
    )
    monkeypatch.setattr(politica_modulo, "obtener_parametros_dominio", obtener_parametros)

    resultado = await reconstruir_precio_vigente(object(), ahora=AHORA)  # type: ignore[arg-type]

    assert resultado == 7
    assert capturada["ruta"] == "lote"
    assert capturada["instante"] == AHORA
    assert capturada["limite"] == AHORA - timedelta(days=30)


async def test_reconstruir_conserva_la_ruta_par_a_par_para_politicas_personalizadas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una politica que no es de produccion no puede perder su `recalcular_par`."""
    capturada: dict[str, Any] = {}

    async def reconstruir_par_a_par(
        sesion: Any,
        pol: Any,
        limite_inferior: datetime,
        instante: datetime,
        parametros: ParametrosDominio,
    ) -> int:
        capturada["politica"] = pol
        return 2

    async def reconstruir_lote(*args: Any, **kwargs: Any) -> int:
        raise AssertionError("una politica personalizada no debe usar la ruta batch")

    async def obtener_parametros(sesion: Any) -> ParametrosDominio:
        return ParametrosDominio()

    monkeypatch.setattr(
        politica_modulo, "_reconstruir_con_politica_personalizada", reconstruir_par_a_par
    )
    monkeypatch.setattr(politica_modulo, "_reconstruir_oficial_con_contraste", reconstruir_lote)
    monkeypatch.setattr(politica_modulo, "obtener_parametros_dominio", obtener_parametros)

    politica = _PoliticaPersonalizada()
    resultado = await reconstruir_precio_vigente(
        object(),  # type: ignore[arg-type]
        ahora=AHORA,
        politica=politica,  # type: ignore[arg-type]
    )

    assert resultado == 2
    assert capturada["politica"] is politica


def test_las_politicas_de_produccion_siguen_siendo_instancias_distintas() -> None:
    """El despacho por tipo no puede confundir `OficialConContraste` con `SoloUsuarios`."""
    assert isinstance(OficialConContraste(), OficialConContraste)
    assert not isinstance(OficialConContraste(), SoloUsuarios)
    assert isinstance(SoloUsuarios(), SoloUsuarios)
