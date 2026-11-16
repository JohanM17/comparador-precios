"""Acceso a datos para consultas de registros de auditoria."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def listar_auditoria_bd(
    sesion: AsyncSession,
    entidad: str | None = None,
    accion: str | None = None,
    actor_id: UUID | None = None,
    limite: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    conds = ["1=1"]
    params: dict[str, Any] = {"limite": limite, "offset": offset}
    if entidad:
        conds.append("entidad = :entidad")
        params["entidad"] = entidad
    if accion:
        conds.append("accion = :accion")
        params["accion"] = accion
    if actor_id:
        conds.append("actor_id = :actor_id")
        params["actor_id"] = actor_id

    where_sql = " AND ".join(conds)
    total = (
        await sesion.execute(
            text(f"SELECT count(*) FROM public.auditoria WHERE {where_sql};"),  # noqa: S608
            params,
        )
    ).scalar() or 0

    sql_items = text(f"""
        SELECT id, actor_id, rol, accion, entidad, entidad_id, antes, despues, creado_en
        FROM public.auditoria
        WHERE {where_sql}
        ORDER BY id DESC
        LIMIT :limite OFFSET :offset;
    """)  # noqa: S608
    filas = (await sesion.execute(sql_items, params)).fetchall()
    return [dict(f._mapping) for f in filas], int(total)
