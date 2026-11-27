"""Pruebas unitarias del historial oficial append-only del modulo comercial (ADR-0019).

No tocan base de datos: parchean el repositorio y comprueban la decision de negocio.
La prueba de integracion real contra `reporte_precio` queda para T-68.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.compartido.seguridad import UsuarioAutenticado
from app.dominio.parametros import ParametrosDominio
from app.dominio.precio_oficial import requiere_historial_oficial
from app.modulos.comercial import servicio as servicio_modulo
from app.modulos.comercial.esquemas import PrecioOficialEntrada, PreciosLoteEntrada
from app.modulos.comercial.repositorio import _SQL_INSERTAR_REPORTE_OFICIAL
from app.modulos.comercial.servicio import ServicioComercial

ESTABLECIMIENTO_ID = UUID(int=1)
PRODUCTO_ID = UUID(int=2)
PRESENTACION_ID = UUID(int=3)
COMERCIO_ID = UUID(int=4)
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

    assert "insert into public.reporte_precio" in sql
    assert "'comercio'" in sql
    assert "'aceptado'" in sql
    assert "'presentacion_tienda'" in sql
    assert "null" in sql
    assert "false" in sql


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
) -> None:
    """Instala un repositorio falso para el flujo de publicacion de precios."""

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

    async def obtener_presentaciones(*args: Any, **kwargs: Any) -> dict[UUID, dict[str, Any]]:
        return {
            PRESENTACION_ID: {
                "id": PRESENTACION_ID,
                "producto_id": PRODUCTO_ID,
                "cantidad_base": CANTIDAD_BASE,
                "activa": True,
            }
        }

    async def obtener_precios_oficiales_cop(*args: Any, **kwargs: Any) -> dict[UUID, int]:
        return {} if anterior is None else {PRESENTACION_ID: anterior}

    async def upsert_precio_oficial(sesion: Any, **datos: Any) -> None:
        if upserts is not None:
            upserts.append(datos)

    async def insertar_reporte_oficial(sesion: Any, **datos: Any) -> UUID:
        historial.append(datos)
        return uuid4()

    async def obtener_parametros_dominio(*args: Any, **kwargs: Any) -> ParametrosDominio:
        return ParametrosDominio()

    async def registrar_auditoria(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        servicio_modulo.repositorio, "obtener_establecimiento", obtener_establecimiento
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


@pytest.mark.asyncio
async def test_el_mismo_precio_repetido_en_el_lote_inserta_una_sola_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dos entradas iguales para la misma presentacion no duplican el historial."""
    historial: list[dict[str, Any]] = []
    _preparar_publicacion(monkeypatch, anterior=None, historial=historial)
    servicio = ServicioComercial(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=CacheEspia(),  # type: ignore[arg-type]
        politica_precio=PoliticaEspia(),  # type: ignore[arg-type]
    )
    lote = PreciosLoteEntrada(
        precios=[
            PrecioOficialEntrada(presentacion_id=PRESENTACION_ID, precio_cop=2500),
            PrecioOficialEntrada(presentacion_id=PRESENTACION_ID, precio_cop=2500),
        ]
    )

    await servicio.publicar_precios(ESTABLECIMIENTO_ID, lote, USUARIO)

    assert len(historial) == 1


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
