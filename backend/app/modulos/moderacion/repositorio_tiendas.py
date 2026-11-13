"""Repositorio de base de datos para operaciones de tiendas/establecimientos en moderacion."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def crear_establecimiento_bd(
    sesion: AsyncSession,
    nombre: str,
    tipo: str,
    cadena: str | None,
    direccion: str,
    barrio: str | None,
    municipio: str,
    departamento: str,
    lat: float,
    lng: float,
    activo: bool,
) -> dict[str, Any]:
    """Inserta un establecimiento con ubicacion geography(Point, 4326)."""
    sql = text("""
        INSERT INTO establecimiento (
            nombre, tipo, cadena, direccion, barrio, municipio, departamento,
            ubicacion, activo
        ) VALUES (
            :nombre, CAST(:tipo AS tipo_establecimiento), :cadena, :direccion, :barrio,
            :municipio, :departamento,
            CAST(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) AS geography), :activo
        )
        RETURNING id, nombre, tipo::text, cadena, direccion, barrio, municipio,
                  departamento, ST_Y(ubicacion::geometry) as lat,
                  ST_X(ubicacion::geometry) as lng, activo;
    """)
    fila = (
        await sesion.execute(
            sql,
            {
                "nombre": nombre,
                "tipo": tipo,
                "cadena": cadena,
                "direccion": direccion,
                "barrio": barrio,
                "municipio": municipio,
                "departamento": departamento,
                "lat": lat,
                "lng": lng,
                "activo": activo,
            },
        )
    ).fetchone()
    return dict(fila._mapping)  # type: ignore[union-attr]


async def obtener_establecimiento_por_id(
    sesion: AsyncSession, est_id: UUID
) -> dict[str, Any] | None:
    """Obtiene establecimiento por id."""
    sql = text("""
        SELECT id, nombre, tipo::text, cadena, direccion, barrio, municipio, departamento,
               ST_Y(ubicacion::geometry) as lat, ST_X(ubicacion::geometry) as lng,
               estado_verificacion::text, activo
        FROM establecimiento WHERE id = :id;
    """)
    fila = (await sesion.execute(sql, {"id": est_id})).fetchone()
    return dict(fila._mapping) if fila else None


async def actualizar_establecimiento_bd(
    sesion: AsyncSession,
    est_id: UUID,
    campos: dict[str, Any],
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any] | None:
    """Actualiza datos y geometria espacial de establecimiento."""
    set_clauses: list[str] = []
    params: dict[str, Any] = {"id": est_id}

    for col, val in campos.items():
        if col == "tipo":
            set_clauses.append("tipo = CAST(:tipo AS tipo_establecimiento)")
        elif col == "estado_verificacion":
            set_clauses.append(
                "estado_verificacion = CAST(:estado_verificacion AS estado_verificacion_est)"
            )
        else:
            set_clauses.append(f"{col} = :{col}")
        params[col] = val

    if lat is not None and lng is not None:
        params["lat"] = lat
        params["lng"] = lng
        set_clauses.append(
            "ubicacion = CAST(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) AS geography)"
        )

    if not set_clauses:
        return await obtener_establecimiento_por_id(sesion, est_id)

    sql = text(f"""
        UPDATE establecimiento
        SET {", ".join(set_clauses)}
        WHERE id = :id
        RETURNING id, nombre, tipo::text, cadena, direccion, barrio, municipio, departamento,
                  ST_Y(ubicacion::geometry) as lat, ST_X(ubicacion::geometry) as lng,
                  estado_verificacion::text, activo;
    """)  # noqa: S608
    fila = (await sesion.execute(sql, params)).fetchone()
    return dict(fila._mapping) if fila else None
