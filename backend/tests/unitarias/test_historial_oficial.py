"""Pruebas unitarias del historial oficial append-only del modulo comercial (ADR-0019).

No tocan base de datos: parchean el repositorio y comprueban la decision de negocio.
La prueba de integracion real contra `reporte_precio` queda para T-68.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.compartido.seguridad import UsuarioAutenticado
from app.dominio.parametros import ParametrosDominio
from app.dominio.precio_oficial import requiere_historial_oficial
from app.modulos.comercial import servicio as servicio_modulo
from app.modulos.comercial.esquemas import PrecioOficialEntrada, PreciosLoteEntrada
from app.modulos.comercial.repositorio import (
    _SQL_BLOQUEAR_ESTABLECIMIENTO,
    _SQL_INSERTAR_REPORTE_OFICIAL,
)
from app.modulos.comercial.servicio import ServicioComercial

ESTABLECIMIENTO_ID = UUID(int=1)
PRODUCTO_ID = UUID(int=2)
PRESENTACION_ID = UUID(int=3)
COMERCIO_ID = UUID(int=4)
PRODUCTO_ID_2 = UUID(int=5)
PRESENTACION_ID_2 = UUID(int=6)
CANTIDAD_BASE = Decimal("1000.000")
USUARIO = UsuarioAutenticado(
    id=COMERCIO_ID,
    email=None,
    rol="comercio",
    estado="activa",
)


@pytest.mark.parametrize(
    ("anterior", "nuevo", "esperado"),
    [
        (None, 2500, True),
        (2500, 2500, False),
        (2500, 2600, True),
        (2600, 2500, True),
    ],
)
def test_requiere_historial_oficial_solo_cuando_el_valor_cambia(
    anterior: int | None,
    nuevo: int,
    esperado: bool,
) -> None:
    """Republicar o revalidar el mismo precio no agrega otra fila al historial."""
    assert requiere_historial_oficial(anterior, nuevo) is esperado


def test_sql_del_historial_oficial_marca_origen_y_no_expone_identidad() -> None:
    """La fila oficial nace aceptada, sin reportante y con el conjunto de la tienda."""
    sql = " ".join(str(_SQL_INSERTAR_REPORTE_OFICIAL).lower().split())
    coincidencia = re.search(
        r"insert into public\.reporte_precio \((.*?)\) values \((.*?)\) returning", sql
    )
    assert coincidencia is not None
    columnas = [c.strip() for c in coincidencia.group(1).split(",")]
    valores = [v.strip() for v in coincidencia.group(2).split(",")]
    fila = dict(zip(columnas, valores, strict=True))

    assert fila["fuente"] == "'comercio'"
    assert fila["reportante_id"] == "null"
    assert fila["observado_en"] == ":observado_en"
    assert fila["estado"] == "'aceptado'"
    assert fila["estado_original"] == "'aceptado'"
    assert fila["conjunto_referencia"] == "'presentacion_tienda'"
    assert fila["es_demo"] == "false"


def test_sql_del_bloqueo_serializa_la_fila_del_establecimiento() -> None:
    """El lock debe ser `FOR UPDATE` sobre el establecimiento, no un SELECT simple."""
    sql = " ".join(str(_SQL_BLOQUEAR_ESTABLECIMIENTO).lower().split())

    assert sql.startswith("select id from public.establecimiento")
    assert "for update" in sql


class PoliticaEspia:
    """Registra los pares recalculados sin ejecutar SQL."""

    def __init__(self) -> None:
        self.pares: list[tuple[UUID, UUID]] = []

    async def recalcular_par(
        self,
        sesion: Any,
        presentacion_id: UUID,
        establecimiento_id: UUID,
        ahora: datetime | None = None,
        params: ParametrosDominio | None = None,
    ) -> None:
        self.pares.append((presentacion_id, establecimiento_id))


class CacheEspia:
    """Registra las invalidaciones de cache del servicio."""

    def __init__(self) -> None:
        self.productos: list[UUID] = []

    async def invalidar_producto(self, producto_id: UUID) -> None:
        self.productos.append(producto_id)


def _preparar_publicacion(
    monkeypatch: pytest.MonkeyPatch,
    *,
    anterior: int | None,
    historial: list[dict[str, Any]],
    upserts: list[dict[str, Any]] | None = None,
    eventos: list[str] | None = None,
    params: ParametrosDominio | None = None,
    presentaciones_extra: dict[UUID, dict[str, Any]] | None = None,
) -> None:
    """Instala un repositorio falso para el flujo de publicacion de precios."""

    def anotar(nombre: str) -> None:
        if eventos is not None:
            eventos.append(nombre)

    async def obtener_establecimiento(*args: Any, **kwargs: Any) -> dict[str, Any]:
        anotar("autorizacion")
        return {
            "id": ESTABLECIMIENTO_ID,
            "nombre": "Tienda de prueba",
            "tipo": "tienda",
            "barrio": None,
            "direccion": None,
            "comercio_id": COMERCIO_ID,
            "estado_verificacion": "verificado",
            "activo": True,
        }

    async def bloquear_establecimiento(*args: Any, **kwargs: Any) -> None:
        anotar("lock")

    async def obtener_presentaciones(*args: Any, **kwargs: Any) -> dict[UUID, dict[str, Any]]:
        anotar("presentaciones")
        presentaciones = {
            PRESENTACION_ID: {
                "id": PRESENTACION_ID,
                "producto_id": PRODUCTO_ID,
                "cantidad_base": CANTIDAD_BASE,
                "activa": True,
            }
        }
        if presentaciones_extra is not None:
            presentaciones.update(presentaciones_extra)
        return presentaciones

    async def obtener_precios_oficiales_cop(*args: Any, **kwargs: Any) -> dict[UUID, int]:
        anotar("precios_anteriores")
        return {} if anterior is None else {PRESENTACION_ID: anterior}

    async def upsert_precio_oficial(sesion: Any, **datos: Any) -> None:
        anotar("upsert")
        if upserts is not None:
            upserts.append(datos)

    async def insertar_reporte_oficial(sesion: Any, **datos: Any) -> UUID:
        anotar("historial")
        historial.append(datos)
        return uuid4()

    async def obtener_parametros_dominio(*args: Any, **kwargs: Any) -> ParametrosDominio:
        return params if params is not None else ParametrosDominio()

    async def registrar_auditoria(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        servicio_modulo.repositorio, "obtener_establecimiento", obtener_establecimiento
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio,
        "bloquear_establecimiento",
        bloquear_establecimiento,
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "obtener_presentaciones", obtener_presentaciones
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio,
        "obtener_precios_oficiales_cop",
        obtener_precios_oficiales_cop,
    )
    monkeypatch.setattr(servicio_modulo.repositorio, "upsert_precio_oficial", upsert_precio_oficial)
    monkeypatch.setattr(
        servicio_modulo.repositorio, "insertar_reporte_oficial", insertar_reporte_oficial
    )
    monkeypatch.setattr(servicio_modulo, "obtener_parametros_dominio", obtener_parametros_dominio)
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", registrar_auditoria)


def _lote(precio_cop: int) -> PreciosLoteEntrada:
    return PreciosLoteEntrada(
        precios=[PrecioOficialEntrada(presentacion_id=PRESENTACION_ID, precio_cop=precio_cop)]
    )


@pytest.mark.asyncio
async def test_publicar_un_precio_nuevo_escribe_la_primera_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin precio anterior, la publicacion deja una fila historica completa."""
    historial: list[dict[str, Any]] = []
    _preparar_publicacion(monkeypatch, anterior=None, historial=historial)
    politica = PoliticaEspia()
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=politica,  # type: ignore[arg-type]
    )

    respuesta = await servicio.publicar_precios(ESTABLECIMIENTO_ID, _lote(2500), USUARIO)

    assert respuesta["actualizados"] == 1
    assert respuesta["rechazados"] == []
    assert len(historial) == 1
    registro = historial[0]
    observado_en = registro.pop("observado_en")
    assert observado_en.tzinfo is not None
    assert registro == {
        "presentacion_id": PRESENTACION_ID,
        "establecimiento_id": ESTABLECIMIENTO_ID,
        "producto_id": PRODUCTO_ID,
        "precio_cop": 2500,
        "cantidad_base": CANTIDAD_BASE,
        "precio_por_base": Decimal("2.500000"),
    }
    assert politica.pares == [(PRESENTACION_ID, ESTABLECIMIENTO_ID)]


