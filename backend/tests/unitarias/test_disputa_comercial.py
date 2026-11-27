"""Pruebas unitarias de la disputa D-01 y de la autorizacion del reclamo comercial.

- El reclamo de titularidad exige autorizacion de datos (Ley 1581).
- Un contraste con `hay_disputa` abre un `caso_moderacion` idempotente.
- Si la insercion del caso falla, el precio vigente se calcula igual.
- Un moderador resuelve la disputa: `confirmar` deja ganar al oficial,
  `descartar` deja ganar a la comunidad y `sancionar` responde 422.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.routing import APIRoute

from app.compartido.errores import ValidacionError
from app.compartido.seguridad import UsuarioAutenticado, requiere_autorizacion_datos
from app.dominio.parametros import ParametrosDominio
from app.modulos.comercial.api import router as comercial_router
from app.modulos.moderacion import repositorio_casos
from app.modulos.moderacion import servicio_casos as servicio_casos_modulo
from app.modulos.moderacion.esquemas_casos import ResolverCasoEntrada
from app.modulos.moderacion.servicio_casos import ServicioCasosModeracion
from app.puertos import politica_precio as politica_modulo
from app.puertos.politica_precio import OficialConContraste

AHORA = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
PRESENTACION = UUID(int=1)
ESTABLECIMIENTO = UUID(int=2)
PRODUCTO = UUID(int=3)
CASO_ID = UUID(int=9)
MODERADOR = UsuarioAutenticado(
    id=UUID(int=4), email="mod@armenia.gov.co", rol="moderador", estado="activa"
)


class ResultadoConsulta:
    """Resultado minimo de una sentencia para las sesiones falsas."""

    def __init__(self, filas: list[Any] | None = None, fila: Any = None) -> None:
        self._filas = filas or []
        self._fila = fila

    def fetchall(self) -> list[Any]:
        return self._filas

    def fetchone(self) -> Any:
        return self._fila

    def first(self) -> Any:
        return self._fila


class _SavepointFalso:
    """Context manager que imita `AsyncSession.begin_nested()`."""

    def __init__(self, sesion: Any) -> None:
        self._sesion = sesion

    async def __aenter__(self) -> Any:
        return self._sesion

    async def __aexit__(self, *exc: object) -> bool:
        return False


class SesionPoliticaFalsa:
    """Sesion que responde como un par con oficial y reportes comunitarios."""

    def __init__(
        self,
        reportes: list[Any],
        precio_oficial_cop: int = 3050,
        falla_caso: bool = False,
    ) -> None:
        self.reportes = reportes
        self.precio_oficial_cop = precio_oficial_cop
        self.falla_caso = falla_caso
        self.upserts: list[dict[str, Any]] = []
        self.casos: list[dict[str, Any]] = []

    def begin_nested(self) -> _SavepointFalso:
        return _SavepointFalso(self)

    async def execute(self, sentencia: Any, parametros: Any = None) -> ResultadoConsulta:
        sql = " ".join(str(sentencia).lower().split())
        if sql.startswith("insert into public.precio_vigente"):
            self.upserts.append(parametros)
            return ResultadoConsulta()
        if "from public.reporte_precio" in sql:
            return ResultadoConsulta(filas=self.reportes)
        if "from public.precio_oficial po" in sql:
            return ResultadoConsulta(
                fila=SimpleNamespace(
                    precio_cop=self.precio_oficial_cop,
                    revalidado_en=AHORA - timedelta(days=1),
                    cantidad_base=Decimal("1000.000"),
                )
            )
        if sql.startswith("insert into public.caso_moderacion"):
            self.casos.append(parametros)
            if self.falla_caso:
                raise RuntimeError("fallo simulado al insertar el caso")
            return ResultadoConsulta()
        raise AssertionError(f"SQL inesperado: {sql}")


class SesionResolucionFalsa:
    """Sesion que ejecuta el SQL real de resolucion de disputas."""

    def __init__(self) -> None:
        self.revalidaciones: list[dict[str, Any]] = []
        self.upserts: list[dict[str, Any]] = []
        self.desactivaciones: list[dict[str, Any]] = []
        self.casos_actualizados: list[dict[str, Any]] = []
        self.auditorias: list[dict[str, Any]] = []

    async def flush(self) -> None:
        return None

    async def execute(self, sentencia: Any, parametros: Any = None) -> ResultadoConsulta:
        sql = " ".join(str(sentencia).lower().split())
        if sql.startswith("select po.precio_cop, po.precio_por_base"):
            return ResultadoConsulta(
                fila=SimpleNamespace(
                    precio_cop=3050,
                    precio_por_base=Decimal("3.050000"),
                    producto_id=PRODUCTO,
                    cantidad_base=Decimal("1000.000"),
                )
            )
        if sql.startswith("update public.precio_oficial set revalidado_en"):
            self.revalidaciones.append(parametros)
            return ResultadoConsulta()
        if sql.startswith("insert into public.precio_vigente"):
            self.upserts.append(parametros)
            return ResultadoConsulta()
        if sql.startswith("update public.precio_oficial set activo = false"):
            self.desactivaciones.append(parametros)
            return ResultadoConsulta(fila=SimpleNamespace(producto_id=PRODUCTO))
        if sql.startswith("update public.caso_moderacion"):
            self.casos_actualizados.append(parametros)
            return ResultadoConsulta()
        if sql.startswith("insert into auditoria"):
            self.auditorias.append(parametros)
            return ResultadoConsulta()
        raise AssertionError(f"SQL inesperado: {sql}")


class PoliticaFalsa:
    """Registra el recalculo que pide la resolucion de una disputa."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[UUID, UUID]] = []

    async def recalcular_par(
        self,
        sesion: Any,
        presentacion_id: UUID,
        establecimiento_id: UUID,
        ahora: datetime | None = None,
        params: ParametrosDominio | None = None,
    ) -> object:
        self.llamadas.append((presentacion_id, establecimiento_id))
        return SimpleNamespace(sello="confiable")


