"""Puerto para la administracion de credenciales de Supabase Auth."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class PuertoAuthAdmin(Protocol):
    """Operaciones administrativas sobre usuarios de autenticacion."""

    async def eliminar_usuario(self, usuario_id: UUID) -> bool:
        """Elimina la credencial del usuario; False si no fue posible."""
        ...
