"""Endpoints de la API REST para reportes de precios, historial y comparaciones."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.bd import sesion_transaccional
from app.compartido.seguridad import UsuarioAutenticado, requiere_autorizacion_datos
from app.modulos.precios.esquemas import (
    CrearReporteEntrada,
    CrearReporteRespuesta,
    MisReportesRespuesta,
    RespuestaComparacion,
)
from app.modulos.precios.servicio import ServicioPrecios
from app.modulos.precios.servicio_comparacion import ServicioComparacion
from app.puertos.cache import PuertoCache

router = APIRouter(tags=["Precios y Comparaciones"])


def obtener_puerto_cache() -> PuertoCache:
    """Proveedor inyectable del puerto de cache (configurado en main.py)."""
    raise NotImplementedError("El puerto de cache debe ser inyectado por FastAPI.")


@router.post(
    "/reportes",
    status_code=201,
    summary="Registrar un reporte de precio con idempotencia (Flujo F2)",
)
async def crear_reporte(
    request: Request,
    response: Response,
    entrada: CrearReporteEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_autorizacion_datos)],
    cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CrearReporteRespuesta:
    ip_cliente = request.client.host if request.client else "127.0.0.1"

    async with sesion_transaccional() as sesion:
        servicio = ServicioPrecios(sesion=sesion, puerto_cache=cache)
        resultado, fue_creado = await servicio.registrar_reporte(
            usuario=usuario,
            idempotency_key=idempotency_key,
            entrada=entrada,
            ip_cliente=ip_cliente,
        )

        if not fue_creado:
            response.status_code = 200

        return resultado


@router.get(
    "/mis-reportes",
    summary="Consultar historial propio de reportes con estado visible",
)
async def mis_reportes(
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_autorizacion_datos)],
    cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
    pagina: Annotated[int, Query(ge=1)] = 1,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MisReportesRespuesta:
    async with sesion_transaccional() as sesion:
        servicio = ServicioPrecios(sesion=sesion, puerto_cache=cache)
        return await servicio.obtener_mis_reportes(usuario=usuario, pagina=pagina, limite=limite)


@router.get(
    "/productos/{id}/comparacion",
    summary="Comparador publico neutral de precios en dos bloques (Flujo F1)",
)
async def comparar_precios_producto(
    id: UUID,
    cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
    presentacion_id: Annotated[UUID | None, Query()] = None,
    orden: Annotated[str, Query()] = "precio_unitario",
    lat: Annotated[float | None, Query()] = None,
    lng: Annotated[float | None, Query()] = None,
    radio_km: Annotated[float | None, Query()] = None,
) -> RespuestaComparacion:
    async with sesion_transaccional() as sesion:
        servicio = ServicioComparacion(sesion=sesion, puerto_cache=cache)
        return await servicio.obtener_comparacion(
            producto_id=id,
            presentacion_id=presentacion_id,
            orden=orden,
            lat=lat,
            lng=lng,
            radio_km=radio_km,
        )
