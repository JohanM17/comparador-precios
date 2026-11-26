"""Pruebas unitarias de validaciones y orquestacion del historial (Tarea T-113)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.compartido.errores import NoEncontradoError, ValidacionError
from app.modulos.precios import servicio_historial as modulo_historial
from app.modulos.precios.esquemas import (
    DatosHistorial,
    PuntoHistorial,
    RespuestaHistorial,
)
from app.modulos.precios.servicio_historial import (
    ServicioHistorial,
    validar_parametros_historial,
)

HASTA = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
VENTANA_MAXIMA = timedelta(days=90)
DESDE = HASTA - VENTANA_MAXIMA

PRODUCTO_ID = UUID(int=101)
ESTABLECIMIENTO_ID = UUID(int=102)
PRESENTACION_ID = UUID(int=103)


def _validar(desde: datetime, hasta: datetime, limite: int = 200) -> None:
    """Invoca la validacion pura con los parametros indicados."""
    validar_parametros_historial(desde, hasta, limite)


@pytest.mark.parametrize("limite", [1, 500])
def test_acepta_ventana_de_90_dias_y_limites_extremos(limite: int) -> None:
    """Una ventana exacta de 90 dias es valida con el limite minimo y maximo."""
    _validar(HASTA - VENTANA_MAXIMA, HASTA, limite)


def test_acepta_ventana_instantanea() -> None:
    """Una ventana de duracion cero tambien es valida."""
    _validar(HASTA, HASTA)


def test_acepta_fechas_aware_con_desplazamiento_distinto_de_utc() -> None:
    """La ventana se valida sobre instantes, no sobre la zona horaria elegida."""
    zona_colombia = timezone(timedelta(hours=-5))
    hasta = datetime(2026, 11, 1, 7, 0, 0, tzinfo=zona_colombia)
    _validar(hasta - VENTANA_MAXIMA, hasta)


def test_rechaza_desde_sin_zona_horaria() -> None:
    """Una fecha 'desde' naive no puede compararse de forma segura."""
    with pytest.raises(ValidacionError, match="'desde' debe incluir zona horaria") as capturado:
        _validar(datetime(2026, 8, 1, 12, 0, 0), HASTA)

    assert capturado.value.status == 422
    assert capturado.value.codigo == "VALIDACION"


def test_rechaza_hasta_sin_zona_horaria() -> None:
    """Una fecha 'hasta' naive no puede compararse de forma segura."""
    with pytest.raises(ValidacionError, match="'hasta' debe incluir zona horaria") as capturado:
        _validar(HASTA - VENTANA_MAXIMA, datetime(2026, 11, 1, 12, 0, 0))

    assert capturado.value.status == 422
    assert capturado.value.codigo == "VALIDACION"


def test_rechaza_desde_posterior_a_hasta() -> None:
    """La ventana exige que 'desde' no sea posterior a 'hasta'."""
    with pytest.raises(ValidacionError, match="no puede ser posterior") as capturado:
        _validar(HASTA, HASTA - timedelta(seconds=1))

    assert capturado.value.status == 422


def test_rechaza_ventana_mayor_a_90_dias_por_un_segundo() -> None:
    """Un segundo adicional sobre la ventana maxima se rechaza con un mensaje claro."""
    with pytest.raises(
        ValidacionError,
        match="La ventana máxima del historial es de 90 días",
    ) as capturado:
        _validar(HASTA - VENTANA_MAXIMA - timedelta(seconds=1), HASTA)

    assert capturado.value.status == 422


@pytest.mark.parametrize("limite", [0, -1, 501])
def test_rechaza_limite_fuera_de_rango(limite: int) -> None:
    """El limite debe estar entre 1 y 500 puntos."""
    with pytest.raises(ValidacionError, match="entre 1 y 500") as capturado:
        _validar(HASTA - VENTANA_MAXIMA, HASTA, limite)

    assert capturado.value.status == 422
    assert capturado.value.codigo == "VALIDACION"


def _fila_reporte(
    reporte_id: UUID,
    observado_en: datetime,
    *,
    precio_cop: int = 5000,
    es_demo: bool = False,
) -> dict[str, Any]:
    """Construye una fila publica tal como la devuelve el repositorio."""
    return {
        "id": reporte_id,
        "observado_en": observado_en,
        "precio_cop": precio_cop,
        "cantidad_base_snapshot": Decimal("1000.000"),
        "precio_por_base": Decimal("5.000000"),
        "origen": "usuario",
        "estado": "aceptado",
        "es_demo": es_demo,
        "presentacion_id": PRESENTACION_ID,
    }


class _NoSolicitado:
    """Centinela para distinguir 'no consultar' de un recurso inexistente."""


_NO_SOLICITADO = _NoSolicitado()


def _montar_repositorio(
    monkeypatch: pytest.MonkeyPatch,
    *,
    producto: dict[str, Any] | None,
    filas: list[dict[str, Any]],
    llamadas: dict[str, Any],
    presentacion: dict[str, Any] | None | _NoSolicitado = _NO_SOLICITADO,
    establecimiento: dict[str, Any] | None | _NoSolicitado = _NO_SOLICITADO,
) -> None:
    """Reemplaza las consultas del repositorio por dobles de prueba."""

    async def producto_falso(sesion: Any, producto_id: UUID) -> dict[str, Any] | None:
        return producto

    async def establecimiento_falso(sesion: Any, establecimiento_id: UUID) -> dict[str, Any] | None:
        if isinstance(establecimiento, _NoSolicitado):
            return {
                "id": ESTABLECIMIENTO_ID,
                "nombre": "Tienda de prueba",
                "municipio": "Armenia",
            }
        return establecimiento

    async def presentacion_falso(
        sesion: Any, presentacion_id: UUID, producto_id: UUID
    ) -> dict[str, Any] | None:
        if isinstance(presentacion, _NoSolicitado):
            raise AssertionError("No debe consultar la presentacion si no se solicito.")
        return presentacion

    async def listar_falso(sesion: Any, **filtros: Any) -> list[dict[str, Any]]:
        llamadas.update(filtros)
        return filas

    monkeypatch.setattr(modulo_historial, "obtener_producto_historial", producto_falso)
    monkeypatch.setattr(
        modulo_historial, "obtener_establecimiento_historial", establecimiento_falso
    )
    monkeypatch.setattr(modulo_historial, "obtener_presentacion_historial", presentacion_falso)
    monkeypatch.setattr(modulo_historial, "listar_reportes_serie", listar_falso)


@pytest.mark.asyncio
async def test_servicio_mapea_la_serie_y_aplica_el_limite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El servicio mapea la serie al DTO y delega el limite y truncado al dominio."""
    llamadas: dict[str, Any] = {}
    filas = [
        _fila_reporte(UUID(int=201), DESDE),
        _fila_reporte(UUID(int=202), DESDE + timedelta(days=1), precio_cop=6000, es_demo=True),
    ]
    _montar_repositorio(
        monkeypatch,
        producto={"id": PRODUCTO_ID, "nombre": "Arroz", "unidad_base": "g"},
        filas=filas,
        llamadas=llamadas,
    )
    servicio = ServicioHistorial(object(), ahora=HASTA)  # type: ignore[arg-type]

    respuesta = await servicio.obtener_historial(
        producto_id=PRODUCTO_ID,
        establecimiento_id=ESTABLECIMIENTO_ID,
        desde=DESDE,
        hasta=HASTA,
    )

    datos = respuesta.datos
    assert datos.producto.id == PRODUCTO_ID
    assert datos.producto.nombre == "Arroz"
    assert datos.producto.unidad_base == "g"
    assert datos.producto.unidad_visualizacion == "kg"
    assert datos.establecimiento.id == ESTABLECIMIENTO_ID
    assert datos.establecimiento.municipio == "Armenia"
    assert datos.presentacion is None
    assert datos.desde == DESDE
    assert datos.hasta == HASTA
    assert [punto.id for punto in datos.puntos] == [UUID(int=201), UUID(int=202)]
    assert datos.total == 2
    assert datos.truncado is False
    assert datos.datos_de_demostracion is True
    assert datos.puntos[0].precio_por_unidad.valor_cop == 5000
    assert datos.puntos[0].precio_por_unidad.por == "kg"
    assert datos.puntos[0].cantidad_base == 1000.0
    assert llamadas == {
        "producto_id": PRODUCTO_ID,
        "establecimiento_id": ESTABLECIMIENTO_ID,
        "desde": DESDE,
        "hasta": HASTA,
        "presentacion_id": None,
    }

    respuesta_corta = await servicio.obtener_historial(
        producto_id=PRODUCTO_ID,
        establecimiento_id=ESTABLECIMIENTO_ID,
        desde=DESDE,
        hasta=HASTA,
        limite=1,
    )
    datos_corta = respuesta_corta.datos
    assert [punto.id for punto in datos_corta.puntos] == [UUID(int=202)]
    assert datos_corta.total == 1
    assert datos_corta.truncado is True


