"""Adaptador best-effort para eliminar credenciales de Supabase Auth."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx

from app.config import Configuracion, obtener_configuracion
from app.puertos.auth_admin import PuertoAuthAdmin

_logger = logging.getLogger("app")

_CODIGOS_EXITO = {200, 204, 404}


class AdaptadorAuthSupabase(PuertoAuthAdmin):
    """Llama al endpoint admin de Supabase con la service role key."""

    def __init__(
        self,
        cfg: Configuracion | None = None,
        cliente_http: httpx.AsyncClient | None = None,
    ) -> None:
        self.cfg = cfg or obtener_configuracion()
        self.cliente_http = cliente_http

    async def eliminar_usuario(self, usuario_id: UUID) -> bool:
        """Elimina el usuario de Auth; nunca lanza y no registra el identificador."""
        if not self.cfg.SUPABASE_URL or not self.cfg.SUPABASE_SERVICE_ROLE_KEY:
            _logger.warning(
                "No se pudo eliminar la credencial de autenticacion: configuracion incompleta."
            )
            return False

        url = f"{self.cfg.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{usuario_id}"
        headers = {
            "Authorization": f"Bearer {self.cfg.SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": self.cfg.SUPABASE_SERVICE_ROLE_KEY,
        }
        cliente_propio = self.cliente_http is None
        cliente = self.cliente_http or httpx.AsyncClient(timeout=10.0)
        try:
            respuesta = await cliente.delete(url, headers=headers)
        except Exception:
            _logger.warning(
                "No se pudo eliminar la credencial de autenticacion por un error de red."
            )
            return False
        finally:
            if cliente_propio:
                await cliente.aclose()

        if respuesta.status_code in _CODIGOS_EXITO:
            return True
        _logger.warning(
            "No se pudo eliminar la credencial de autenticacion: respuesta HTTP %s.",
            respuesta.status_code,
        )
        return False
