"""Repositorio de base de datos para operaciones de productos y presentaciones."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def crear_producto_bd(
    sesion: AsyncSession,
    nombre: str,
    nombre_norm: str,
    categoria_id: int,
    unidad_base: str,
    imagen_url: str | None,
) -> dict[str, Any]:
    """Inserta un producto en la tabla producto."""
    sql = text("""
        INSERT INTO producto (
            nombre, nombre_norm, categoria_id, unidad_base, imagen_url, activo
        ) VALUES (
            :nombre, :nombre_norm, :categoria_id,
            CAST(:unidad_base AS unidad_base), :imagen_url, true
        )
        RETURNING id, nombre, categoria_id, unidad_base::text, imagen_url, activo;
    """)
    fila = (
        await sesion.execute(
            sql,
            {
                "nombre": nombre,
                "nombre_norm": nombre_norm,
                "categoria_id": categoria_id,
                "unidad_base": unidad_base,
                "imagen_url": imagen_url,
            },
        )
    ).fetchone()
    return dict(fila._mapping)  # type: ignore[union-attr]


async def obtener_producto_por_id(sesion: AsyncSession, producto_id: UUID) -> dict[str, Any] | None:
    """Obtiene un producto por su clave primaria."""
    sql = text("""
        SELECT id, nombre, categoria_id, unidad_base::text, imagen_url, activo
        FROM producto WHERE id = :id;
    """)
    fila = (await sesion.execute(sql, {"id": producto_id})).fetchone()
    return dict(fila._mapping) if fila else None


async def actualizar_producto_bd(
    sesion: AsyncSession,
    producto_id: UUID,
    campos: dict[str, Any],
) -> dict[str, Any] | None:
    """Actualiza dinamicamente columnas permitidas de producto."""
    set_clauses: list[str] = []
    params: dict[str, Any] = {"id": producto_id}

    for col, val in campos.items():
        if col == "unidad_base":
            set_clauses.append("unidad_base = CAST(:unidad_base AS unidad_base)")
        else:
            set_clauses.append(f"{col} = :{col}")
        params[col] = val

    if not set_clauses:
        return await obtener_producto_por_id(sesion, producto_id)

    sql = text(f"""
        UPDATE producto
        SET {", ".join(set_clauses)}
        WHERE id = :id
        RETURNING id, nombre, categoria_id, unidad_base::text, imagen_url, activo;
    """)  # noqa: S608
    fila = (await sesion.execute(sql, params)).fetchone()
    return dict(fila._mapping) if fila else None


async def crear_presentacion_bd(
    sesion: AsyncSession,
    producto_id: UUID,
    marca: str | None,
    valor_cantidad: Decimal,
    unidad: str,
    multiplicador: int,
    cantidad_base: Decimal,
    etiqueta: str,
    etiqueta_norm: str,
    codigo_barras: str | None,
    fuente_catalogo: str,
) -> dict[str, Any]:
    """Inserta una presentacion calculando su dimension base."""
    sql = text("""
        INSERT INTO presentacion (
            producto_id, marca, valor_cantidad, unidad, multiplicador,
            cantidad_base, etiqueta, etiqueta_norm, codigo_barras, fuente_catalogo, activa
        ) VALUES (
            :producto_id, :marca, :valor_cantidad, CAST(:unidad AS unidad_entrada), :multiplicador,
            :cantidad_base, :etiqueta, :etiqueta_norm, :codigo_barras, :fuente_catalogo, true
        )
        RETURNING id, producto_id, marca, valor_cantidad, unidad::text, multiplicador,
                  cantidad_base, etiqueta, codigo_barras, activa;
    """)
    fila = (
        await sesion.execute(
            sql,
            {
                "producto_id": producto_id,
                "marca": marca,
                "valor_cantidad": valor_cantidad,
                "unidad": unidad,
                "multiplicador": multiplicador,
                "cantidad_base": cantidad_base,
                "etiqueta": etiqueta,
                "etiqueta_norm": etiqueta_norm,
                "codigo_barras": codigo_barras,
                "fuente_catalogo": fuente_catalogo,
            },
        )
    ).fetchone()
    return dict(fila._mapping)  # type: ignore[union-attr]


async def obtener_presentacion_por_id(
    sesion: AsyncSession, presentacion_id: UUID
) -> dict[str, Any] | None:
    """Obtiene una presentacion por su UUID."""
    sql = text("""
        SELECT id, producto_id, marca, valor_cantidad, unidad::text,
               multiplicador, cantidad_base, etiqueta, codigo_barras, activa
        FROM presentacion WHERE id = :id;
    """)
    fila = (await sesion.execute(sql, {"id": presentacion_id})).fetchone()
    return dict(fila._mapping) if fila else None


async def actualizar_presentacion_bd(
    sesion: AsyncSession,
    presentacion_id: UUID,
    campos: dict[str, Any],
) -> dict[str, Any] | None:
    """Actualiza atributos mutables de presentacion."""
    set_clauses: list[str] = []
    params: dict[str, Any] = {"id": presentacion_id}

    for col, val in campos.items():
        if col == "unidad":
            set_clauses.append("unidad = CAST(:unidad AS unidad_entrada)")
        else:
            set_clauses.append(f"{col} = :{col}")
        params[col] = val

    if not set_clauses:
        return await obtener_presentacion_por_id(sesion, presentacion_id)

    sql = text(f"""
        UPDATE presentacion
        SET {", ".join(set_clauses)}
        WHERE id = :id
        RETURNING id, producto_id, marca, valor_cantidad, unidad::text,
                  multiplicador, cantidad_base, etiqueta, codigo_barras, activa;
    """)  # noqa: S608
    fila = (await sesion.execute(sql, params)).fetchone()
    return dict(fila._mapping) if fila else None
