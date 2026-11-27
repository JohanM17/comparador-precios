"""Acceso a datos para sanciones de usuarios y apelaciones."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def insertar_sancion_bd(
    sesion: AsyncSession,
    usuario_id: UUID,
    tipo: str,
    motivo: str,
    moderador_id: UUID,
    desde: datetime,
    hasta: datetime | None,
) -> UUID:
    sql = text("""
        INSERT INTO public.sancion (
            usuario_id, tipo, motivo, desde, hasta, moderador_id
        ) VALUES (
            :uid, CAST(:tipo AS tipo_sancion), :motivo, :desde, :hasta, :mod_id
        ) RETURNING id;
    """)
    res = (
        await sesion.execute(
            sql,
            {
                "uid": usuario_id,
                "tipo": tipo,
                "motivo": motivo,
                "desde": desde,
                "hasta": hasta,
                "mod_id": moderador_id,
            },
        )
    ).scalar_one()
    return UUID(str(res))


async def actualizar_estado_perfil_bd(
    sesion: AsyncSession, usuario_id: UUID, estado: str, suspendida_hasta: datetime | None
) -> bool:
    """Cambia el estado solo si la cuenta no fue eliminada; False si no aplica."""
    sql = text("""
        UPDATE public.perfil
        SET estado = CAST(:estado AS estado_cuenta),
            suspendida_hasta = :hasta,
            actualizado_en = now()
        WHERE id = :id AND estado <> 'eliminada'
        RETURNING id;
    """)
    fila = (
        await sesion.execute(sql, {"id": usuario_id, "estado": estado, "hasta": suspendida_hasta})
    ).first()
    return fila is not None


async def registrar_apelacion_bd(
    sesion: AsyncSession, sancion_id: UUID, texto_apelacion: str
) -> None:
    sql = text("""
        UPDATE public.sancion
        SET apelacion = :apelacion
        WHERE id = :id;
    """)
    await sesion.execute(sql, {"id": sancion_id, "apelacion": texto_apelacion})


async def resolver_apelacion_bd(
    sesion: AsyncSession, sancion_id: UUID, aprobada: bool
) -> dict[str, Any] | None:
    sql = text("""
        UPDATE public.sancion
        SET apelacion_resuelta = :aprobada
        WHERE id = :id
        RETURNING id, usuario_id, tipo::text, motivo, desde, hasta, apelacion, apelacion_resuelta;
    """)
    fila = (await sesion.execute(sql, {"id": sancion_id, "aprobada": aprobada})).first()
    return dict(fila._mapping) if fila else None


async def obtener_sancion_por_id_bd(
    sesion: AsyncSession, sancion_id: UUID
) -> dict[str, Any] | None:
    sql = text("""
        SELECT id, usuario_id, tipo::text, motivo, desde, hasta,
               moderador_id, apelacion, apelacion_resuelta
        FROM public.sancion WHERE id = :id;
    """)
    fila = (await sesion.execute(sql, {"id": sancion_id})).first()
    return dict(fila._mapping) if fila else None
