"""Repositorio de acceso a datos espaciales y moderacion de tiendas."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def listar_establecimientos(
    sesion: AsyncSession,
    termino: str | None,
    tipo: str | None,
    municipio: str | None,
    lat: float | None,
    lng: float | None,
    radio_km: float,
    limite: int,
) -> tuple[list[dict[str, Any]], int]:
    """Consulta establecimientos con filtros de texto y calculo de proximidad PostGIS."""
    filtros: list[str] = ["activo = true"]
    params: dict[str, Any] = {"limite": limite}

    if municipio:
        filtros.append("municipio ILIKE :municipio")
        params["municipio"] = municipio

    if tipo:
        filtros.append("tipo::text = :tipo")
        params["tipo"] = tipo

    if termino:
        params["patron"] = f"%{termino}%"
        filtros.append("(nombre ILIKE :patron OR direccion ILIKE :patron)")

    distancia_columna = "NULL as distancia_m"
    orden_sql = "nombre ASC"

    if lat is not None and lng is not None:
        params["lat"] = lat
        params["lng"] = lng
        params["radio_m"] = radio_km * 1000.0

        punto_geom = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"
        filtros.append(f"ST_DWithin(ubicacion, {punto_geom}, :radio_m)")
        distancia_columna = f"round(ST_Distance(ubicacion, {punto_geom}))::int as distancia_m"
        orden_sql = "distancia_m ASC, nombre ASC"

    clausula_where = " AND ".join(filtros)

    sql_conteo = text(
        f"SELECT count(*) FROM establecimiento WHERE {clausula_where};"  # noqa: S608
    )
    conteo_total = (await sesion.scalar(sql_conteo, params)) or 0

    sql_establecimientos = text(f"""
        SELECT id, nombre, tipo::text, cadena, direccion, barrio,
               municipio, departamento,
               ST_Y(ubicacion::geometry) as lat,
               ST_X(ubicacion::geometry) as lng,
               {distancia_columna},
               estado_verificacion::text, activo
        FROM establecimiento
        WHERE {clausula_where}
        ORDER BY {orden_sql}
        LIMIT :limite;
    """)  # noqa: S608

    filas = (await sesion.execute(sql_establecimientos, params)).fetchall()
    return [dict(f._mapping) for f in filas], conteo_total


async def obtener_establecimiento_por_id(
    sesion: AsyncSession,
    establecimiento_id: UUID,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any] | None:
    """Consulta el detalle de un establecimiento y sus precios vigentes."""
    params: dict[str, Any] = {"id": establecimiento_id}
    distancia_columna = "NULL as distancia_m"

    if lat is not None and lng is not None:
        params["lat"] = lat
        params["lng"] = lng
        punto_geom = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"
        distancia_columna = f"round(ST_Distance(ubicacion, {punto_geom}))::int as distancia_m"

    sql_est = text(f"""
        SELECT id, nombre, tipo::text, cadena, direccion, barrio,
               municipio, departamento,
               ST_Y(ubicacion::geometry) as lat,
               ST_X(ubicacion::geometry) as lng,
               {distancia_columna},
               estado_verificacion::text, activo
        FROM establecimiento
        WHERE id = :id AND activo = true;
    """)  # noqa: S608
    fila_est = (await sesion.execute(sql_est, params)).fetchone()
    if not fila_est:
        return None

    est = dict(fila_est._mapping)

    sql_precios = text("""
        SELECT pv.presentacion_id, pv.producto_id,
               p.nombre as producto_nombre,
               pr.etiqueta as presentacion_etiqueta,
               pv.precio_cop, pv.precio_por_base,
               pv.sello::text, pv.motivo_sello,
               pv.ultimo_reporte_en
        FROM precio_vigente pv
        JOIN producto p ON p.id = pv.producto_id
        JOIN presentacion pr ON pr.id = pv.presentacion_id
        WHERE pv.establecimiento_id = :id
        ORDER BY pv.ultimo_reporte_en DESC
        LIMIT 50;
    """)
    filas_prec = (await sesion.execute(sql_precios, {"id": establecimiento_id})).fetchall()
    est["precios_vigentes"] = [dict(f._mapping) for f in filas_prec]
    return est


async def registrar_solicitud_correccion(
    sesion: AsyncSession,
    establecimiento_id: UUID,
    correo: str,
    mensaje: str,
) -> UUID:
    """Inserta un caso de moderacion por reporte ciudadano de datos de tienda."""
    detalle_json = json.dumps({"correo": correo, "mensaje": mensaje})
    sql = text("""
        INSERT INTO caso_moderacion (
            tipo, referencia_tabla, referencia_id, detalle, prioridad, estado
        ) VALUES (
            'solicitud_correccion', 'establecimiento', :ref_id,
            CAST(:detalle AS jsonb), 3, 'abierto'
        )
        RETURNING id;
    """)
    nuevo_id = await sesion.scalar(sql, {"ref_id": establecimiento_id, "detalle": detalle_json})
    return UUID(str(nuevo_id))
