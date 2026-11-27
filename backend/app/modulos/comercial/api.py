"""Endpoints del modulo comercial: titularidad, precios oficiales y promociones (Etapa 2)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.bd import obtener_sesion
from app.compartido.dependencias import obtener_puerto_cache
from app.compartido.seguridad import UsuarioAutenticado, requiere_rol, requiere_usuario
from app.modulos.comercial.esquemas import (
    EstablecimientoComercioResumen,
    ListaSolicitudesRespuesta,
    PreciosLoteEntrada,
    PreciosLoteRespuesta,
    PromocionEntrada,
    PromocionRespuesta,
    ReclamoComercioEntrada,
    ReclamoComercioRespuesta,
    RevalidarRespuesta,
    VerificarComercioEntrada,
    VerificarComercioRespuesta,
)
from app.modulos.comercial.servicio import ServicioComercial
from app.puertos.cache import PuertoCache

router = APIRouter(tags=["comercial"])


def obtener_servicio_comercial(
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
) -> ServicioComercial:
    """Proveedor de dependencia del servicio comercial."""
    return ServicioComercial(sesion=sesion, puerto_cache=cache)


@router.post(
    "/comercio/reclamos",
    response_model=ReclamoComercioRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Reclamar la titularidad de un establecimiento",
)
async def reclamar_titularidad(
    entrada: ReclamoComercioEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
    servicio: Annotated[ServicioComercial, Depends(obtener_servicio_comercial)],
) -> Any:
    """Cualquier cuenta puede reclamar un establecimiento; la decision es de un moderador."""
    return await servicio.reclamar_titularidad(entrada, usuario)


@router.get(
    "/moderacion/comercios",
    response_model=ListaSolicitudesRespuesta,
    summary="Cola de reclamos de titularidad sin resolver",
)
async def listar_solicitudes_comercio(
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioComercial, Depends(obtener_servicio_comercial)],
    limite: int = Query(default=50, ge=1, le=200),
) -> Any:
    """Sin esta cola un reclamo no tendria quien lo mire: solo se podria resolver
    quien ya conociera su identificador."""
    datos = await servicio.listar_solicitudes_pendientes(usuario, limite)
    return {"datos": datos, "total": len(datos)}


@router.post(
    "/moderacion/comercios/{solicitud_id}/verificar",
    response_model=VerificarComercioRespuesta,
    summary="Aprobar o rechazar un reclamo de titularidad",
)
async def verificar_comercio(
    solicitud_id: UUID,
    entrada: VerificarComercioEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioComercial, Depends(obtener_servicio_comercial)],
) -> Any:
    """Al aprobar, enlaza el establecimiento con la cuenta y le asigna el rol de comercio."""
    return await servicio.verificar_comercio(solicitud_id, entrada, usuario)


@router.get(
    "/comercio/establecimientos",
    response_model=list[EstablecimientoComercioResumen],
    summary="Listar los establecimientos verificados del comercio",
)
async def listar_establecimientos(
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("comercio", "admin"))],
    servicio: Annotated[ServicioComercial, Depends(obtener_servicio_comercial)],
) -> Any:
    """Incluye cuantos precios oficiales tiene cada uno y cuantos piden revalidacion."""
    return await servicio.listar_establecimientos(usuario)


@router.put(
    "/comercio/establecimientos/{establecimiento_id}/precios",
    response_model=PreciosLoteRespuesta,
    summary="Publicar o actualizar precios oficiales en lote",
)
async def publicar_precios(
    establecimiento_id: UUID,
    entrada: PreciosLoteEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("comercio", "admin"))],
    servicio: Annotated[ServicioComercial, Depends(obtener_servicio_comercial)],
) -> Any:
    """Hasta 200 precios por lote. Recalcula el precio vigente de cada par al instante."""
    return await servicio.publicar_precios(establecimiento_id, entrada, usuario)


@router.post(
    "/comercio/establecimientos/{establecimiento_id}/revalidar",
    response_model=RevalidarRespuesta,
    summary="Confirmar que los precios siguen igual",
)
async def revalidar_precios(
    establecimiento_id: UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("comercio", "admin"))],
    servicio: Annotated[ServicioComercial, Depends(obtener_servicio_comercial)],
) -> Any:
    """Accion «Todo sigue igual»: renueva la fecha sin cambiar ningun valor (D-06)."""
    return await servicio.revalidar(establecimiento_id, usuario)


@router.get(
    "/comercio/establecimientos/{establecimiento_id}/promociones",
    response_model=list[PromocionRespuesta],
    summary="Listar las promociones del establecimiento",
)
async def listar_promociones(
    establecimiento_id: UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("comercio", "admin"))],
    servicio: Annotated[ServicioComercial, Depends(obtener_servicio_comercial)],
) -> Any:
    """Incluye las revocadas, para que el comercio vea su historial."""
    return await servicio.listar_promociones(establecimiento_id, usuario)


@router.post(
    "/comercio/establecimientos/{establecimiento_id}/promociones",
    response_model=PromocionRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Publicar una promocion",
)
async def crear_promocion(
    establecimiento_id: UUID,
    entrada: PromocionEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("comercio", "admin"))],
    servicio: Annotated[ServicioComercial, Depends(obtener_servicio_comercial)],
) -> Any:
    """Sin condiciones o sin vigencia declarada se responde 422 (Ley 1480, articulo 33)."""
    return await servicio.crear_promocion(establecimiento_id, entrada, usuario)


@router.delete(
    "/comercio/establecimientos/{establecimiento_id}/promociones/{promocion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revocar una promocion",
)
async def revocar_promocion(
    establecimiento_id: UUID,
    promocion_id: UUID,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("comercio", "admin"))],
    servicio: Annotated[ServicioComercial, Depends(obtener_servicio_comercial)],
) -> None:
    """La promocion queda inactiva y con fecha de revocacion; no se borra la fila."""
    await servicio.revocar_promocion(establecimiento_id, promocion_id, usuario)
