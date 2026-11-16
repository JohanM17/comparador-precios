"""Ayudantes y actores parametrizados para pruebas de matriz RBAC (Seccion 6.5)."""

from __future__ import annotations

from uuid import uuid4

import jwt
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.config import obtener_configuracion

ROLES_RBAC = [
    "anonimo",
    "sin_autorizar",
    "reportante_activa",
    "moderador_activa",
    "suspendida",
    "bloqueada",
]

_MAPA_ROLES = {
    "sin_autorizar": ("sin_autorizar", "activa", False),
    "reportante_activa": ("reportante", "activa", True),
    "moderador_activa": ("moderador", "activa", True),
    "suspendida": ("reportante", "suspendida", True),
    "bloqueada": ("reportante", "bloqueada", True),
}


def generar_token_rbac(usuario_id: str) -> str:
    """Genera un token JWT de prueba firmado localmente."""
    cfg = obtener_configuracion()
    secreto = cfg.SUPABASE_JWT_SECRET or "secreto_jwt_prueba_local_32_bytes_min"
    cfg.SUPABASE_JWT_SECRET = secreto
    return jwt.encode({"sub": usuario_id, "email": f"{usuario_id[:8]}@test.co"}, secreto, "HS256")


async def crear_actor_bd(rol: str, estado: str, con_autorizacion: bool) -> dict[str, str]:
    """Inserta perfil y autorizacion Ley 1581 opcional para un actor RBAC."""
    uid = str(uuid4())
    if rol != "sin_autorizar":
        async with sesion_transaccional() as sesion:
            await sesion.execute(
                text("""
                    INSERT INTO public.perfil (id, alias, rol, estado, reputacion)
                    VALUES (
                        :id, :alias, CAST(:rol AS rol_usuario),
                        CAST(:estado AS estado_cuenta), 0.7
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        rol = CAST(:rol AS rol_usuario),
                        estado = CAST(:estado AS estado_cuenta);
                """),
                {"id": uid, "alias": f"rbac_{uid[:8]}", "rol": rol, "estado": estado},
            )
            if con_autorizacion:
                await sesion.execute(
                    text("""
                        INSERT INTO public.autorizacion_datos
                            (usuario_id, version_politica, finalidad)
                        VALUES (
                            :uid, '1.0',
                            'Autorizacion de prueba parametrizada RBAC Ley 1581'
                        );
                    """),
                    {"uid": uid},
                )
    return {"uid": uid, "token": generar_token_rbac(uid)}


async def obtener_ids_semilla() -> tuple[str, str, str]:
    """Obtiene IDs activos de producto, presentacion y establecimiento semilla."""
    async with sesion_transaccional() as sesion:
        fila = (
            await sesion.execute(
                text("SELECT id, producto_id FROM public.presentacion WHERE activa = true LIMIT 1;")
            )
        ).first()
        est = (
            await sesion.execute(
                text("SELECT id FROM public.establecimiento WHERE activo = true LIMIT 1;")
            )
        ).scalar_one()
        assert fila is not None
        return str(fila[1]), str(fila[0]), str(est)


async def headers_para_rol(clave_rol: str) -> dict[str, str]:
    """Retorna cabeceras Authorization listas segun la clave de rol RBAC."""
    if clave_rol == "anonimo":
        return {}
    rol, estado, con_auth = _MAPA_ROLES[clave_rol]
    actor = await crear_actor_bd(rol, estado, con_auth)
    return {"Authorization": f"Bearer {actor['token']}"}
