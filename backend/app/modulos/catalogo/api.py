"""Endpoints publicos para catalogo de productos y categorias."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.bd import obtener_sesion
from app.modulos.catalogo.esquemas import (
    CategoriaRespuesta,
    ListaProductosRespuesta,
    ProductoDetalleRespuesta,
)
from app.modulos.catalogo.servicio import ServicioCatalogo

router = APIRouter(tags=["catalogo"])


def obtener_servicio_catalogo(
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> ServicioCatalogo:
    """Proveedor de dependencia para el servicio de catalogo."""
    return ServicioCatalogo(sesion)


@router.get(
    "/categorias",
    summary="Listar categorias de productos",
)
async def listar_todas_las_categorias(
    servicio: Annotated[ServicioCatalogo, Depends(obtener_servicio_catalogo)],
) -> list[CategoriaRespuesta]:
    """Retorna las 10 categorias oficiales de la canasta familiar ordenadas."""
    return await servicio.obtener_categorias()


@router.get(
    "/productos",
    summary="Buscador difuso de productos",
)
async def buscar_productos_catalogo(
    servicio: Annotated[ServicioCatalogo, Depends(obtener_servicio_catalogo)],
    q: Annotated[str | None, Query(description="Texto o cantidad (ej. arroz 1/2 kilo)")] = None,
    categoria_id: Annotated[int | None, Query(description="Filtrar por categoria")] = None,
    limite: Annotated[int, Query(ge=1, le=100, description="Cantidad maxima de resultados")] = 24,
    cursor: Annotated[str | None, Query(description="Paginador por cursor")] = None,
) -> ListaProductosRespuesta:
    """Busca productos tolerando tildes, mayusculas y fracciones de cantidad."""
    return await servicio.buscar(
        q=q,
        categoria_id=categoria_id,
        limite=limite,
        cursor=cursor,
    )


@router.get(
    "/productos/{id}",
    summary="Ficha tecnica del producto",
)
async def obtener_detalle_producto(
    id: UUID,
    servicio: Annotated[ServicioCatalogo, Depends(obtener_servicio_catalogo)],
) -> ProductoDetalleRespuesta:
    """Devuelve la ficha del producto y sus presentaciones activas."""
    return await servicio.obtener_por_id(id)
