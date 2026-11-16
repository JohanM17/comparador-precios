"""Cargador y cache en memoria de parametros de negocio desde config_parametro."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.parametros import ParametrosDominio

_CACHE_PARAMETROS: dict[str, Any] = {}
_ULTIMA_ACTUALIZACION: float = 0.0
_TTL_CACHE_PARAMETROS: float = 60.0  # 60 segundos de vigencia


async def obtener_parametros_dominio(
    sesion: AsyncSession,
    forzar_refresco: bool = False,
) -> ParametrosDominio:
    """Carga los 43 parametros de configuracion desde PostgreSQL con cache en memoria."""
    global _CACHE_PARAMETROS, _ULTIMA_ACTUALIZACION

    ahora = time.time()
    if (
        not forzar_refresco
        and _CACHE_PARAMETROS
        and (ahora - _ULTIMA_ACTUALIZACION) < _TTL_CACHE_PARAMETROS
    ):
        return ParametrosDominio.desde_dict(_CACHE_PARAMETROS)

    try:
        sql = text("SELECT clave, valor FROM public.config_parametro;")
        filas = (await sesion.execute(sql)).fetchall()
        diccionario: dict[str, Any] = {}
        for clave, valor in filas:
            diccionario[str(clave)] = valor

        if diccionario:
            _CACHE_PARAMETROS = diccionario
            _ULTIMA_ACTUALIZACION = ahora
            return ParametrosDominio.desde_dict(diccionario)
    except Exception:
        if _CACHE_PARAMETROS:
            return ParametrosDominio.desde_dict(_CACHE_PARAMETROS)

    # Si la tabla aun no tiene datos o falla la consulta, retorna valores por defecto
    return ParametrosDominio()


def invalidar_cache_parametros() -> None:
    """Invalida la cache en memoria forzando recarga en la proxima consulta."""
    global _ULTIMA_ACTUALIZACION
    _ULTIMA_ACTUALIZACION = 0.0
