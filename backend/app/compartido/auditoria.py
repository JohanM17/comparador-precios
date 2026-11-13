"""Servicio compartido de auditoria inmutable para trazabilidad de acciones del sistema."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def registrar_auditoria(
    sesion: AsyncSession,
    actor_id: UUID | None,
    rol: str | None,
    accion: str,
    entidad: str,
    entidad_id: str | None,
    antes: dict[str, Any] | None,
    despues: dict[str, Any] | None,
) -> None:
    """Inserta un registro inmutable en la tabla de auditoria del sistema."""
    antes_json = json.dumps(antes, default=str) if antes is not None else None
    despues_json = json.dumps(despues, default=str) if despues is not None else None

    sql = text("""
        INSERT INTO auditoria (
            actor_id, rol, accion, entidad, entidad_id, antes, despues
        ) VALUES (
            :actor_id, :rol, :accion, :entidad, :entidad_id,
            CAST(:antes AS jsonb), CAST(:despues AS jsonb)
        );
    """)
    await sesion.execute(
        sql,
        {
            "actor_id": actor_id,
            "rol": rol,
            "accion": accion,
            "entidad": entidad,
            "entidad_id": entidad_id,
            "antes": antes_json,
            "despues": despues_json,
        },
    )
