"""Pruebas unitarias de la disputa D-01 y de la autorizacion del reclamo comercial.

- El reclamo de titularidad exige autorizacion de datos (Ley 1581).
- Un contraste con `hay_disputa` abre un `caso_moderacion` idempotente.
- Una disputa confirmada es durable: los reportes previos ya no la reabren.
- La resolucion valida la version del precio oficial y bloquea el caso.
- `confirmar` deja ganar al oficial, `descartar` a la comunidad y `sancionar` da 422.
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

from app.compartido.errores import ConflictoError, ValidacionError
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
    """Sesion que responde como un par con oficial, reportes y un posible corte."""

    def __init__(
        self,
        reportes: list[Any],
        precio_oficial_cop: int = 3050,
        falla_caso: bool = False,
        corte: datetime | None = None,
    ) -> None:
        self.reportes = reportes
        self.precio_oficial_cop = precio_oficial_cop
        self.falla_caso = falla_caso
        self.corte = corte
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
        if "max(c.resuelto_en)" in sql:
            return ResultadoConsulta(fila=SimpleNamespace(corte=self.corte))
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
    """Sesion que ejecuta el SQL real de resolucion y simula la fila vigente."""

    def __init__(
        self,
        precio_oficial_cop: int = 3050,
        precio_oficial_activo: bool = True,
    ) -> None:
        self.precio_oficial_cop = precio_oficial_cop
        self.precio_oficial_activo = precio_oficial_activo
        self.revalidaciones: list[dict[str, Any]] = []
        self.upserts: list[dict[str, Any]] = []
        self.desactivaciones: list[dict[str, Any]] = []
        self.casos_actualizados: list[dict[str, Any]] = []
        self.detalles_actualizados: list[dict[str, Any]] = []
        self.auditorias: list[dict[str, Any]] = []
        self.commits = 0
        # Proyeccion previa con conteos comunitarios que deben sobrevivir a confirmar.
        self.precio_vigente: dict[str, Any] = {
            "producto_id": PRODUCTO,
            "precio_cop": 2600,
            "precio_por_base": Decimal("2.600000"),
            "cantidad_base": Decimal("1000.000"),
            "sello": "en_disputa",
            "motivo_sello": "La comunidad reporta un precio distinto",
            "n_reportes_validos": 3,
            "n_fuentes": 3,
            "dispersion": Decimal("0.0300"),
            "ultimo_reporte_en": AHORA - timedelta(hours=2),
            "reporte_origen_id": UUID(int=77),
            "precio_oficial_cop": 3050,
            "diferencia_pct": Decimal("0.1475"),
            "requiere_revalidacion": False,
        }

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, sentencia: Any, parametros: Any = None) -> ResultadoConsulta:
        sql = " ".join(str(sentencia).lower().split())
        if sql.startswith("select po.precio_cop, po.precio_por_base"):
            if not self.precio_oficial_activo:
                return ResultadoConsulta()
            return ResultadoConsulta(
                fila=SimpleNamespace(
                    precio_cop=self.precio_oficial_cop,
                    precio_por_base=Decimal("3.050000"),
                    producto_id=PRODUCTO,
                    cantidad_base=Decimal("1000.000"),
                    _mapping={
                        "precio_cop": self.precio_oficial_cop,
                        "precio_por_base": Decimal("3.050000"),
                        "producto_id": PRODUCTO,
                        "cantidad_base": Decimal("1000.000"),
                    },
                )
            )
        if sql.startswith("update public.precio_oficial set revalidado_en"):
            self.revalidaciones.append(parametros)
            return ResultadoConsulta()
        if sql.startswith("insert into public.precio_vigente"):
            self.upserts.append(parametros)
            # Solo los campos que el ON CONFLICT oficial debe tocar.
            self.precio_vigente.update(
                {
                    "producto_id": parametros["prod_id"],
                    "precio_cop": parametros["precio_cop"],
                    "precio_por_base": parametros["precio_por_base"],
                    "cantidad_base": parametros["cantidad_base"],
                    "sello": "oficial",
                    "motivo_sello": "Precio oficial confirmado por moderacion",
                    "precio_oficial_cop": parametros["precio_oficial_cop"],
                    "diferencia_pct": 0,
                    "requiere_revalidacion": False,
                    "ultimo_reporte_en": parametros["ahora"],
                    "reporte_origen_id": None,
                    "recalculado_en": AHORA,
                }
            )
            return ResultadoConsulta()
        if sql.startswith("update public.precio_oficial set activo = false"):
            self.desactivaciones.append(parametros)
            self.precio_oficial_activo = False
            return ResultadoConsulta(fila=SimpleNamespace(producto_id=PRODUCTO))
        if sql.startswith("update public.caso_moderacion set detalle"):
            self.detalles_actualizados.append(parametros)
            return ResultadoConsulta()
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


def _parchear_repositorio(
    monkeypatch: pytest.MonkeyPatch,
    caso: dict[str, Any],
    casos_para_resolver: list[dict[str, Any]] | None = None,
) -> None:
    """Sustituye la lectura de casos; el resto del SQL corre contra la sesion falsa."""
    cola = list(casos_para_resolver) if casos_para_resolver is not None else None

    async def obtener_para_resolver(sesion: Any, caso_id: UUID) -> dict[str, Any]:
        if cola is None:
            return dict(caso)
        if not cola:
            return {**caso, "estado": "resuelto"}
        return cola.pop(0)

    async def obtener_por_id(sesion: Any, caso_id: UUID) -> dict[str, Any]:
        return dict(caso)

    async def parametros(sesion: Any) -> ParametrosDominio:
        return ParametrosDominio()

    actualizar_real = repositorio_casos.actualizar_detalle_disputa_bd

    async def actualizar_detalle(sesion: Any, caso_id: UUID, detalle: dict[str, Any]) -> None:
        await actualizar_real(sesion, caso_id, detalle)
        caso["detalle"] = dict(detalle)

    monkeypatch.setattr(repositorio_casos, "obtener_caso_para_resolver_bd", obtener_para_resolver)
    monkeypatch.setattr(repositorio_casos, "obtener_caso_por_id_bd", obtener_por_id)
    monkeypatch.setattr(repositorio_casos, "actualizar_detalle_disputa_bd", actualizar_detalle)
    monkeypatch.setattr(servicio_casos_modulo, "obtener_parametros_dominio", parametros)


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
    assert "RuntimeError" in caplog.text


async def test_disputa_confirmada_ignora_reportes_anteriores_al_corte() -> None:
    """Confirmar deja un corte durable: los reportes ya juzgados no reabren el caso."""
    sesion = SesionPoliticaFalsa(_reportes_contradictorios(), corte=AHORA)

    resultado = await OficialConContraste().recalcular_par(
        sesion,  # type: ignore[arg-type]
        PRESENTACION,
        ESTABLECIMIENTO,
        AHORA + timedelta(hours=1),
        ParametrosDominio(),
    )

    assert resultado is not None
    assert resultado.sello == "oficial"
    assert sesion.casos == []
    # El resultado oficial conserva los conteos comunitarios completos.
    assert resultado.n_reportes_validos == 3
    assert resultado.n_fuentes == 3


async def test_reporte_posterior_al_corte_si_puede_abrir_un_caso_nuevo() -> None:
    """La comunidad puede volver a contradecir con evidencia posterior al corte."""
    reportes = [
        *_reportes_contradictorios(),
        _reporte(2600, "d", -0.10),
        _reporte(2600, "e", -0.20),
        _reporte(2650, "f", -0.30),
    ]
    sesion = SesionPoliticaFalsa(reportes, corte=AHORA)

    resultado = await OficialConContraste().recalcular_par(
        sesion,  # type: ignore[arg-type]
        PRESENTACION,
        ESTABLECIMIENTO,
        AHORA + timedelta(hours=2),
        ParametrosDominio(),
    )

    assert resultado is not None
    assert resultado.sello == "en_disputa"
    assert len(sesion.casos) == 1


def test_filtro_post_corte_excluye_el_instante_exacto() -> None:
    """El corte es estrictamente posterior; el mismo instante ya estaba a la vista."""
    candidatos = [
        SimpleNamespace(observado_en=AHORA - timedelta(seconds=1)),
        SimpleNamespace(observado_en=AHORA),
        SimpleNamespace(observado_en=AHORA + timedelta(seconds=1)),
    ]

    filtrados = politica_modulo.filtrar_candidatos_post_corte(candidatos, AHORA)  # type: ignore[arg-type]

    assert [c.observado_en for c in filtrados] == [AHORA + timedelta(seconds=1)]
    assert politica_modulo.filtrar_candidatos_post_corte(candidatos, None) == candidatos  # type: ignore[arg-type]


async def test_confirmar_disputa_deja_ganar_al_precio_oficial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El moderador revalida el oficial y la proyeccion vuelve a sus valores."""
    sesion = SesionResolucionFalsa()
    cache = CacheFalsa()
    politica = PoliticaFalsa()
    caso = _caso_disputa()
    _parchear_repositorio(monkeypatch, caso)
    inicio = datetime.now(UTC)

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

    # Valores finales de la fila preexistente, no solo el texto de la sentencia.
    vigente = sesion.precio_vigente
    assert vigente["precio_cop"] == 3050
    assert vigente["precio_por_base"] == Decimal("3.050000")
    assert vigente["sello"] == "oficial"
    assert vigente["motivo_sello"] == "Precio oficial confirmado por moderacion"
    assert vigente["precio_oficial_cop"] == 3050
    assert vigente["diferencia_pct"] == 0
    assert vigente["requiere_revalidacion"] is False
    assert vigente["ultimo_reporte_en"] >= inicio
    assert vigente["reporte_origen_id"] is None
    # Los conteos comunitarios existentes se conservan en el conflicto.
    assert vigente["n_reportes_validos"] == 3
    assert vigente["n_fuentes"] == 3
    assert vigente["dispersion"] == Decimal("0.0300")

    sql_upsert = " ".join(str(repositorio_casos._SQL_FIJAR_PRECIO_VIGENTE_OFICIAL).lower().split())
    assert "ultimo_reporte_en = excluded.ultimo_reporte_en" in sql_upsert
    assert "reporte_origen_id = excluded.reporte_origen_id" in sql_upsert
    assert "diferencia_pct = 0" in sql_upsert
    assert "requiere_revalidacion = false" in sql_upsert
    assert "'oficial'" in sql_upsert
    assert "precio oficial confirmado por moderacion" in sql_upsert
    assert "n_reportes_validos = excluded" not in sql_upsert
    assert "n_fuentes = excluded" not in sql_upsert
    assert "dispersion = excluded" not in sql_upsert

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
    _parchear_repositorio(monkeypatch, caso)

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


