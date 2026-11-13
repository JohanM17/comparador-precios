"""Endpoints publicos para directorio de establecimientos y solicitudes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.bd import obtener_sesion
from app.modulos.establecimientos.esquemas import (
    EstablecimientoDetalleRespuesta,
    ListaEstablecimientosRespuesta,
    SolicitudCorreccionEntrada,
    SolicitudCorreccionRespuesta,
)
from app.modulos.establecimientos.servicio import ServicioEstablecimientos

router = APIRouter(tags=["establecimientos"])


def obtener_servicio_establecimientos(
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> ServicioEstablecimientos:
    """Proveedor de dependencia para el servicio de establecimientos."""
    return ServicioEstablecimientos(sesion)


@router.get(
    "/establecimientos",
    summary="Directorio de establecimientos con filtro espacial",
)
async def listar_establecimientos_publicos(
    servicio: Annotated[ServicioEstablecimientos, Depends(obtener_servicio_establecimientos)],
    q: Annotated[str | None, Query(description="Nombre o direccion")] = None,
    tipo: Annotated[str | None, Query(description="tipo_establecimiento")] = None,
    municipio: Annotated[str | None, Query(description="Municipio")] = "Armenia",
    lat: Annotated[float | None, Query(ge=-90.0, le=90.0, description="Latitud")] = None,
    lng: Annotated[float | None, Query(ge=-180.0, le=180.0, description="Longitud")] = None,
    radio_km: Annotated[float, Query(gt=0.0, le=100.0, description="Radio en kilometros")] = 10.0,
    limite: Annotated[int, Query(ge=1, le=100, description="Limite de registros")] = 50,
) -> ListaEstablecimientosRespuesta:
    """Filtra establecimientos por texto, tipo y calcula distancia_m con PostGIS."""
    return await servicio.listar(
        termino=q,
        tipo=tipo,
        municipio=municipio,
        lat=lat,
        lng=lng,
        radio_km=radio_km,
        limite=limite,
    )


@router.get(
    "/establecimientos/{id}",
    summary="Ficha del establecimiento y precios vigentes",
)
async def obtener_detalle_establecimiento(
    id: UUID,
    servicio: Annotated[ServicioEstablecimientos, Depends(obtener_servicio_establecimientos)],
    lat: Annotated[float | None, Query(ge=-90.0, le=90.0, description="Latitud")] = None,
    lng: Annotated[float | None, Query(ge=-180.0, le=180.0, description="Longitud")] = None,
) -> EstablecimientoDetalleRespuesta:
    """Devuelve los datos de la tienda y sus precios vigentes activos."""
    return await servicio.obtener_por_id(id, lat=lat, lng=lng)


@router.post(
    "/establecimientos/{id}/solicitudes-correccion",
    status_code=status.HTTP_201_CREATED,
    summary="Enviar solicitud ciudadana de correccion de datos",
)
async def enviar_solicitud_correccion_tienda(
    id: UUID,
    entrada: SolicitudCorreccionEntrada,
    request: Request,
    servicio: Annotated[ServicioEstablecimientos, Depends(obtener_servicio_establecimientos)],
) -> SolicitudCorreccionRespuesta:
    """Recibe reporte ciudadano de datos erroneros de tienda y abre caso de moderacion."""
    ip_cliente = request.client.host if request.client else "127.0.0.1"
    return await servicio.procesar_solicitud_correccion(
        establecimiento_id=id,
        entrada=entrada,
        ip_cliente=ip_cliente,
    )