@pytest.mark.asyncio
async def test_republicar_el_mismo_precio_no_duplica_el_historial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Revalidar o reenviar el mismo valor conserva una sola version historica."""
    historial: list[dict[str, Any]] = []
    upserts: list[dict[str, Any]] = []
    _preparar_publicacion(
        monkeypatch,
        anterior=2500,
        historial=historial,
        upserts=upserts,
    )
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=PoliticaEspia(),  # type: ignore[arg-type]
    )

    respuesta = await servicio.publicar_precios(ESTABLECIMIENTO_ID, _lote(2500), USUARIO)

    assert respuesta["actualizados"] == 1
    assert len(upserts) == 1
    assert historial == []


@pytest.mark.asyncio
async def test_cambiar_el_precio_agrega_una_version_sin_borrar_la_anterior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un valor distinto deja otra fila append-only; el historial nunca se actualiza."""
    historial: list[dict[str, Any]] = []
    _preparar_publicacion(monkeypatch, anterior=2500, historial=historial)
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=PoliticaEspia(),  # type: ignore[arg-type]
    )

    await servicio.publicar_precios(ESTABLECIMIENTO_ID, _lote(2600), USUARIO)

    assert len(historial) == 1
    assert historial[0]["precio_cop"] == 2600
    assert historial[0]["precio_por_base"] == Decimal("2.600000")


