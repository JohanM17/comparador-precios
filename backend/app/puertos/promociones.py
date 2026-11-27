"""Puerto de lectura de promociones comerciales para la comparacion (EC-06, ADR-018).

La comparacion necesita mostrar las promociones vigentes de un producto, pero el modulo
`precios` tiene prohibido importar al modulo `comercial`: esa frontera es la que garantiza
que una relacion comercial no pueda alterar el orden de los resultados, y la verifica
`import-linter` en cada ejecucion del pipeline.

La salida se entrega como diccionarios y no como un modelo tipado a proposito. El contrato
del nucleo reservo `promociones` como un arreglo de objetos sin esquema, y cambiarlo ahora
seria modificar un endpoint ya publicado. La forma de cada elemento es la que el frontend
ya esperaba desde la Etapa 1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LIMITE_PROMOCIONES = 20

_SQL_PROMOCIONES_VIGENTES = text("""
    SELECT p.id, p.titulo, p.tipo::text AS tipo,
           p.porcentaje_descuento, p.precio_especial_cop, p.pague_x, p.lleve_y,
           p.condiciones, p.vigente_desde, p.vigente_hasta, p.hasta_revocar,
           e.nombre AS establecimiento_nombre,
           pr.etiqueta AS presentacion_etiqueta
    FROM public.promocion p
    JOIN public.establecimiento e ON e.id = p.establecimiento_id
    LEFT JOIN public.presentacion pr ON pr.id = p.presentacion_id
    WHERE p.producto_id = :pid
      AND p.activa = true
      AND e.activo = true
      AND p.vigente_desde <= :ahora
      AND (p.vigente_hasta IS NULL OR p.vigente_hasta >= :ahora)
    ORDER BY p.vigente_desde DESC
    LIMIT :limite;
""")


class PuertoPromociones(Protocol):
    """Protocolo de lectura de promociones vigentes de un producto."""

    async def listar_vigentes(
        self,
        sesion: AsyncSession,
        producto_id: UUID,
        ahora: datetime,
    ) -> list[dict[str, Any]]:
        """Promociones vigentes del producto, siempre marcadas como contenido comercial."""
        ...


class SinPromociones:
    """Politica de la Etapa 1: la plataforma no publica promociones todavia."""

    async def listar_vigentes(
        self,
        sesion: AsyncSession,
        producto_id: UUID,
        ahora: datetime,
    ) -> list[dict[str, Any]]:
        """Devuelve siempre un arreglo vacio."""
        return []


class PromocionesPublicadas:
    """Politica de la Etapa 2: lee las promociones que publicaron los comercios."""

    async def listar_vigentes(
        self,
        sesion: AsyncSession,
        producto_id: UUID,
        ahora: datetime,
    ) -> list[dict[str, Any]]:
        """Promociones activas y dentro de su ventana de vigencia declarada."""
        filas = (
            await sesion.execute(
                _SQL_PROMOCIONES_VIGENTES,
                {"pid": producto_id, "ahora": ahora, "limite": LIMITE_PROMOCIONES},
            )
        ).fetchall()
        # FR-025: todo elemento sale marcado como promocion, para que ninguna capa de
        # arriba pueda confundirlo con un resultado de la comparacion.
        return [{**dict(f._mapping), "es_promocion": True} for f in filas]
