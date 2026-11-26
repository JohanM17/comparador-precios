"""Servicio de consulta y comparacion publica de precios con cache y neutralidad (T-26)."""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from opentelemetry.trace import StatusCode
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bd import sesion_transaccional
from app.compartido.errores import NoEncontradoError, ValidacionError
from app.compartido.telemetria import obtener_meter, obtener_tracer
from app.dominio.orden import ItemComparacion, ordenar_comparacion
from app.dominio.unidades import calcular_precio_visualizacion
from app.modulos.precios.esquemas import (
    DatosComparacion,
    EstablecimientoComparacion,
    ItemResultadoComparacion,
    MetaComparacion,
    PrecioUnidad,
    PresentacionComparacion,
    ProductoComparacion,
    RespuestaComparacion,
)
from app.puertos.cache import PuertoCache

tracer = obtener_tracer("app.modulos.precios.servicio_comparacion")
meter = obtener_meter("app.modulos.precios.servicio_comparacion")
_contador_comparaciones = meter.create_counter(
    "precios.comparaciones",
    unit="1",
    description="Comparaciones de precios servidas por acierto de cache",
)
_histograma_db_ms = meter.create_histogram(
    "precios.db_ms",
    unit="ms",
    description="Latencia de la consulta a base de datos en comparaciones",
)