@pytest.mark.asyncio
async def test_servicio_usa_ventana_de_90_dias_por_defecto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin fechas explícitas, la ventana termina en 'ahora' y dura 90 días."""
    _montar_repositorio(
        monkeypatch,
        producto={"id": PRODUCTO_ID, "nombre": "Arroz", "unidad_base": "g"},
        filas=[_fila_reporte(UUID(int=301), DESDE)],
        llamadas={},
    )
    servicio = ServicioHistorial(object(), ahora=HASTA)  # type: ignore[arg-type]

    respuesta = await servicio.obtener_historial(
        producto_id=PRODUCTO_ID,
        establecimiento_id=ESTABLECIMIENTO_ID,
    )

    assert respuesta.datos.hasta == HASTA
    assert respuesta.datos.desde == HASTA - VENTANA_MAXIMA


@pytest.mark.asyncio
async def test_servicio_normaliza_la_ventana_a_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una ventana con offset -05:00 se consulta y se devuelve normalizada a UTC."""
    llamadas: dict[str, Any] = {}
    zona_colombia = timezone(timedelta(hours=-5))
    hasta_local = datetime(2026, 11, 1, 7, 0, 0, tzinfo=zona_colombia)
    desde_local = hasta_local - VENTANA_MAXIMA
    _montar_repositorio(
        monkeypatch,
        producto={"id": PRODUCTO_ID, "nombre": "Arroz", "unidad_base": "g"},
        filas=[_fila_reporte(UUID(int=303), DESDE)],
        llamadas=llamadas,
    )
    servicio = ServicioHistorial(object(), ahora=HASTA)  # type: ignore[arg-type]

    respuesta = await servicio.obtener_historial(
        producto_id=PRODUCTO_ID,
        establecimiento_id=ESTABLECIMIENTO_ID,
        desde=desde_local,
        hasta=hasta_local,
    )

    datos = respuesta.datos
    assert datos.hasta == HASTA
    assert datos.desde == DESDE
    assert datos.hasta.utcoffset() == timedelta(0)
    assert datos.desde.utcoffset() == timedelta(0)
    assert llamadas["hasta"] == HASTA
    assert llamadas["desde"] == DESDE
    assert llamadas["hasta"].utcoffset() == timedelta(0)
    assert llamadas["desde"].utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_servicio_incluye_la_presentacion_solicitada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si se pide una presentación activa, el DTO la identifica y los puntos la respetan."""
    llamadas: dict[str, Any] = {}
    _montar_repositorio(
        monkeypatch,
        producto={"id": PRODUCTO_ID, "nombre": "Arroz", "unidad_base": "g"},
        filas=[_fila_reporte(UUID(int=302), DESDE)],
        llamadas=llamadas,
        presentacion={"id": PRESENTACION_ID, "etiqueta": "Arroz 1 kg"},
    )
    servicio = ServicioHistorial(object(), ahora=HASTA)  # type: ignore[arg-type]

    respuesta = await servicio.obtener_historial(
        producto_id=PRODUCTO_ID,
        establecimiento_id=ESTABLECIMIENTO_ID,
        presentacion_id=PRESENTACION_ID,
    )

    datos = respuesta.datos
    assert datos.presentacion is not None
    assert datos.presentacion.id == PRESENTACION_ID
    assert datos.presentacion.etiqueta == "Arroz 1 kg"
    assert all(punto.presentacion_id == PRESENTACION_ID for punto in datos.puntos)
    assert llamadas["presentacion_id"] == PRESENTACION_ID


@pytest.mark.asyncio
async def test_servicio_rechaza_producto_inexistente(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un producto inexistente o inactivo se traduce en un 404 de negocio."""
    _montar_repositorio(monkeypatch, producto=None, filas=[], llamadas={})

    with pytest.raises(NoEncontradoError, match="Producto no encontrado o inactivo"):
        await ServicioHistorial(object(), ahora=HASTA).obtener_historial(  # type: ignore[arg-type]
            producto_id=PRODUCTO_ID,
            establecimiento_id=ESTABLECIMIENTO_ID,
            desde=DESDE,
            hasta=HASTA,
        )


