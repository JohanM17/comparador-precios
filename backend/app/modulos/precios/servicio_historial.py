"""Servicio de consulta del historial publico de precios (Historia A2, T-113).

Orquesta las validaciones, las consultas parametrizadas y el dominio puro de la
serie historica. No expone identidad, red, foto ni coordenadas del reportante.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.errores import NoEncontradoError, ValidacionError
from app.dominio.serie_precios import PuntoSeriePrecio, ReporteSerie, construir_serie
from app.modulos.precios.esquemas import (
    DatosHistorial,
    EstablecimientoHistorial,
    PrecioUnidad,
    PresentacionHistorial,
    ProductoHistorial,
    PuntoHistorial,
    RespuestaHistorial,
)
from app.modulos.precios.repositorio import (
    listar_reportes_serie,
    obtener_establecimiento_historial,
    obtener_presentacion_historial,
    obtener_producto_historial,
)

DIAS_MAXIMOS_HISTORIAL: Final[int] = 90
LIMITE_MINIMO_HISTORIAL: Final[int] = 1
LIMITE_MAXIMO_HISTORIAL: Final[int] = 500
MAPA_UNIDADES_VISUALIZACION: Final[dict[str, str]] = {
    "g": "kg",
    "ml": "l",
    "unidad": "unidad",
}


def _es_fecha_aware(fecha: datetime) -> bool:
    """Indica si la fecha tiene una zona horaria con desplazamiento definido."""
    return fecha.tzinfo is not None and fecha.utcoffset() is not None


def validar_parametros_historial(desde: datetime, hasta: datetime, limite: int) -> None:
    """Valida la ventana temporal y el limite antes de consultar la base de datos."""
    if not _es_fecha_aware(desde):
        raise ValidacionError("La fecha 'desde' debe incluir zona horaria.")
    if not _es_fecha_aware(hasta):
        raise ValidacionError("La fecha 'hasta' debe incluir zona horaria.")
    if desde > hasta:
        raise ValidacionError("La fecha 'desde' no puede ser posterior a 'hasta'.")
    if hasta - desde > timedelta(days=DIAS_MAXIMOS_HISTORIAL):
        raise ValidacionError("La ventana máxima del historial es de 90 días.")
    if not LIMITE_MINIMO_HISTORIAL <= limite <= LIMITE_MAXIMO_HISTORIAL:
        raise ValidacionError("El limite debe estar entre 1 y 500 puntos.")


def _mapear_reporte(fila: dict[str, Any]) -> ReporteSerie:
    """Convierte una fila publica del repositorio en un reporte de dominio."""
    return ReporteSerie(
        id=fila["id"],
        observado_en=fila["observado_en"],
        precio_cop=int(fila["precio_cop"]),
        cantidad_base=Decimal(str(fila["cantidad_base_snapshot"])),
        precio_por_base=Decimal(str(fila["precio_por_base"])),
        origen=str(fila["origen"]),
        estado=str(fila["estado"]),
        es_demo=bool(fila["es_demo"]),
        presentacion_id=fila["presentacion_id"],
    )


def _mapear_punto(punto: PuntoSeriePrecio) -> PuntoHistorial:
    """Convierte un punto de la serie de dominio en el DTO publico."""
    return PuntoHistorial(
        id=punto.id,
        observado_en=punto.observado_en,
        precio_cop=punto.precio_cop,
        precio_por_unidad=PrecioUnidad(
            valor_cop=punto.precio_por_unidad,
            por=punto.unidad_visualizacion,
        ),
        origen=punto.origen,
        estado=punto.estado,
        es_demo=punto.es_demo,
        presentacion_id=punto.presentacion_id,
        cantidad_base=float(punto.cantidad_base),
    )


class ServicioHistorial:
    """Implementa la consulta publica del historial de precios de un producto."""

    def __init__(self, sesion: AsyncSession, ahora: datetime | None = None) -> None:
        self.sesion = sesion
        self.ahora = ahora

    async def obtener_historial(
        self,
        *,
        producto_id: UUID,
        establecimiento_id: UUID,
        presentacion_id: UUID | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        limite: int = 200,
    ) -> RespuestaHistorial:
        """Devuelve la serie historica validada, limitada y libre de datos personales."""
        instante_actual = self.ahora if self.ahora is not None else datetime.now(UTC)
        hasta_efectivo = hasta if hasta is not None else instante_actual
        desde_efectivo = (
            desde if desde is not None else hasta_efectivo - timedelta(days=DIAS_MAXIMOS_HISTORIAL)
        )
        validar_parametros_historial(desde_efectivo, hasta_efectivo, limite)
        desde_efectivo = desde_efectivo.astimezone(UTC)
        hasta_efectivo = hasta_efectivo.astimezone(UTC)

        producto = await obtener_producto_historial(self.sesion, producto_id)
        if producto is None:
            raise NoEncontradoError("Producto no encontrado o inactivo.")

        establecimiento = await obtener_establecimiento_historial(self.sesion, establecimiento_id)
        if establecimiento is None:
            raise NoEncontradoError("Establecimiento no encontrado o inactivo.")

        presentacion: dict[str, Any] | None = None
        if presentacion_id is not None:
            presentacion = await obtener_presentacion_historial(
                self.sesion, presentacion_id, producto_id
            )
            if presentacion is None:
                raise NoEncontradoError("Presentación no encontrada o inactiva.")

        filas = await listar_reportes_serie(
            self.sesion,
            producto_id=producto_id,
            establecimiento_id=establecimiento_id,
            desde=desde_efectivo,
            hasta=hasta_efectivo,
            presentacion_id=presentacion_id,
        )
        resultado = construir_serie(
            [_mapear_reporte(fila) for fila in filas],
            desde=desde_efectivo,
            hasta=hasta_efectivo,
            unidad_base=str(producto["unidad_base"]),
            limite=limite,
        )

        unidad_base = str(producto["unidad_base"])
        unidad_visualizacion = MAPA_UNIDADES_VISUALIZACION[unidad_base]
        puntos = [_mapear_punto(punto) for punto in resultado.puntos]
        presentacion_dto = (
            PresentacionHistorial(
                id=presentacion["id"],
                etiqueta=str(presentacion["etiqueta"]),
            )
            if presentacion is not None
            else None
        )

        return RespuestaHistorial(
            datos=DatosHistorial(
                producto=ProductoHistorial(
                    id=producto["id"],
                    nombre=str(producto["nombre"]),
                    unidad_base=unidad_base,
                    unidad_visualizacion=unidad_visualizacion,
                ),
                establecimiento=EstablecimientoHistorial(
                    id=establecimiento["id"],
                    nombre=str(establecimiento["nombre"]),
                    municipio=str(establecimiento["municipio"]),
                ),
                presentacion=presentacion_dto,
                desde=desde_efectivo,
                hasta=hasta_efectivo,
                puntos=puntos,
                total=len(puntos),
                truncado=resultado.truncado,
                datos_de_demostracion=resultado.datos_de_demostracion,
            )
        )