async def test_confirmar_refresca_detalle_y_segundo_intento_resuelve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si el precio cambio, el primer intento refresca el caso y el segundo resuelve."""
    sesion = SesionResolucionFalsa(precio_oficial_cop=3100)
    caso = _caso_disputa()
    _parchear_repositorio(monkeypatch, caso)

    servicio = ServicioCasosModeracion(
        sesion=sesion,  # type: ignore[arg-type]
        cache=CacheFalsa(),  # type: ignore[arg-type]
        politica=PoliticaFalsa(),  # type: ignore[arg-type]
    )
    entrada = ResolverCasoEntrada(decision="confirmar", nota="Precio revisado en gondola")

    with pytest.raises(ConflictoError) as exc:
        await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert exc.value.status == 409
    assert "detalle se actualizo" in exc.value.detalle
    assert sesion.commits == 1
    assert len(sesion.detalles_actualizados) == 1
    refrescado = json.loads(sesion.detalles_actualizados[0]["detalle"])
    assert refrescado["precio_oficial_cop"] == 3100
    assert refrescado["precio_oficial_anterior_cop"] == 3050
    assert datetime.fromisoformat(refrescado["detalle_actualizado_en"]).tzinfo is not None
    assert caso["detalle"]["precio_oficial_cop"] == 3100
    assert [a["accion"] for a in sesion.auditorias] == ["refrescar_detalle_disputa"]
    assert sesion.revalidaciones == []
    assert sesion.casos_actualizados == []

    await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert sesion.casos_actualizados[-1]["decision"] == "confirmar"
    assert len(sesion.revalidaciones) == 1
    assert sesion.precio_vigente["sello"] == "oficial"
    assert sesion.precio_vigente["precio_oficial_cop"] == 3100


async def test_descartar_refresca_detalle_y_segundo_intento_resuelve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Descartar con precio cambiado refresca y solo resuelve en el segundo intento."""
    sesion = SesionResolucionFalsa(precio_oficial_cop=3100)
    caso = _caso_disputa()
    _parchear_repositorio(monkeypatch, caso)
    politica = PoliticaFalsa()

    servicio = ServicioCasosModeracion(
        sesion=sesion,  # type: ignore[arg-type]
        cache=CacheFalsa(),  # type: ignore[arg-type]
        politica=politica,  # type: ignore[arg-type]
    )
    entrada = ResolverCasoEntrada(decision="descartar", nota="La comunidad tiene razon")

    with pytest.raises(ConflictoError) as exc:
        await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert exc.value.status == 409
    assert sesion.commits == 1
    assert sesion.desactivaciones == []
    assert politica.llamadas == []
    assert sesion.casos_actualizados == []
    assert caso["detalle"]["precio_oficial_cop"] == 3100

    await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert sesion.desactivaciones[0]["pres_id"] == PRESENTACION
    assert politica.llamadas == [(PRESENTACION, ESTABLECIMIENTO)]
    assert sesion.casos_actualizados[-1]["decision"] == "descartar"