def _calcular_haversine_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi, delta_lambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return int(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _validar_parametros_consulta(
    orden: str, presentacion_id: UUID | None, lat: float | None, lng: float | None
) -> None:
    if orden not in ("precio_unitario", "precio", "distancia"):
        raise ValidacionError(f"Criterio de orden '{orden}' no soportado.")
    if orden == "precio" and not presentacion_id:
        raise ValidacionError("El orden por 'precio' exige especificar 'presentacion_id'.")
    if orden == "distancia" and (lat is None or lng is None):
        raise ValidacionError("El orden por 'distancia' exige coordenadas 'lat' y 'lng'.")


def _procesar_fila_item(
    f: Any, lat: float | None, lng: float | None, radio_km: float | None
) -> tuple[ItemComparacion | None, int | None]:
    dist_m: int | None = None
    if lat is not None and lng is not None and f.est_lat is not None and f.est_lng is not None:
        dist_m = _calcular_haversine_metros(lat, lng, float(f.est_lat), float(f.est_lng))
        if radio_km is not None and dist_m > (radio_km * 1000):
            return None, None

    item = ItemComparacion(
        establecimiento_id=f.establecimiento_id,
        establecimiento_nombre=f.est_nombre,
        precio_cop=int(f.precio_cop),
        precio_por_base=Decimal(str(f.precio_por_base)),
        sello=str(f.sello),
        ultimo_reporte_en=f.ultimo_reporte_en,
        distancia_m=dist_m,
    )
    return item, dist_m


def _construir_item_dto(
    item: ItemComparacion, f: Any, dist_m: int | None, unidad_base: str
) -> ItemResultadoComparacion:
    val_unitario, por_unidad = calcular_precio_visualizacion(
        item.precio_por_base, unidad_base=unidad_base
    )
    est_dto = EstablecimientoComparacion(
        id=f.establecimiento_id,
        nombre=f.est_nombre,
        tipo=f.est_tipo,
        barrio=f.est_barrio,
        direccion=f.est_direccion,
        distancia_m=dist_m,
    )
    pres_dto = PresentacionComparacion(
        id=f.presentacion_id,
        etiqueta=f.pres_etiqueta,
        marca=f.pres_marca,
        cantidad_base=float(f.pres_cantidad_base),
    )
    return ItemResultadoComparacion(
        establecimiento=est_dto,
        presentacion=pres_dto,
        precio_cop=item.precio_cop,
        precio_oficial_cop=None,
        precio_por_unidad=PrecioUnidad(valor_cop=val_unitario, por=por_unidad),
        sello=item.sello,
        motivo_sello=f.motivo_sello,
        n_reportes_validos=int(f.n_reportes_validos),
        n_fuentes=int(f.n_fuentes),
        ultimo_reporte_en=f.ultimo_reporte_en,
        con_foto_prueba=bool(f.con_foto),
        es_bloque_secundario=item.es_bloque_secundario,
    )


class ServicioComparacion:
    """Implementa el Flujo F1 del comparador de precios con cache L1/L2 y neutralidad EC-06."""

    def __init__(
        self,
        puerto_cache: PuertoCache,
        sesion: AsyncSession | None = None,
    ) -> None:
        self.sesion = sesion
        self.cache = puerto_cache

    async def _consultar_bd(
        self,
        sesion: AsyncSession,
        producto_id: UUID,
        presentacion_id: UUID | None,
    ) -> tuple[Any, list[PresentacionComparacion], list[Any]]:
        sql_prod = text("""
            SELECT id, nombre, categoria_id, unidad_base
            FROM public.producto WHERE id = :pid AND activo = true;
        """)
        fila_prod = (await sesion.execute(sql_prod, {"pid": producto_id})).first()
        if not fila_prod:
            raise NoEncontradoError("Producto no encontrado o inactivo.")

        sql_pres = text("""
            SELECT id, etiqueta, marca, cantidad_base
            FROM public.presentacion WHERE producto_id = :pid AND activa = true
            ORDER BY cantidad_base ASC;
        """)
        filas_pres = (await sesion.execute(sql_pres, {"pid": producto_id})).fetchall()
        presentaciones_dto = [
            PresentacionComparacion(
                id=f.id, etiqueta=f.etiqueta, marca=f.marca, cantidad_base=float(f.cantidad_base)
            )
            for f in filas_pres
        ]

        sql_filas = text("""
            SELECT pv.presentacion_id, pv.establecimiento_id, pv.precio_cop,
                   pv.precio_por_base, pv.cantidad_base, pv.sello::text,
                   pv.motivo_sello, pv.n_reportes_validos, pv.n_fuentes,
                   pv.dispersion, pv.ultimo_reporte_en, pv.reporte_origen_id,
                   e.nombre as est_nombre, e.tipo::text as est_tipo,
                   e.barrio as est_barrio, e.direccion as est_direccion,
                   ST_Y(e.ubicacion::geometry) as est_lat,
                   ST_X(e.ubicacion::geometry) as est_lng,
                   pr.etiqueta as pres_etiqueta, pr.marca as pres_marca,
                   pr.cantidad_base as pres_cantidad_base,
                   (
                       SELECT foto_prueba_path IS NOT NULL
                       FROM public.reporte_precio rp
                       WHERE rp.id = pv.reporte_origen_id
                   ) as con_foto
            FROM public.precio_vigente pv
            JOIN public.establecimiento e ON pv.establecimiento_id = e.id
            JOIN public.presentacion pr ON pv.presentacion_id = pr.id
            WHERE pv.producto_id = :pid
              AND (CAST(:pres_id AS uuid) IS NULL OR pv.presentacion_id = CAST(:pres_id AS uuid))
              AND e.activo = true;
        """)
        filas = list(
            (
                await sesion.execute(sql_filas, {"pid": producto_id, "pres_id": presentacion_id})
            ).fetchall()
        )
        return fila_prod, presentaciones_dto, filas

    async def obtener_comparacion(
        self,
        producto_id: UUID,
        presentacion_id: UUID | None = None,
        orden: str = "precio_unitario",
        lat: float | None = None,
        lng: float | None = None,
        radio_km: float | None = None,
        ahora: datetime | None = None,
    ) -> RespuestaComparacion:
        """Obtiene la comparacion dentro de un span sin atributos de ubicacion."""
        with tracer.start_as_current_span(
            "precios.obtener_comparacion",
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            span.set_attribute("precios.orden", orden)
            span.set_attribute("precios.presentacion", presentacion_id is not None)
            if radio_km is not None:
                span.set_attribute("precios.radio_km", float(radio_km))
            try:
                respuesta, cache_hit, db_ms = await self._obtener_comparacion(
                    producto_id=producto_id,
                    presentacion_id=presentacion_id,
                    orden=orden,
                    lat=lat,
                    lng=lng,
                    radio_km=radio_km,
                    ahora=ahora,
                )
            except Exception as error:
                span.record_exception(error)
                span.set_status(StatusCode.ERROR, type(error).__name__)
                raise
            span.set_attribute("precios.cache_hit", cache_hit)
            span.set_attribute("precios.resultados_count", len(respuesta.datos.resultados))
            span.set_attribute("precios.db_ms", db_ms)
            span.set_status(StatusCode.OK)
            _contador_comparaciones.add(1, {"cache_hit": cache_hit})
            _histograma_db_ms.record(db_ms)
            return respuesta

    async def _obtener_comparacion(
        self,
        producto_id: UUID,
        presentacion_id: UUID | None = None,
        orden: str = "precio_unitario",
        lat: float | None = None,
        lng: float | None = None,
        radio_km: float | None = None,
        ahora: datetime | None = None,
    ) -> tuple[RespuestaComparacion, bool, float]:
        instante = ahora if ahora is not None else datetime.now(UTC)
        _validar_parametros_consulta(orden, presentacion_id, lat, lng)

        es_cacheable = lat is None and lng is None and radio_km is None
        subllave = f"armenia:{presentacion_id or 'todas'}:{orden}"

        if es_cacheable:
            datos_cache = await self.cache.obtener(producto_id, subllave)
            if datos_cache:
                return RespuestaComparacion.model_validate(datos_cache), True, 0.0

        inicio_bd = time.perf_counter()
        if self.sesion is not None:
            fila_prod, presentaciones_dto, filas = await self._consultar_bd(
                self.sesion, producto_id, presentacion_id
            )
        else:
            async with sesion_transaccional() as sesion:
                fila_prod, presentaciones_dto, filas = await self._consultar_bd(
                    sesion, producto_id, presentacion_id
                )
        db_ms = (time.perf_counter() - inicio_bd) * 1000.0

        items_dominio: list[ItemComparacion] = []
        mapa_filas: dict[UUID, tuple[Any, int | None]] = {}

        for f in filas:
            it, dist_m = _procesar_fila_item(f, lat, lng, radio_km)
            if it is not None:
                mapa_filas[f.establecimiento_id] = (f, dist_m)
                items_dominio.append(it)

        ordenados = ordenar_comparacion(items_dominio, criterio=orden)  # type: ignore[arg-type]
        unidad_base = str(fila_prod.unidad_base)
        _, unidad_vis = calcular_precio_visualizacion(Decimal("1"), unidad_base=unidad_base)

        resultados_dto = [
            _construir_item_dto(
                it,
                mapa_filas[it.establecimiento_id][0],
                mapa_filas[it.establecimiento_id][1],
                unidad_base,
            )
            for it in ordenados
        ]

        criterio_texto = "distancia" if orden == "distancia" else f"precio por {unidad_vis}"
        respuesta = RespuestaComparacion(
            datos=DatosComparacion(
                producto=ProductoComparacion(
                    id=fila_prod.id,
                    nombre=fila_prod.nombre,
                    categoria_id=fila_prod.categoria_id,
                    unidad_base=unidad_base,
                    unidad_visualizacion=unidad_vis,
                    presentaciones=presentaciones_dto,
                ),
                resultados=resultados_dto,
                promociones=[],  # EC-06: Bloque separado neutral
                meta=MetaComparacion(
                    criterio_orden=orden,
                    texto_neutralidad=(
                        f"Ordenado por {criterio_texto}. Las promociones no cambian el orden."
                    ),
                    bloques=["vigentes", "dudosos_y_desactualizados"],
                    generado_en=instante.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    datos_de_demostracion=False,
                ),
            )
        )

        if es_cacheable:
            await self.cache.guardar(
                producto_id, subllave, respuesta.model_dump(mode="json"), ttl_segundos=60
            )

        return respuesta, False, db_ms