def test_el_lote_rechaza_la_misma_presentacion_dos_veces() -> None:
    """Un lote ambiguo se rechaza con 422 antes de tocar el historial."""
    with pytest.raises(ValidationError, match="una sola vez"):
        PreciosLoteEntrada(
            precios=[
                PrecioOficialEntrada(presentacion_id=PRESENTACION_ID, precio_cop=2500),
                PrecioOficialEntrada(presentacion_id=PRESENTACION_ID, precio_cop=2600),
            ]
        )


@pytest.mark.asyncio
async def test_publicar_precios_adquiere_el_lock_antes_de_leer_el_precio_anterior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La lectura del precio previo ocurre despues del bloqueo por establecimiento."""
    eventos: list[str] = []
    _preparar_publicacion(
        monkeypatch,
        anterior=2500,
        historial=[],
        eventos=eventos,
    )
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=PoliticaEspia(),  # type: ignore[arg-type]
    )

    await servicio.publicar_precios(ESTABLECIMIENTO_ID, _lote(2600), USUARIO)

    assert eventos.index("lock") < eventos.index("autorizacion")
    assert eventos.index("lock") < eventos.index("precios_anteriores")
    assert eventos.index("lock") < eventos.index("upsert")
    assert eventos.count("lock") == 1


@pytest.mark.asyncio
async def test_revalidar_no_escribe_historial_ni_republica_el_precio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """«Todo sigue igual» solo renueva la confirmacion: no crea una version nueva."""

    async def obtener_establecimiento(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "id": ESTABLECIMIENTO_ID,
            "nombre": "Tienda de prueba",
            "tipo": "tienda",
            "barrio": None,
            "direccion": None,
            "comercio_id": COMERCIO_ID,
            "estado_verificacion": "verificado",
            "activo": True,
        }

    async def revalidar_precios(*args: Any, **kwargs: Any) -> tuple[int, datetime]:
        return 1, datetime.now(UTC)

    async def listar_presentaciones(*args: Any, **kwargs: Any) -> list[UUID]:
        return [PRESENTACION_ID]

    async def obtener_presentaciones(*args: Any, **kwargs: Any) -> dict[UUID, dict[str, Any]]:
        return {
            PRESENTACION_ID: {
                "id": PRESENTACION_ID,
                "producto_id": PRODUCTO_ID,
                "cantidad_base": CANTIDAD_BASE,
                "activa": True,
            }
        }

    async def fallar_si_se_escribe(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Revalidar no debe escribir el historial oficial.")

    async def obtener_parametros_dominio(*args: Any, **kwargs: Any) -> ParametrosDominio:
        return ParametrosDominio()

    async def registrar_auditoria(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        servicio_modulo.repositorio, "obtener_establecimiento", obtener_establecimiento
    )
    monkeypatch.setattr(servicio_modulo.repositorio, "revalidar_precios", revalidar_precios)
    monkeypatch.setattr(
        servicio_modulo.repositorio,
        "listar_presentaciones_con_precio_oficial",
        listar_presentaciones,
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "obtener_presentaciones", obtener_presentaciones
    )
    monkeypatch.setattr(
        servicio_modulo.repositorio, "insertar_reporte_oficial", fallar_si_se_escribe
    )
    monkeypatch.setattr(servicio_modulo.repositorio, "upsert_precio_oficial", fallar_si_se_escribe)
    monkeypatch.setattr(servicio_modulo, "obtener_parametros_dominio", obtener_parametros_dominio)
    monkeypatch.setattr(servicio_modulo, "registrar_auditoria", registrar_auditoria)

    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=PoliticaEspia(),  # type: ignore[arg-type]
    )

    respuesta = await servicio.revalidar(ESTABLECIMIENTO_ID, USUARIO)

    assert respuesta["revalidados"] == 1


@pytest.mark.asyncio
async def test_precio_bajo_el_minimo_configurado_se_rechaza_sin_romper_el_lote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El minimo sale de config_parametro y el rechazo viaja en el bloque del lote."""
    historial: list[dict[str, Any]] = []
    upserts: list[dict[str, Any]] = []
    params = ParametrosDominio(precio_min_cop=1000, precio_max_cop=2000)
    _preparar_publicacion(
        monkeypatch,
        anterior=None,
        historial=historial,
        upserts=upserts,
        params=params,
    )
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=PoliticaEspia(),  # type: ignore[arg-type]
    )

    respuesta = await servicio.publicar_precios(ESTABLECIMIENTO_ID, _lote(999), USUARIO)

    assert respuesta["actualizados"] == 0
    assert len(respuesta["rechazados"]) == 1
    rechazo = respuesta["rechazados"][0]
    assert rechazo.presentacion_id == PRESENTACION_ID
    assert "1000" in rechazo.motivo
    assert "2000" in rechazo.motivo
    assert upserts == []
    assert historial == []


