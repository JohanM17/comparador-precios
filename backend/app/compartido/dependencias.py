"""Proveedores de dependencias compartidos entre modulos.

El puerto de cache lo necesitan tanto `precios` como `comercial`. Vivia dentro de
`precios.api`, lo que obligaba al modulo comercial a importar al de precios solo para
inyectar una dependencia. Aqui no pertenece a ningun modulo, y la sustitucion que hace
`main.py` sigue funcionando porque FastAPI resuelve los reemplazos por identidad de la
funcion, no por su ubicacion.
"""

from __future__ import annotations

from app.puertos.cache import PuertoCache


def obtener_puerto_cache() -> PuertoCache:
    """Proveedor inyectable del puerto de cache (se sustituye en la raiz de composicion)."""
    raise NotImplementedError("El puerto de cache debe ser inyectado por FastAPI.")
