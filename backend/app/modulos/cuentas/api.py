"""Endpoints de la API REST para el modulo de cuentas y derechos Ley 1581."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.bd import sesion_transaccional
from app.compartido.seguridad import UsuarioAutenticado, requiere_usuario
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

router = APIRouter(tags=["Cuentas y Privacidad"])


def obtener_puerto_almacenamiento() -> PuertoAlmacenamientoFotos:
    """Proveedor inyectable del puerto de almacenamiento (inyectado en main.py)."""
    raise NotImplementedError("El puerto de almacenamiento debe ser inyectado por FastAPI.")


def obtener_servicio_cuentas(
    puerto_almacenamiento: Annotated[
        PuertoAlmacenamientoFotos, Depends(obtener_puerto_almacenamiento)
    ],
) -> ServicioCuentas:
    """Instancia del servicio de cuentas con sesion y puerto inyectados."""
    # Nota: la sesion se abre dentro de cada endpoint para garantizar transaccionalidad
    return ServicioCuentas(sesion=None, puerto_almacenamiento=puerto_almacenamiento)  # type: ignore[arg-type]


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
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
) -> AutorizacionRespuesta:
    """Registra el consentimiento expreso e informado de un reportante autenticado."""
    async with sesion_transaccional() as sesion:
        servicio = ServicioCuentas(sesion=sesion)
        return await servicio.registrar_autorizacion(usuario, entrada)


@router.get(
    "/mi-cuenta",
    summary="Consultar perfil del titular y autorizacion vigente",
)
async def obtener_perfil_usuario(
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
) -> PerfilUsuarioRespuesta:
    """Retorna el perfil del usuario autenticado; exige consentimiento activo."""
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
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
    puerto_almacenamiento: Annotated[
        PuertoAlmacenamientoFotos, Depends(obtener_puerto_almacenamiento)
    ],
) -> EliminarCuentaRespuesta:
    """Anonimiza todos los reportes, fotos y da de baja la cuenta (FR-007)."""
    async with sesion_transaccional() as sesion:
        servicio = ServicioCuentas(sesion=sesion, puerto_almacenamiento=puerto_almacenamiento)
        return await servicio.eliminar_mi_cuenta(usuario)