@pytest.mark.asyncio
async def test_precio_sobre_el_maximo_configurado_se_rechaza_sin_romper_el_lote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El maximo tambien sale de config_parametro, no del esquema Pydantic."""
    historial: list[dict[str, Any]] = []
    upserts: list[dict[str, Any]] = []
    params = ParametrosDominio(precio_min_cop=1000, precio_max_cop=2000)
    _preparar_publicacion(
        monkeypatch,
        anterior=None,
        historial=historial,
        upserts=upserts,
        params=params,
    )
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=PoliticaEspia(),  # type: ignore[arg-type]
    )

    respuesta = await servicio.publicar_precios(ESTABLECIMIENTO_ID, _lote(2001), USUARIO)

    assert respuesta["actualizados"] == 0
    assert len(respuesta["rechazados"]) == 1
    assert upserts == []
    assert historial == []


@pytest.mark.asyncio
async def test_precio_dentro_del_rango_configurado_se_publica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un valor valido cruza el mismo camino y actualiza el precio oficial."""
    historial: list[dict[str, Any]] = []
    upserts: list[dict[str, Any]] = []
    params = ParametrosDominio(precio_min_cop=1000, precio_max_cop=2000)
    _preparar_publicacion(
        monkeypatch,
        anterior=None,
        historial=historial,
        upserts=upserts,
        params=params,
    )
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=PoliticaEspia(),  # type: ignore[arg-type]
    )

    respuesta = await servicio.publicar_precios(ESTABLECIMIENTO_ID, _lote(1500), USUARIO)

    assert respuesta["actualizados"] == 1
    assert respuesta["rechazados"] == []
    assert len(upserts) == 1
    assert upserts[0]["precio_cop"] == 1500
    assert len(historial) == 1