class CacheFalsa:
    def __init__(self) -> None:
        self.invalidados: list[UUID] = []

    async def invalidar_producto(self, producto_id: UUID) -> None:
        self.invalidados.append(producto_id)


def _reporte(precio_cop: int, autor: str, horas_atras: float) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        precio_cop=precio_cop,
        cantidad_base_snapshot=Decimal("1000.000"),
        observado_en=AHORA - timedelta(hours=horas_atras),
        reportante_id=autor,
        fuente="usuario",
        foto_prueba_path=None,
        estado="aceptado",
        producto_id=PRODUCTO,
    )


def _reportes_contradictorios() -> list[SimpleNamespace]:
    return [
        _reporte(2600, "a", 5),
        _reporte(2600, "b", 10),
        _reporte(2650, "c", 20),
    ]


def _reportes_que_coinciden() -> list[SimpleNamespace]:
    return [
        _reporte(2900, "a", 5),
        _reporte(2900, "b", 10),
        _reporte(2900, "c", 20),
    ]


def _caso_disputa() -> dict[str, Any]:
    return {
        "id": CASO_ID,
        "tipo": "disputa_precio",
        "referencia_tabla": "presentacion",
        "referencia_id": PRESENTACION,
        "detalle": {
            "presentacion_id": str(PRESENTACION),
            "establecimiento_id": str(ESTABLECIMIENTO),
            "producto_id": str(PRODUCTO),
            "precio_oficial_cop": 3050,
            "precio_comunidad_cop": 2600,
            "diferencia_pct": 0.1475,
            "n_reportes_validos": 3,
            "n_fuentes": 3,
            "sello": "en_disputa",
        },
        "prioridad": 2,
        "estado": "abierto",
        "decision": None,
        "moderador_id": None,
        "nota": None,
        "creado_en": AHORA,
        "resuelto_en": None,
    }


def test_reclamo_de_comercio_exige_autorizacion_de_datos() -> None:
    """La ruta no puede seguir aceptando cuentas sin autorizacion Ley 1581."""
    ruta = next(
        r
        for r in comercial_router.routes
        if isinstance(r, APIRoute) and r.path == "/comercio/reclamos"
    )
    assert "POST" in ruta.methods
    dependencias = {d.call for d in ruta.dependant.dependencies}
    assert requiere_autorizacion_datos in dependencias