@pytest.mark.asyncio
async def test_servicio_rechaza_establecimiento_inexistente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un establecimiento inexistente o inactivo se traduce en un 404 de negocio."""
    _montar_repositorio(
        monkeypatch,
        producto={"id": PRODUCTO_ID, "nombre": "Arroz", "unidad_base": "g"},
        filas=[],
        llamadas={},
        establecimiento=None,
    )

    with pytest.raises(NoEncontradoError, match="Establecimiento no encontrado o inactivo"):
        await ServicioHistorial(object(), ahora=HASTA).obtener_historial(  # type: ignore[arg-type]
            producto_id=PRODUCTO_ID,
            establecimiento_id=ESTABLECIMIENTO_ID,
            desde=DESDE,
            hasta=HASTA,
        )


@pytest.mark.asyncio
async def test_servicio_rechaza_presentacion_inexistente(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una presentacion inexistente o inactiva se traduce en un 404 de negocio."""
    _montar_repositorio(
        monkeypatch,
        producto={"id": PRODUCTO_ID, "nombre": "Arroz", "unidad_base": "g"},
        filas=[],
        llamadas={},
        presentacion=None,
    )

    with pytest.raises(NoEncontradoError, match="Presentación no encontrada o inactiva"):
        await ServicioHistorial(object(), ahora=HASTA).obtener_historial(  # type: ignore[arg-type]
            producto_id=PRODUCTO_ID,
            establecimiento_id=ESTABLECIMIENTO_ID,
            presentacion_id=PRESENTACION_ID,
            desde=DESDE,
            hasta=HASTA,
        )