async def test_descartar_con_oficial_inactivo_resuelve_sin_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si el oficial ya esta apagado, la comunidad gano: descartar cierra el caso."""
    sesion = SesionResolucionFalsa(precio_oficial_activo=False)
    caso = _caso_disputa()
    _parchear_repositorio(monkeypatch, caso)
    politica = PoliticaFalsa()
    cache = CacheFalsa()

    servicio = ServicioCasosModeracion(
        sesion=sesion,  # type: ignore[arg-type]
        cache=cache,  # type: ignore[arg-type]
        politica=politica,  # type: ignore[arg-type]
    )
    entrada = ResolverCasoEntrada(decision="descartar", nota="La comunidad tiene razon")

    await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert sesion.desactivaciones == []
    assert sesion.detalles_actualizados == []
    assert politica.llamadas == [(PRESENTACION, ESTABLECIMIENTO)]
    assert cache.invalidados == [PRODUCTO]
    assert sesion.casos_actualizados[0]["decision"] == "descartar"
    assert sesion.auditorias[-1]["accion"] == "resolver_caso_descartar"


async def test_confirmar_con_oficial_inactivo_devuelve_409_y_sugiere_descartar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin oficial activo no hay nada que confirmar; el caso sigue abierto."""
    sesion = SesionResolucionFalsa(precio_oficial_activo=False)
    caso = _caso_disputa()
    _parchear_repositorio(monkeypatch, caso)

    servicio = ServicioCasosModeracion(
        sesion=sesion,  # type: ignore[arg-type]
        cache=CacheFalsa(),  # type: ignore[arg-type]
        politica=PoliticaFalsa(),  # type: ignore[arg-type]
    )
    entrada = ResolverCasoEntrada(decision="confirmar", nota="Precio revisado en gondola")

    with pytest.raises(ConflictoError) as exc:
        await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert exc.value.status == 409
    assert "Use 'descartar'" in exc.value.detalle
    assert sesion.commits == 0
    assert sesion.casos_actualizados == []
    assert sesion.auditorias == []
    assert caso["detalle"]["precio_oficial_cop"] == 3050


