"""Bloqueos transaccionales compartidos entre modulos."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_SQL_BLOQUEO_USUARIO = text("""
    SELECT pg_advisory_xact_lock(hashtext(:usuario_id_texto));
""")


async def bloquear_por_usuario(sesion: AsyncSession, usuario_id: UUID) -> None:
    """Serializa operaciones que compiten por los datos de un mismo titular.

    Es un advisory lock transaccional: se libera solo al terminar la transaccion
    (commit o rollback), no al cerrar una sentencia. La baja de cuenta y el
    reclamo de titularidad usan la misma clave para que el reclamo no pueda
    insertar PII despues de que la baja haya borrado sus reclamos.
    """
    await sesion.execute(_SQL_BLOQUEO_USUARIO, {"usuario_id_texto": str(usuario_id)})