async def test_contraste_con_disputa_abre_caso_de_moderacion() -> None:
    """La contradiccion comunitaria queda en la cola humana, no solo en el sello."""
    sesion = SesionPoliticaFalsa(_reportes_contradictorios())

    resultado = await OficialConContraste().recalcular_par(
        sesion,  # type: ignore[arg-type]
        PRESENTACION,
        ESTABLECIMIENTO,
        AHORA,
        ParametrosDominio(),
    )

    assert resultado is not None
    assert resultado.sello == "en_disputa"
    assert len(sesion.casos) == 1

    parametros = sesion.casos[0]
    assert parametros["pres_id"] == PRESENTACION
    assert parametros["est_id_txt"] == str(ESTABLECIMIENTO)
    detalle = json.loads(parametros["detalle"])
    assert detalle["presentacion_id"] == str(PRESENTACION)
    assert detalle["establecimiento_id"] == str(ESTABLECIMIENTO)
    assert detalle["producto_id"] == str(PRODUCTO)
    assert detalle["precio_oficial_cop"] == 3050
    assert detalle["precio_comunidad_cop"] == 2600
    assert detalle["diferencia_pct"] == pytest.approx(0.1475)
    assert detalle["n_reportes_validos"] == 3
    assert detalle["n_fuentes"] == 3
    assert detalle["sello"] == "en_disputa"


def test_insercion_del_caso_es_idempotente_por_par_abierto() -> None:
    """El SQL no duplica el caso mientras siga abierto o en revision."""
    sql = " ".join(str(politica_modulo._SQL_ABRIR_CASO_DISPUTA).lower().split())

    assert "where not exists" in sql
    assert "detalle ->> 'establecimiento_id'" in sql
    assert "estado in ('abierto', 'en_revision')" in sql
    assert "prioridad" in sql


async def test_contraste_sin_disputa_no_abre_caso() -> None:
    """Un contraste normal no ensucia la cola de moderacion."""
    sesion = SesionPoliticaFalsa(_reportes_que_coinciden())

    resultado = await OficialConContraste().recalcular_par(
        sesion,  # type: ignore[arg-type]
        PRESENTACION,
        ESTABLECIMIENTO,
        AHORA,
        ParametrosDominio(),
    )

    assert resultado is not None
    assert resultado.sello == "oficial"
    assert sesion.casos == []


