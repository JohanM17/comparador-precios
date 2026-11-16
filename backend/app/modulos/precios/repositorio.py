"""Consultas de base de datos para reportes, vigencia y comparaciones de precios."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def obtener_presentacion_con_producto(
    sesion: AsyncSession,
    presentacion_id: UUID,
) -> dict[str, Any] | None:
    sql = text("""
        SELECT pr.id, pr.producto_id, pr.cantidad_base, pr.unidad, pr.etiqueta, pr.activa,
               p.nombre as producto_nombre, p.unidad_base, p.categoria_id
        FROM public.presentacion pr
        JOIN public.producto p ON pr.producto_id = p.id
        WHERE pr.id = :id AND pr.activa = true AND p.activo = true;
    """)
    fila = (await sesion.execute(sql, {"id": presentacion_id})).first()
    return dict(fila._mapping) if fila else None


async def verificar_establecimiento_activo(
    sesion: AsyncSession,
    establecimiento_id: UUID,
) -> bool:
    sql = text("SELECT 1 FROM public.establecimiento WHERE id = :id AND activo = true LIMIT 1;")
    fila = (await sesion.execute(sql, {"id": establecimiento_id})).first()
    return fila is not None


async def buscar_reporte_idempotente(
    sesion: AsyncSession,
    reportante_id: UUID,
    idempotency_key: UUID,
) -> dict[str, Any] | None:
    sql = text("""
        SELECT id, estado::text
        FROM public.reporte_precio
        WHERE reportante_id = :uid AND idempotency_key = :key
        LIMIT 1;
    """)
    fila = (await sesion.execute(sql, {"uid": reportante_id, "key": idempotency_key})).first()
    return dict(fila._mapping) if fila else None


async def insertar_reporte_precio(
    sesion: AsyncSession,
    datos: dict[str, Any],
) -> UUID:
    sql = text("""
        INSERT INTO public.reporte_precio (
            id, producto_id, presentacion_id, establecimiento_id, precio_cop,
            cantidad_base_snapshot, precio_por_base, fuente, reportante_id,
            observado_en, foto_prueba_path, estado, estado_original, senales,
            puntaje_anomalia, riesgo_contexto, conjunto_referencia, huella_red,
            idempotency_key, es_demo
        ) VALUES (
            :id, :producto_id, :presentacion_id, :establecimiento_id, :precio_cop,
            :cantidad_base, :precio_por_base, 'usuario', :reportante_id,
            :observado_en, :foto_ruta, CAST(:estado AS estado_confianza),
            CAST(:estado_original AS estado_confianza), :senales,
            :puntaje_anomalia, :riesgo_contexto, :conjunto_referencia, :huella_red,
            :idempotency_key, :es_demo
        ) RETURNING id;
    """)
    fila = (await sesion.execute(sql, datos)).first()
    if not fila:
        raise RuntimeError("No fue posible insertar el reporte de precio.")
    return UUID(str(fila[0]))


async def insertar_caso_moderacion(
    sesion: AsyncSession,
    tipo: str,
    referencia_tabla: str,
    referencia_id: UUID,
    detalle: dict[str, Any],
    prioridad: int = 3,
) -> UUID:
    import json

    sql = text("""
        INSERT INTO public.caso_moderacion (
            tipo, referencia_tabla, referencia_id, detalle, prioridad, estado
        ) VALUES (
            CAST(:tipo AS tipo_caso), :ref_tabla, :ref_id,
            CAST(:detalle AS jsonb), :prioridad, 'abierto'
        ) RETURNING id;
    """)
    fila = (
        await sesion.execute(
            sql,
            {
                "tipo": tipo,
                "ref_tabla": referencia_tabla,
                "ref_id": referencia_id,
                "detalle": json.dumps(detalle),
                "prioridad": prioridad,
            },
        )
    ).first()
    if not fila:
        raise RuntimeError("No fue posible insertar el caso de moderacion.")
    return UUID(str(fila[0]))


async def corroborar_reportes_previos(
    sesion: AsyncSession,
    presentacion_id: UUID,
    establecimiento_id: UUID,
    precio_cop: int,
    usuario_id: UUID,
    limite_dias: datetime,
) -> None:
    precio_min = int(precio_cop * 0.95)
    precio_max = int(precio_cop * 1.05)
    sql = text("""
        UPDATE public.perfil
        SET reportes_corroborados = reportes_corroborados + 1
        WHERE id IN (
            SELECT DISTINCT reportante_id
            FROM public.reporte_precio
            WHERE presentacion_id = :pres_id
              AND establecimiento_id = :est_id
              AND precio_cop BETWEEN :p_min AND :p_max
              AND reportante_id IS NOT NULL
              AND reportante_id <> :uid
              AND observado_en >= :limite
              AND estado = 'aceptado'
        );
    """)
    await sesion.execute(
        sql,
        {
            "pres_id": presentacion_id,
            "est_id": establecimiento_id,
            "p_min": precio_min,
            "p_max": precio_max,
            "uid": usuario_id,
            "limite": limite_dias,
        },
    )


async def reclasificar_rafaga_hacia_atras(
    sesion: AsyncSession,
    huella_red: str,
    establecimiento_id: UUID,
    limite_rafaga: datetime,
) -> list[tuple[UUID, UUID]]:
    sql_sel = text("""
        SELECT DISTINCT presentacion_id, establecimiento_id
        FROM public.reporte_precio
        WHERE huella_red = :huella
          AND establecimiento_id = :est_id
          AND creado_en >= :limite
          AND estado = 'aceptado';
    """)
    filas = (
        await sesion.execute(
            sql_sel,
            {"huella": huella_red, "est_id": establecimiento_id, "limite": limite_rafaga},
        )
    ).fetchall()

    sql_upd = text("""
        UPDATE public.reporte_precio
        SET estado = 'dudoso'
        WHERE huella_red = :huella
          AND establecimiento_id = :est_id
          AND creado_en >= :limite
          AND estado = 'aceptado';
    """)
    await sesion.execute(
        sql_upd,
        {"huella": huella_red, "est_id": establecimiento_id, "limite": limite_rafaga},
    )

    return [(f.presentacion_id, f.establecimiento_id) for f in filas]


async def listar_mis_reportes(
    sesion: AsyncSession,
    usuario_id: UUID,
    limite: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    sql_total = text("SELECT count(*) FROM public.reporte_precio WHERE reportante_id = :uid;")
    total = (await sesion.execute(sql_total, {"uid": usuario_id})).scalar() or 0

    sql_filas = text("""
        SELECT rp.id, p.nombre as producto_nombre, pr.etiqueta as presentacion_etiqueta,
               e.nombre as establecimiento_nombre, rp.precio_cop, rp.observado_en,
               rp.creado_en, rp.estado::text
        FROM public.reporte_precio rp
        JOIN public.presentacion pr ON rp.presentacion_id = pr.id
        JOIN public.producto p ON pr.producto_id = p.id
        JOIN public.establecimiento e ON rp.establecimiento_id = e.id
        WHERE rp.reportante_id = :uid
        ORDER BY rp.creado_en DESC
        LIMIT :limite OFFSET :offset;
    """)
    filas = (
        await sesion.execute(sql_filas, {"uid": usuario_id, "limite": limite, "offset": offset})
    ).fetchall()
    return [dict(f._mapping) for f in filas], total
