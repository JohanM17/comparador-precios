"""Endpoints para moderacion de catalogo, tiendas, sugerencias y catalogo externo."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.bd import obtener_sesion
from app.compartido.seguridad import UsuarioAutenticado, requiere_rol, requiere_usuario
from app.modulos.moderacion.esquemas import (
    AprobarSugerenciaEntrada,
    ConsultaCatalogoExternoRespuesta,
    EstablecimientoActualizarEntrada,
    EstablecimientoCrearEntrada,
    PresentacionActualizarEntrada,
    PresentacionCrearEntrada,
    ProductoActualizarEntrada,
    ProductoCrearEntrada,
    RechazarSugerenciaEntrada,
    SugerenciaPresentacionEntrada,
)
from app.modulos.moderacion.servicio import ServicioModeracion
from app.puertos.catalogo_externo import PuertoCatalogoExterno

router = APIRouter(tags=["moderacion"])


def obtener_puerto_catalogo() -> PuertoCatalogoExterno | None:
    """Punto de extension inyectado por FastAPI en la raiz de composicion."""
    return None


def obtener_servicio_moderacion(
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    puerto_catalogo: Annotated[PuertoCatalogoExterno | None, Depends(obtener_puerto_catalogo)],
) -> ServicioModeracion:
    """Proveedor de dependencia para el servicio de moderacion."""
    return ServicioModeracion(sesion, puerto_catalogo=puerto_catalogo)


@router.post(
    "/moderacion/productos",
    status_code=status.HTTP_201_CREATED,
    summary="Crear producto en catalogo",
)
async def crear_producto_moderacion(
    entrada: ProductoCrearEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> dict[str, Any]:
    """Crea un producto nuevo en el catalogo y asienta en auditoria."""
    return await servicio.crear_producto(entrada, usuario)


@router.patch(
    "/moderacion/productos/{id}",
    summary="Actualizar producto en catalogo",
)
async def actualizar_producto_moderacion(
    id: UUID,
    entrada: ProductoActualizarEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> dict[str, Any]:
    """Actualiza campos de un producto y registra antes/despues en auditoria."""
    return await servicio.actualizar_producto(id, entrada, usuario)


@router.post(
    "/moderacion/presentaciones",
    status_code=status.HTTP_201_CREATED,
    summary="Crear presentacion calculando cantidad_base",
)
async def crear_presentacion_moderacion(
    entrada: PresentacionCrearEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> dict[str, Any]:
    """Calcula cantidad_base con el dominio e inserta presentacion."""
    return await servicio.crear_presentacion(entrada, usuario)


@router.patch(
    "/moderacion/presentaciones/{id}",
    summary="Actualizar presentacion comercial",
)
async def actualizar_presentacion_moderacion(
    id: UUID,
    entrada: PresentacionActualizarEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> dict[str, Any]:
    """Actualiza presentacion y rechaza taxativamente cualquier cambio a cantidad_base."""
    return await servicio.actualizar_presentacion(id, entrada, usuario)


@router.post(
    "/moderacion/establecimientos",
    status_code=status.HTTP_201_CREATED,
    summary="Crear establecimiento en directorio",
)
async def crear_establecimiento_moderacion(
    entrada: EstablecimientoCrearEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> dict[str, Any]:
    """Da de alta una tienda georreferenciada con auditoria."""
    return await servicio.crear_establecimiento(entrada, usuario)


@router.patch(
    "/moderacion/establecimientos/{id}",
    summary="Actualizar datos de establecimiento",
)
async def actualizar_establecimiento_moderacion(
    id: UUID,
    entrada: EstablecimientoActualizarEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> dict[str, Any]:
    """Actualiza datos y geometria espacial de establecimiento."""
    return await servicio.actualizar_establecimiento(id, entrada, usuario)


@router.get(
    "/moderacion/catalogo-externo",
    summary="Consultar producto por codigo de barras en fuentes externas",
)
async def consultar_catalogo_externo_endpoint(
    codigo_barras: Annotated[str, Query(pattern=r"^[0-9]{8,14}$")],
    _usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> ConsultaCatalogoExternoRespuesta:
    """Consulta Open Food Facts con Circuit Breaker en memoria."""
    return await servicio.consultar_catalogo_externo(codigo_barras)


@router.post(
    "/sugerencias-presentacion",
    status_code=status.HTTP_201_CREATED,
    summary="Enviar sugerencia de nueva presentacion comercial",
)
async def enviar_sugerencia_presentacion(
    entrada: SugerenciaPresentacionEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> dict[str, Any]:
    """Registra sugerencia previa validacion de autorizacion Ley 1581."""
    return await servicio.registrar_sugerencia_presentacion(entrada, usuario)


@router.post(
    "/moderacion/sugerencias/{id}/aprobar",
    summary="Aprobar sugerencia de presentacion",
)
async def aprobar_sugerencia_presentacion(
    id: UUID,
    entrada: AprobarSugerenciaEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> dict[str, Any]:
    """Aprueba la sugerencia creando la presentacion oficial con auditoria."""
    return await servicio.aprobar_sugerencia(id, entrada, usuario)


@router.post(
    "/moderacion/sugerencias/{id}/rechazar",
    summary="Rechazar sugerencia de presentacion",
)
async def rechazar_sugerencia_presentacion(
    id: UUID,
    entrada: RechazarSugerenciaEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    servicio: Annotated[ServicioModeracion, Depends(obtener_servicio_moderacion)],
) -> dict[str, Any]:
    """Rechaza la sugerencia archivando el motivo en auditoria."""
    return await servicio.rechazar_sugerencia(id, entrada, usuario)