async def test_fallo_al_abrir_el_caso_no_rompe_el_calculo(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """El precio vigente es la funcion principal; el caso es reintentable."""
    sesion = SesionPoliticaFalsa(_reportes_contradictorios(), falla_caso=True)

    with caplog.at_level(logging.WARNING):
        resultado = await OficialConContraste().recalcular_par(
            sesion,  # type: ignore[arg-type]
            PRESENTACION,
            ESTABLECIMIENTO,
            AHORA,
            ParametrosDominio(),
        )

    assert resultado is not None
    assert resultado.sello == "en_disputa"
    assert len(sesion.upserts) == 1
    assert "caso de disputa" in caplog.text


async def test_confirmar_disputa_deja_ganar_al_precio_oficial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El moderador revalida el oficial y la proyeccion vuelve a sus valores."""
    sesion = SesionResolucionFalsa()
    cache = CacheFalsa()
    politica = PoliticaFalsa()
    caso = _caso_disputa()

    async def obtener_caso(sesion_falsa: Any, caso_id: UUID) -> dict[str, Any]:
        return dict(caso)

    async def parametros(sesion_falsa: Any) -> ParametrosDominio:
        return ParametrosDominio()

    monkeypatch.setattr(repositorio_casos, "obtener_caso_por_id_bd", obtener_caso)
    monkeypatch.setattr(servicio_casos_modulo, "obtener_parametros_dominio", parametros)

    servicio = ServicioCasosModeracion(
        sesion=sesion,  # type: ignore[arg-type]
        cache=cache,  # type: ignore[arg-type]
        politica=politica,  # type: ignore[arg-type]
    )
    entrada = ResolverCasoEntrada(decision="confirmar", nota="Factura y gondola revisadas")
    await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert sesion.revalidaciones[0]["pres_id"] == PRESENTACION
    assert sesion.revalidaciones[0]["est_id"] == ESTABLECIMIENTO
    assert len(sesion.upserts) == 1
    upsert = sesion.upserts[0]
    assert upsert["precio_cop"] == 3050
    assert upsert["precio_oficial_cop"] == 3050
    assert upsert["precio_por_base"] == Decimal("3.050000")

    sql_upsert = " ".join(str(repositorio_casos._SQL_FIJAR_PRECIO_VIGENTE_OFICIAL).lower().split())
    assert "diferencia_pct = 0" in sql_upsert
    assert "requiere_revalidacion = false" in sql_upsert
    assert "'oficial'" in sql_upsert
    assert "precio oficial confirmado por moderacion" in sql_upsert

    assert politica.llamadas == []
    assert cache.invalidados == [PRODUCTO]
    assert sesion.casos_actualizados[0]["decision"] == "confirmar"
    assert len(sesion.auditorias) == 1
    assert sesion.auditorias[0]["accion"] == "resolver_caso_confirmar"
    despues = json.loads(sesion.auditorias[0]["despues"])
    assert despues["precio_ganador"] == "oficial"


async def test_descartar_disputa_deja_ganar_a_la_comunidad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El moderador apaga el oficial y recalcula con la comunidad."""
    sesion = SesionResolucionFalsa()
    cache = CacheFalsa()
    politica = PoliticaFalsa()
    caso = _caso_disputa()

    async def obtener_caso(sesion_falsa: Any, caso_id: UUID) -> dict[str, Any]:
        return dict(caso)

    async def parametros(sesion_falsa: Any) -> ParametrosDominio:
        return ParametrosDominio()

    monkeypatch.setattr(repositorio_casos, "obtener_caso_por_id_bd", obtener_caso)
    monkeypatch.setattr(servicio_casos_modulo, "obtener_parametros_dominio", parametros)

    servicio = ServicioCasosModeracion(
        sesion=sesion,  # type: ignore[arg-type]
        cache=cache,  # type: ignore[arg-type]
        politica=politica,  # type: ignore[arg-type]
    )
    entrada = ResolverCasoEntrada(decision="descartar", nota="La comunidad tiene razon")
    await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert sesion.desactivaciones[0]["pres_id"] == PRESENTACION
    assert sesion.desactivaciones[0]["est_id"] == ESTABLECIMIENTO
    assert politica.llamadas == [(PRESENTACION, ESTABLECIMIENTO)]
    assert cache.invalidados == [PRODUCTO]
    assert sesion.casos_actualizados[0]["decision"] == "descartar"
    assert len(sesion.auditorias) == 1
    assert sesion.auditorias[0]["accion"] == "resolver_caso_descartar"
    despues = json.loads(sesion.auditorias[0]["despues"])
    assert despues["precio_ganador"] == "comunidad"


async def test_sancionar_no_aplica_a_una_disputa_de_precio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No hay un unico reporte que sancionar: la decision se rechaza con 422."""
    sesion = SesionResolucionFalsa()
    caso = _caso_disputa()

    async def obtener_caso(sesion_falsa: Any, caso_id: UUID) -> dict[str, Any]:
        return dict(caso)

    async def parametros(sesion_falsa: Any) -> ParametrosDominio:
        return ParametrosDominio()

    monkeypatch.setattr(repositorio_casos, "obtener_caso_por_id_bd", obtener_caso)
    monkeypatch.setattr(servicio_casos_modulo, "obtener_parametros_dominio", parametros)

    servicio = ServicioCasosModeracion(
        sesion=sesion,  # type: ignore[arg-type]
        cache=CacheFalsa(),  # type: ignore[arg-type]
        politica=PoliticaFalsa(),  # type: ignore[arg-type]
    )
    entrada = ResolverCasoEntrada(decision="sancionar", nota="Castigar al autor")

    with pytest.raises(ValidacionError) as exc:
        await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert exc.value.status == 422
    assert "no aplica a una disputa de precio" in exc.value.detalle
    assert sesion.revalidaciones == []
    assert sesion.desactivaciones == []
    assert sesion.upserts == []
    assert sesion.casos_actualizados == []
    assert sesion.auditorias == []
