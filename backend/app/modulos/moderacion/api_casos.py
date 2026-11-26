"""Endpoints REST para moderacion de casos, sanciones, auditoria y parametros."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.bd import obtener_sesion
from app.compartido.dependencias import obtener_puerto_cache
from app.compartido.seguridad import (
    UsuarioAutenticado,
    requiere_rol,
    requiere_usuario_autenticado_base,
)
from app.modulos.moderacion.esquemas_casos import (
    ActualizarParametrosEntrada,
    ApelacionSancionEntrada,
    CasoDetalleRespuesta,
    ListaAuditoriaRespuesta,
    ListaCasosRespuesta,
    ListaParametrosRespuesta,
    ResolverApelacionEntrada,
    ResolverCasoEntrada,
    SancionDirectaEntrada,
    UsuarioModeracionRespuesta,
)
from app.modulos.moderacion.servicio_casos import ServicioCasosModeracion
from app.modulos.moderacion.servicio_parametros import ServicioParametros
from app.modulos.moderacion.servicio_sanciones import ServicioSancionesAuditoria
from app.puertos.cache import PuertoCache

router = APIRouter(prefix="/moderacion", tags=["Moderacion de Casos y Parametros"])


@router.get("/casos", summary="Listar casos de moderacion")
async def listar_casos(
    _usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
    estado: Annotated[str | None, Query()] = None,
    tipo: Annotated[str | None, Query()] = None,
    prioridad: Annotated[int | None, Query(ge=1, le=5)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListaCasosRespuesta:
    servicio = ServicioCasosModeracion(sesion, cache)
    return await servicio.listar_casos(estado, tipo, prioridad, limite, offset)


@router.get("/casos/{id}", summary="Detalle de caso de moderacion")
async def obtener_caso(
    id: UUID,
    _usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
) -> CasoDetalleRespuesta:
    servicio = ServicioCasosModeracion(sesion, cache)
    return await servicio.obtener_caso(id)


@router.post("/casos/{id}/resolver", summary="Resolver caso de moderacion")
async def resolver_caso(
    id: UUID,
    entrada: ResolverCasoEntrada,
    moderador: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
) -> CasoDetalleRespuesta:
    servicio = ServicioCasosModeracion(sesion, cache)
    return await servicio.resolver_caso(id, entrada, moderador)


@router.get("/usuarios/{id}", summary="Consultar usuario para moderacion")
async def obtener_usuario_moderacion(
    id: UUID,
    _moderador: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> UsuarioModeracionRespuesta:
    servicio = ServicioSancionesAuditoria(sesion)
    return await servicio.obtener_usuario_moderacion(id)


@router.post(
    "/sanciones", status_code=status.HTTP_201_CREATED, summary="Aplicar sancion directa a usuario"
)
async def crear_sancion_directa(
    entrada: SancionDirectaEntrada,
    moderador: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> dict[str, Any]:
    servicio = ServicioSancionesAuditoria(sesion)
    sanc_id = await servicio.crear_sancion_directa(entrada, moderador)
    return {"id": str(sanc_id), "mensaje": "Sancion aplicada exitosamente"}


@router.post("/sanciones/{id}/apelacion", summary="Radicar apelacion a una sancion")
async def radicar_apelacion(
    id: UUID,
    entrada: ApelacionSancionEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario_autenticado_base)],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> dict[str, str]:
    servicio = ServicioSancionesAuditoria(sesion)
    await servicio.registrar_apelacion(id, entrada, usuario)
    return {"mensaje": "Apelacion radicada exitosamente"}


@router.post("/sanciones/{id}/resolver-apelacion", summary="Resolver apelacion a una sancion")
async def resolver_apelacion(
    id: UUID,
    entrada: ResolverApelacionEntrada,
    moderador: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> dict[str, str]:
    servicio = ServicioSancionesAuditoria(sesion)
    await servicio.resolver_apelacion(id, entrada, moderador)
    return {"mensaje": "Apelacion resuelta exitosamente"}


@router.get("/auditoria", summary="Consultar bitacora de auditoria")
async def listar_auditoria(
    _moderador: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    entidad: Annotated[str | None, Query()] = None,
    accion: Annotated[str | None, Query()] = None,
    actor_id: Annotated[UUID | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListaAuditoriaRespuesta:
    servicio = ServicioSancionesAuditoria(sesion)
    return await servicio.listar_auditoria(entidad, accion, actor_id, limite, offset)


@router.post("/recalcular-precio-vigente", summary="Forzar recalculacion de precio vigente")
async def recalcular_precio_vigente(
    moderador: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
    presentacion_id: Annotated[UUID | None, Query()] = None,
    establecimiento_id: Annotated[UUID | None, Query()] = None,
) -> dict[str, Any]:
    servicio = ServicioCasosModeracion(sesion, cache)
    return await servicio.recalcular_precio_vigente_manual(
        moderador, presentacion_id, establecimiento_id
    )


@router.get("/parametros", summary="Consultar los 43 parametros de negocio")
async def listar_parametros(
    _moderador: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> ListaParametrosRespuesta:
    servicio = ServicioParametros(sesion)
    return await servicio.listar_parametros()


@router.put("/parametros", summary="Actualizar parametros de negocio")
async def actualizar_parametros(
    entrada: ActualizarParametrosEntrada,
    moderador: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> ListaParametrosRespuesta:
    servicio = ServicioParametros(sesion)
    return await servicio.actualizar_parametros(entrada, moderador)
