"""Endpoints de la API REST para el modulo de cuentas y derechos Ley 1581."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.bd import sesion_transaccional
from app.compartido.dependencias import obtener_puerto_cache
from app.compartido.seguridad import (
    UsuarioAutenticado,
    requiere_usuario,
    requiere_usuario_autenticado_base,
)
from app.modulos.cuentas.esquemas import (
    ActualizarAliasEntrada,
    AutorizacionEntrada,
    AutorizacionRespuesta,
    EliminarCuentaRespuesta,
    PerfilUsuarioRespuesta,
    PoliticaTratamientoRespuesta,
)
from app.modulos.cuentas.servicio import ServicioCuentas
from app.puertos.almacenamiento import PuertoAlmacenamientoFotos
from app.puertos.auth_admin import PuertoAuthAdmin
from app.puertos.cache import PuertoCache

router = APIRouter(tags=["Cuentas y Privacidad"])


def obtener_puerto_almacenamiento() -> PuertoAlmacenamientoFotos:
    """Proveedor inyectable del puerto de almacenamiento (inyectado en main.py)."""
    raise NotImplementedError("El puerto de almacenamiento debe ser inyectado por FastAPI.")


def obtener_puerto_auth_admin() -> PuertoAuthAdmin:
    """Proveedor inyectable del cliente admin de Supabase Auth."""
    raise NotImplementedError("El puerto de auth admin debe ser inyectado por FastAPI.")


def obtener_servicio_cuentas(
    puerto_almacenamiento: Annotated[
        PuertoAlmacenamientoFotos, Depends(obtener_puerto_almacenamiento)
    ],
    puerto_cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
    puerto_auth_admin: Annotated[PuertoAuthAdmin, Depends(obtener_puerto_auth_admin)],
) -> ServicioCuentas:
    """Instancia del servicio de cuentas con sesion y puertos inyectados."""
    # Nota: la sesion se abre dentro de cada endpoint para garantizar transaccionalidad
    return ServicioCuentas(
        sesion=None,  # type: ignore[arg-type]
        puerto_almacenamiento=puerto_almacenamiento,
        puerto_cache=puerto_cache,
        puerto_auth_admin=puerto_auth_admin,
    )


@router.get(
    "/legal/politica-tratamiento",
    summary="Politica publica de tratamiento de datos personales",
)
async def consultar_politica_tratamiento() -> PoliticaTratamientoRespuesta:
    """Retorna la version vigente, finalidades y correo de atencion de derechos ARCO."""
    async with sesion_transaccional() as sesion:
        servicio = ServicioCuentas(sesion=sesion)
        return servicio.obtener_politica_tratamiento()


@router.post(
    "/mi-cuenta/autorizacion",
    status_code=201,
    summary="Registrar autorizacion previa de tratamiento de datos",
)
async def registrar_autorizacion_usuario(
    entrada: AutorizacionEntrada,
    response: Response,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
) -> AutorizacionRespuesta:
    """Registra el consentimiento expreso e informado de un reportante autenticado."""
    async with sesion_transaccional() as sesion:
        servicio = ServicioCuentas(sesion=sesion)
        resultado, fue_creada = await servicio.registrar_autorizacion_con_estado(usuario, entrada)
        if not fue_creada:
            response.status_code = 200
        return resultado


@router.get(
    "/mi-cuenta",
    summary="Consultar perfil del titular y autorizacion vigente",
)
async def obtener_perfil_usuario(
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario_autenticado_base)],
) -> PerfilUsuarioRespuesta:
    """Retorna el perfil del usuario autenticado; permite acceso a suspendidas (Ley 1581)."""
    async with sesion_transaccional() as sesion:
        servicio = ServicioCuentas(sesion=sesion)
        return await servicio.obtener_mi_cuenta(usuario)


@router.patch(
    "/mi-cuenta",
    summary="Actualizar alias publico del titular",
)
async def actualizar_alias_usuario(
    entrada: ActualizarAliasEntrada,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
) -> PerfilUsuarioRespuesta:
    """Modifica el alias publico verificando unicidad."""
    async with sesion_transaccional() as sesion:
        servicio = ServicioCuentas(sesion=sesion)
        return await servicio.actualizar_mi_alias(usuario, entrada)


@router.delete(
    "/mi-cuenta",
    summary="Ejercicio del derecho de supresion y anonimizacion irreversible",
)
async def eliminar_cuenta_usuario(
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario_autenticado_base)],
    puerto_almacenamiento: Annotated[
        PuertoAlmacenamientoFotos, Depends(obtener_puerto_almacenamiento)
    ],
    puerto_cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
    puerto_auth_admin: Annotated[PuertoAuthAdmin, Depends(obtener_puerto_auth_admin)],
) -> EliminarCuentaRespuesta:
    """Anonimiza todos los reportes, fotos y da de baja la cuenta (FR-007)."""
    async with sesion_transaccional() as sesion:
        servicio = ServicioCuentas(
            sesion=sesion,
            puerto_almacenamiento=puerto_almacenamiento,
            puerto_cache=puerto_cache,
            puerto_auth_admin=puerto_auth_admin,
        )
        resultado = await servicio.eliminar_mi_cuenta(usuario)

    # La cache y la credencial de Auth se tocan solo despues del commit. Si la
    # API externa falla, la baja local ya quedo consumada y se responde 200.
    await servicio.invalidar_cache_baja()
    await servicio.eliminar_credencial_auth(usuario.id)
    return resultado
