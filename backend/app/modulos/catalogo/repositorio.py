"""Repositorio de acceso a datos para categorias y productos."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def listar_categorias(sesion: AsyncSession) -> list[dict[str, Any]]:
    """Obtiene el listado de categorias ordenadas por su campo orden."""
    consulta = text("""
        SELECT id, nombre, padre_id, orden
        FROM categoria
        ORDER BY orden ASC, id ASC;
    """)
    resultado = await sesion.execute(consulta)
    return [dict(fila._mapping) for fila in resultado.fetchall()]


async def buscar_productos(
    sesion: AsyncSession,
    termino: str | None,
    categoria_id: int | None,
    cantidad_filtro: Decimal | None,
    limite: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Busca productos en el catalogo tolerando errores tipograficos y tildes."""
    filtros: list[str] = ["p.activo = true"]
    params: dict[str, Any] = {"limite": limite, "offset": offset}

    if categoria_id is not None:
        filtros.append("p.categoria_id = :categoria_id")
        params["categoria_id"] = categoria_id

    orden_sql = "p.nombre ASC"

    if termino:
        params["termino"] = termino
        params["patron"] = f"%{termino}%"
        subcondiciones = [
            "p.nombre_norm ILIKE :patron",
            "similarity(p.nombre_norm, :termino) > 0.15",
            """p.id IN (
                SELECT a.producto_id FROM alias_producto a
                WHERE a.alias_norm ILIKE :patron
                   OR similarity(a.alias_norm, :termino) > 0.20
            )""",
            """p.id IN (
                SELECT pr.producto_id FROM presentacion pr
                WHERE pr.etiqueta_norm ILIKE :patron
                   OR similarity(pr.etiqueta_norm, :termino) > 0.20
            )""",
        ]
        filtros.append(f"({' OR '.join(subcondiciones)})")
        orden_sql = "similarity(p.nombre_norm, :termino) DESC, p.nombre ASC"

    if cantidad_filtro is not None:
        params["cantidad_filtro"] = float(cantidad_filtro)
        filtros.append("""p.id IN (
            SELECT pr2.producto_id FROM presentacion pr2
            WHERE pr2.activa = true AND pr2.cantidad_base = :cantidad_filtro
        )""")

    clausula_where = " AND ".join(filtros)

    sql_productos = text(f"""
        SELECT p.id, p.nombre, p.categoria_id, p.unidad_base, p.imagen_url, p.activo,
               count(*) OVER() AS total_registros
        FROM producto p
        WHERE {clausula_where}
        ORDER BY {orden_sql}
        LIMIT :limite OFFSET :offset;
    """)  # noqa: S608
    filas_prod = (await sesion.execute(sql_productos, params)).fetchall()
    if not filas_prod:
        return [], 0

    conteo_total = int(filas_prod[0].total_registros)
    productos = [
        {
            "id": f.id,
            "nombre": f.nombre,
            "categoria_id": f.categoria_id,
            "unidad_base": f.unidad_base,
            "imagen_url": f.imagen_url,
            "activo": f.activo,
        }
        for f in filas_prod
    ]

    producto_ids = [p["id"] for p in productos]
    sql_presentaciones = text("""
        SELECT id, producto_id, marca, valor_cantidad, unidad,
               multiplicador, cantidad_base, etiqueta, codigo_barras, activa
        FROM presentacion
        WHERE producto_id = ANY(:ids) AND activa = true
        ORDER BY cantidad_base ASC;
    """)
    filas_pres = (await sesion.execute(sql_presentaciones, {"ids": producto_ids})).fetchall()
    pres_por_prod: dict[UUID, list[dict[str, Any]]] = {pid: [] for pid in producto_ids}
    for f in filas_pres:
        pres_por_prod[f.producto_id].append(dict(f._mapping))

    sql_precios = text("""
        SELECT producto_id,
               min(precio_por_base) as min_precio_base,
               count(DISTINCT establecimiento_id) as n_tiendas
        FROM precio_vigente
        WHERE producto_id = ANY(:ids)
        GROUP BY producto_id;
    """)
    filas_prec = (await sesion.execute(sql_precios, {"ids": producto_ids})).fetchall()
    precios_por_prod = {f.producto_id: (f.min_precio_base, f.n_tiendas) for f in filas_prec}

    for prod in productos:
        pid = prod["id"]
        prod["presentaciones"] = pres_por_prod.get(pid, [])
        info_precio = precios_por_prod.get(pid)
        if info_precio:
            prod["min_precio_base"] = info_precio[0]
            prod["n_tiendas_con_precio"] = info_precio[1]
        else:
            prod["min_precio_base"] = None
            prod["n_tiendas_con_precio"] = 0

    return productos, conteo_total


async def obtener_producto_por_id(sesion: AsyncSession, producto_id: UUID) -> dict[str, Any] | None:
    """Obtiene la informacion detallada de un producto con sus presentaciones."""
    sql_prod = text("""
        SELECT id, nombre, categoria_id, unidad_base, imagen_url, activo
        FROM producto
        WHERE id = :id AND activo = true;
    """)
    fila_prod = (await sesion.execute(sql_prod, {"id": producto_id})).fetchone()
    if not fila_prod:
        return None

    prod = dict(fila_prod._mapping)
    sql_pres = text("""
        SELECT id, producto_id, marca, valor_cantidad, unidad,
               multiplicador, cantidad_base, etiqueta, codigo_barras, activa
        FROM presentacion
        WHERE producto_id = :id AND activa = true
        ORDER BY cantidad_base ASC;
    """)
    filas_pres = (await sesion.execute(sql_pres, {"id": producto_id})).fetchall()
    prod["presentaciones"] = [dict(f._mapping) for f in filas_pres]
    return prod