async def test_doble_resolucion_del_mismo_caso_devuelve_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El segundo moderador encuentra el caso resuelto y no lo vuelve a decidir."""
    sesion = SesionResolucionFalsa()
    caso = _caso_disputa()
    _parchear_repositorio(monkeypatch, caso, casos_para_resolver=[dict(caso)])

    servicio = ServicioCasosModeracion(
        sesion=sesion,  # type: ignore[arg-type]
        cache=CacheFalsa(),  # type: ignore[arg-type]
        politica=PoliticaFalsa(),  # type: ignore[arg-type]
    )
    entrada = ResolverCasoEntrada(decision="confirmar", nota="Precio revisado en gondola")
    await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    with pytest.raises(ConflictoError) as exc:
        await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert exc.value.status == 409
    assert "ya se encuentra resuelto" in exc.value.detalle


def test_resolucion_bloquea_la_fila_del_caso() -> None:
    """El SELECT de resolucion toma FOR UPDATE para serializar a los moderadores."""
    sql = " ".join(str(repositorio_casos._SQL_CASO_PARA_RESOLVER).lower().split())
    assert "for update" in sql


def test_consulta_oficial_para_resolver_exige_activo_y_bloquea_la_fila() -> None:
    """La version validada es la del oficial activo, no una fila ya apagada."""
    sql = " ".join(str(repositorio_casos._SQL_PRECIO_OFICIAL_DEL_PAR).lower().split())
    assert "po.activo = true" in sql
    assert "for update of po" in sql


def test_corte_durable_solo_considera_confirmaciones() -> None:
    """Un descarte no crea corte: la comunidad ya gano ese caso."""
    sql = " ".join(str(politica_modulo._SQL_CORTE_DISPUTA_CONFIRMADA).lower().split())
    assert "decision = cast('confirmar' as decision_caso)" in sql
    assert "max(c.resuelto_en)" in sql


@pytest.mark.parametrize(
    "cambio",
    [
        {"presentacion_id": "no-es-uuid"},
        {"establecimiento_id": "no-es-uuid"},
        {"precio_oficial_cop": "no-es-numero"},
        {"precio_oficial_cop": 0},
        {"precio_oficial_cop": True},
        {"precio_oficial_cop": 3050.5},
        {"precio_oficial_cop": 1e400},
        {"presentacion_id": str(UUID(int=999))},
    ],
)
async def test_referencias_malformadas_del_caso_devuelven_422(
    monkeypatch: pytest.MonkeyPatch, cambio: dict[str, Any]
) -> None:
    """Un detalle corrupto se rechaza con 422 y no toca el caso ni el precio."""
    sesion = SesionResolucionFalsa()
    caso = _caso_disputa()
    caso["detalle"] = {**caso["detalle"], **cambio}
    _parchear_repositorio(monkeypatch, caso)

    servicio = ServicioCasosModeracion(
        sesion=sesion,  # type: ignore[arg-type]
        cache=CacheFalsa(),  # type: ignore[arg-type]
        politica=PoliticaFalsa(),  # type: ignore[arg-type]
    )
    entrada = ResolverCasoEntrada(decision="confirmar", nota="Precio revisado en gondola")

    with pytest.raises(ValidacionError) as exc:
        await servicio.resolver_caso(CASO_ID, entrada, MODERADOR)

    assert exc.value.status == 422
    assert sesion.casos_actualizados == []
    assert sesion.auditorias == []


async def test_sancionar_no_aplica_a_una_disputa_de_precio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No hay un unico reporte que sancionar: la decision se rechaza con 422."""
    sesion = SesionResolucionFalsa()
    caso = _caso_disputa()
    _parchear_repositorio(monkeypatch, caso)

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
