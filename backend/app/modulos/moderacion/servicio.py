"""Servicio unificado de moderacion de catalogo, tiendas y sugerencias."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modulos.moderacion.servicio_catalogo import ServicioCatalogoModeracion
from app.modulos.moderacion.servicio_sugerencias import ServicioSugerenciasModeracion
from app.puertos.catalogo_externo import PuertoCatalogoExterno


class ServicioModeracion(ServicioCatalogoModeracion, ServicioSugerenciasModeracion):
    """Fachada unificada para coordinar la moderacion integral de catalogo y sugerencias."""

    def __init__(
        self,
        sesion: AsyncSession,
        puerto_catalogo: PuertoCatalogoExterno | None = None,
    ) -> None:
        ServicioCatalogoModeracion.__init__(self, sesion=sesion, puerto_catalogo=puerto_catalogo)
        ServicioSugerenciasModeracion.__init__(self, sesion=sesion)


__all__ = ["ServicioCatalogoModeracion", "ServicioModeracion", "ServicioSugerenciasModeracion"]