def test_el_esquema_acepta_un_valor_sobre_el_maximo_para_que_el_lote_lo_rechace() -> None:
    """El esquema ya no fija 2M: ese limite se decide con config_parametro."""
    entrada = PrecioOficialEntrada(presentacion_id=PRESENTACION_ID, precio_cop=2_500_000)

    assert entrada.precio_cop == 2_500_000


@pytest.mark.parametrize("precio_cop", [1000, 2000])
@pytest.mark.asyncio
async def test_los_limites_exactos_configurados_se_publican(
    monkeypatch: pytest.MonkeyPatch,
    precio_cop: int,
) -> None:
    """Los bordes del rango son inclusivos: min y max exactos son validos."""
    historial: list[dict[str, Any]] = []
    upserts: list[dict[str, Any]] = []
    params = ParametrosDominio(precio_min_cop=1000, precio_max_cop=2000)
    _preparar_publicacion(
        monkeypatch,
        anterior=None,
        historial=historial,
        upserts=upserts,
        params=params,
    )
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=PoliticaEspia(),  # type: ignore[arg-type]
    )

    respuesta = await servicio.publicar_precios(ESTABLECIMIENTO_ID, _lote(precio_cop), USUARIO)

    assert respuesta["actualizados"] == 1
    assert respuesta["rechazados"] == []
    assert upserts[0]["precio_cop"] == precio_cop


@pytest.mark.asyncio
async def test_lote_mixto_aplica_el_valido_y_rechaza_el_invalido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un item fuera de rango no tumba el lote ni impide publicar el resto."""
    historial: list[dict[str, Any]] = []
    upserts: list[dict[str, Any]] = []
    params = ParametrosDominio(precio_min_cop=1000, precio_max_cop=2000)
    extra = {
        PRESENTACION_ID_2: {
            "id": PRESENTACION_ID_2,
            "producto_id": PRODUCTO_ID_2,
            "cantidad_base": CANTIDAD_BASE,
            "activa": True,
        }
    }
    _preparar_publicacion(
        monkeypatch,
        anterior=None,
        historial=historial,
        upserts=upserts,
        params=params,
        presentaciones_extra=extra,
    )
    politica = PoliticaEspia()
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=politica,  # type: ignore[arg-type]
    )
    lote = PreciosLoteEntrada(
        precios=[
            PrecioOficialEntrada(presentacion_id=PRESENTACION_ID, precio_cop=1500),
            PrecioOficialEntrada(presentacion_id=PRESENTACION_ID_2, precio_cop=999),
        ]
    )

    respuesta = await servicio.publicar_precios(ESTABLECIMIENTO_ID, lote, USUARIO)

    assert respuesta["actualizados"] == 1
    assert len(respuesta["rechazados"]) == 1
    assert respuesta["rechazados"][0].presentacion_id == PRESENTACION_ID_2
    assert [u["presentacion_id"] for u in upserts] == [PRESENTACION_ID]
    assert [h["presentacion_id"] for h in historial] == [PRESENTACION_ID]
    assert politica.pares == [(PRESENTACION_ID, ESTABLECIMIENTO_ID)]
