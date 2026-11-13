"""Fachada de repositorios para el modulo de moderacion."""

from __future__ import annotations

from app.modulos.moderacion.repositorio_catalogo import (
    actualizar_presentacion_bd,
    actualizar_producto_bd,
    crear_presentacion_bd,
    crear_producto_bd,
    obtener_presentacion_por_id,
    obtener_producto_por_id,
)
from app.modulos.moderacion.repositorio_sugerencias import (
    crear_sugerencia_presentacion_bd,
    obtener_sugerencia_por_id,
    resolver_sugerencia_bd,
    verificar_autorizacion_vigente,
)
from app.modulos.moderacion.repositorio_tiendas import (
    actualizar_establecimiento_bd,
    crear_establecimiento_bd,
    obtener_establecimiento_por_id,
)

__all__ = [
    "actualizar_establecimiento_bd",
    "actualizar_presentacion_bd",
    "actualizar_producto_bd",
    "crear_establecimiento_bd",
    "crear_presentacion_bd",
    "crear_producto_bd",
    "crear_sugerencia_presentacion_bd",
    "obtener_establecimiento_por_id",
    "obtener_presentacion_por_id",
    "obtener_producto_por_id",
    "obtener_sugerencia_por_id",
    "resolver_sugerencia_bd",
    "verificar_autorizacion_vigente",
]