def _punto_valido() -> dict[str, Any]:
    """Payload minimo valido de un punto publico del historial."""
    return {
        "id": str(UUID(int=401)),
        "observado_en": DESDE.isoformat(),
        "precio_cop": 5000,
        "precio_por_unidad": {"valor_cop": 5000, "por": "kg"},
        "origen": "usuario",
        "estado": "aceptado",
        "es_demo": False,
        "presentacion_id": None,
        "cantidad_base": 1000.0,
    }


def _datos_validos() -> dict[str, Any]:
    """Payload minimo valido del cuerpo de datos del historial."""
    return {
        "producto": {
            "id": str(PRODUCTO_ID),
            "nombre": "Arroz",
            "unidad_base": "g",
            "unidad_visualizacion": "kg",
        },
        "establecimiento": {
            "id": str(ESTABLECIMIENTO_ID),
            "nombre": "Tienda de prueba",
            "municipio": "Armenia",
        },
        "presentacion": None,
        "desde": DESDE.isoformat(),
        "hasta": HASTA.isoformat(),
        "puntos": [_punto_valido()],
        "total": 1,
        "truncado": False,
        "datos_de_demostracion": False,
    }


def test_modelos_historial_aceptan_el_payload_valido() -> None:
    """Los tres DTO publicos aceptan un payload completo sin campos adicionales."""
    punto = PuntoHistorial.model_validate(_punto_valido())
    datos = DatosHistorial.model_validate(_datos_validos())
    respuesta = RespuestaHistorial.model_validate({"datos": _datos_validos()})

    assert punto.origen == "usuario"
    assert punto.precio_por_unidad.valor_cop == 5000
    assert datos.total == 1
    assert respuesta.datos.puntos[0].id == UUID(int=401)


@pytest.mark.parametrize(
    "campo_extra",
    ["reportante_id", "huella_red", "alias", "correo", "email", "ip", "lat", "lng"],
)
def test_punto_historial_rechaza_campos_extra(campo_extra: str) -> None:
    """El punto no admite campos distintos al contrato publico."""
    with pytest.raises(ValidationError) as capturado:
        PuntoHistorial.model_validate({**_punto_valido(), campo_extra: "prohibido"})

    assert capturado.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    "campo_extra",
    ["reportante_id", "huella_red", "alias", "correo", "email", "ip", "lat", "lng"],
)
def test_datos_historial_rechazan_campos_extra(campo_extra: str) -> None:
    """El cuerpo de datos no admite campos distintos al contrato publico."""
    with pytest.raises(ValidationError) as capturado:
        DatosHistorial.model_validate({**_datos_validos(), campo_extra: "prohibido"})

    assert capturado.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("campo_extra", ["datos_privados", "pii"])
def test_respuesta_historial_rechaza_campos_extra(campo_extra: str) -> None:
    """La respuesta completa no admite bloques adicionales fuera de 'datos'."""
    with pytest.raises(ValidationError) as capturado:
        RespuestaHistorial.model_validate(
            {"datos": _datos_validos(), campo_extra: {"reportante_id": "filtrado"}}
        )

    assert capturado.value.errors()[0]["type"] == "extra_forbidden"
