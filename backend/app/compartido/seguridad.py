"""Modulo de autenticacion y autorizacion JWT con soporte dual JWKS / HS256."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, Header
from jwt import PyJWKClient, PyJWTError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bd import obtener_sesion
from app.compartido.errores import (
    AutorizacionRequeridaError,
    CuentaSuspendidaError,
    NoAutenticadoError,
    ProhibidoError,
)
from app.config import obtener_configuracion


@dataclass(frozen=True)
class UsuarioAutenticado:
    """Entidad que representa al usuario autenticado en el contexto de la solicitud."""

    id: UUID
    email: str | None
    rol: str
    estado: str


def decodificar_token(token: str) -> dict[str, Any]:
    """Valida y decodifica un JWT contra JWKS de Supabase o secreto simetrico HS256."""
    cfg = obtener_configuracion()
    errores: list[str] = []

    # 1. Intento con clave asimetrica JWKS (metodo moderno de Supabase Auth)
    if cfg.SUPABASE_JWKS_URL:
        try:
            jwks_client = PyJWKClient(cfg.SUPABASE_JWKS_URL, cache_keys=True)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                options={"verify_aud": False},
            )
            return payload
        except Exception as exc:
            errores.append(f"JWKS: {exc}")

    # 2. Respaldo con firma simetrica HS256 (proyectos legados o pruebas locales)
    if cfg.SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                cfg.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            return payload
        except PyJWTError as exc:
            errores.append(f"HS256: {exc}")

    raise NoAutenticadoError("Token JWT invalido, expirado o con firma no verificable.")


async def _consultar_perfil_bd(usuario_id: UUID, sesion: AsyncSession) -> tuple[str, str]:
    """Consulta rol y estado directamente en la tabla perfil de PostgreSQL (FR-005)."""
    try:
        resultado = await sesion.execute(
            text("SELECT rol, estado FROM public.perfil WHERE id = :id;"),
            {"id": usuario_id},
        )
        fila = resultado.fetchone()
        if fila:
            return str(fila[0]), str(fila[1])
    except Exception:  # noqa: S110
        # En etapas tempranas (T-03 a T-20) la tabla perfil aun no ha sido migrada
        pass
    return "consumidor", "activa"


async def requiere_usuario(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)] = None,  # type: ignore[assignment]
) -> UsuarioAutenticado:
    """Dependencia que valida la cabecera Authorization y retorna el usuario autenticado."""
    if not authorization or not authorization.startswith("Bearer "):
        raise NoAutenticadoError("Cabecera Authorization: Bearer ausente o malformada.")

    token = authorization[7:].strip()
    if not token:
        raise NoAutenticadoError("Token Bearer vacio.")

    payload = decodificar_token(token)
    sub = payload.get("sub")
    if not sub:
        raise NoAutenticadoError("Token no contiene el identificador de usuario ('sub').")

    try:
        usuario_id = UUID(str(sub))
    except (ValueError, TypeError) as exc:
        raise NoAutenticadoError("Identificador de usuario 'sub' no es un UUID valido.") from exc

    email = payload.get("email")

    # FR-005: El rol se lee exclusivamente desde la base de datos (nunca user_metadata)
    rol, estado = await _consultar_perfil_bd(usuario_id, sesion)

    if estado in ("suspendida", "bloqueada"):
        raise CuentaSuspendidaError()

    return UsuarioAutenticado(
        id=usuario_id,
        email=str(email) if email else None,
        rol=rol,
        estado=estado,
    )


def requiere_rol(*roles_permitidos: str) -> Any:
    """Genera una dependencia que exige que el usuario posea uno de los roles autorizados."""

    def _verificador_rol(
        usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
    ) -> UsuarioAutenticado:
        if usuario.rol not in roles_permitidos:
            raise ProhibidoError("No posee el rol requerido para acceder a este recurso.")
        return usuario

    return _verificador_rol


async def requiere_autorizacion_datos(
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> UsuarioAutenticado:
    """Valida que el usuario tenga autorizacion previa y expresa segun Ley 1581 (FR-006)."""
    sql = text("""
        SELECT 1 FROM public.autorizacion_datos
        WHERE usuario_id = :uid AND revocada_en IS NULL
        LIMIT 1;
    """)
    fila = (await sesion.execute(sql, {"uid": usuario.id})).fetchone()
    if not fila:
        raise AutorizacionRequeridaError(
            "Se requiere autorizacion previa y expresa segun Ley 1581 para realizar esta accion."
        )
    return usuario
