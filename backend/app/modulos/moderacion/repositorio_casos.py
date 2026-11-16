"""Acceso a datos para casos de moderacion y penalizaciones de reputacion."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.reputacion import calcular_reputacion_bayesiana


async def listar_casos_bd(
    sesion: AsyncSession,
    estado: str | None = None,
    tipo: str | None = None,
    prioridad: int | None = None,
    limite: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    condiciones = ["1=1"]
    params: dict[str, Any] = {"limite": limite, "offset": offset}
    if estado:
        condiciones.append("estado = CAST(:estado AS estado_caso)")
        params["estado"] = estado
    if tipo:
        condiciones.append("tipo = CAST(:tipo AS tipo_caso)")
        params["tipo"] = tipo
    if prioridad is not None:
        condiciones.append("prioridad = :prioridad")
        params["prioridad"] = prioridad

    where_sql = " AND ".join(condiciones)
    sql_total = text(f"SELECT count(*) FROM public.caso_moderacion WHERE {where_sql};")  # noqa: S608
    total = (await sesion.execute(sql_total, params)).scalar() or 0

    sql_casos = text(f"""
        SELECT id, tipo::text, referencia_tabla, referencia_id, detalle,
               prioridad, estado::text, decision::text, moderador_id, nota,
               creado_en, resuelto_en
        FROM public.caso_moderacion
        WHERE {where_sql}
        ORDER BY prioridad ASC, creado_en ASC
        LIMIT :limite OFFSET :offset;
    """)  # noqa: S608
    filas = (await sesion.execute(sql_casos, params)).fetchall()
    return [dict(f._mapping) for f in filas], int(total)


async def obtener_caso_por_id_bd(sesion: AsyncSession, caso_id: UUID) -> dict[str, Any] | None:
    sql = text("""
        SELECT id, tipo::text, referencia_tabla, referencia_id, detalle,
               prioridad, estado::text, decision::text, moderador_id, nota,
               creado_en, resuelto_en
        FROM public.caso_moderacion WHERE id = :id;
    """)
    fila = (await sesion.execute(sql, {"id": caso_id})).first()
    return dict(fila._mapping) if fila else None


async def obtener_datos_referencia_bd(
    sesion: AsyncSession, tabla: str, ref_id: UUID | None
) -> dict[str, Any] | None:
    if not ref_id or tabla != "reporte_precio":
        return None
    sql = text("""
        SELECT rp.id, rp.precio_cop, rp.precio_por_base, rp.estado::text as estado_reporte,
               rp.observado_en, rp.reportante_id, rp.producto_id, rp.presentacion_id,
               rp.establecimiento_id, p.nombre as producto_nombre,
               pr.etiqueta as presentacion_etiqueta, e.nombre as establecimiento_nombre,
               perf.alias as reportante_alias
        FROM public.reporte_precio rp
        JOIN public.producto p ON rp.producto_id = p.id
        JOIN public.presentacion pr ON rp.presentacion_id = pr.id
        JOIN public.establecimiento e ON rp.establecimiento_id = e.id
        LEFT JOIN public.perfil perf ON rp.reportante_id = perf.id
        WHERE rp.id = :rid;
    """)
    fila = (await sesion.execute(sql, {"rid": ref_id})).first()
    return dict(fila._mapping) if fila else None


async def actualizar_caso_resuelto_bd(
    sesion: AsyncSession,
    caso_id: UUID,
    decision: str,
    nota: str,
    moderador_id: UUID,
    resuelto_en: datetime,
) -> None:
    sql = text("""
        UPDATE public.caso_moderacion
        SET estado = 'resuelto',
            decision = CAST(:decision AS decision_caso),
            nota = :nota,
            moderador_id = :mod_id,
            resuelto_en = :resuelto_en
        WHERE id = :id;
    """)
    await sesion.execute(
        sql,
        {
            "id": caso_id,
            "decision": decision,
            "nota": nota,
            "mod_id": moderador_id,
            "resuelto_en": resuelto_en,
        },
    )


async def actualizar_estado_reporte_bd(
    sesion: AsyncSession,
    reporte_id: UUID,
    nuevo_estado: str,
    moderador_id: UUID,
    revisado_en: datetime,
) -> None:
    sql = text("""
        UPDATE public.reporte_precio
        SET estado = CAST(:estado AS estado_confianza),
            revisado_por = :mod_id,
            revisado_en = :revisado_en
        WHERE id = :id;
    """)
    await sesion.execute(
        sql,
        {
            "id": reporte_id,
            "estado": nuevo_estado,
            "mod_id": moderador_id,
            "revisado_en": revisado_en,
        },
    )


async def penalizar_reputacion_autor_bd(sesion: AsyncSession, autor_id: UUID) -> float:
    sql_perfil = text("""
        SELECT reportes_corroborados, reportes_malos_confirmados
        FROM public.perfil WHERE id = :id FOR UPDATE;
    """)
    fila = (await sesion.execute(sql_perfil, {"id": autor_id})).first()
    if not fila:
        return 0.5

    a = int(fila.reportes_corroborados)
    m = int(fila.reportes_malos_confirmados) + 1
    nueva_rep = float(calcular_reputacion_bayesiana(a, m))

    sql_upd = text("""
        UPDATE public.perfil
        SET reportes_malos_confirmados = :m,
            reputacion = :rep,
            actualizado_en = now()
        WHERE id = :id;
    """)
    await sesion.execute(sql_upd, {"id": autor_id, "m": m, "rep": nueva_rep})
    return nueva_rep


async def obtener_usuario_moderacion_bd(
    sesion: AsyncSession, usuario_id: UUID
) -> dict[str, Any] | None:
    sql_perf = text("""
        SELECT id, alias, rol::text, estado::text, suspendida_hasta,
               reputacion, reportes_corroborados, reportes_malos_confirmados, creado_en
        FROM public.perfil WHERE id = :id;
    """)
    perf = (await sesion.execute(sql_perf, {"id": usuario_id})).first()
    if not perf:
        return None

    sql_sanc = text("""
        SELECT id, tipo::text, motivo, desde, hasta, apelacion, apelacion_resuelta
        FROM public.sancion WHERE usuario_id = :id ORDER BY desde DESC;
    """)
    sanciones = [
        dict(s._mapping) for s in (await sesion.execute(sql_sanc, {"id": usuario_id})).fetchall()
    ]

    sql_rep = text("""
        SELECT estado::text, count(*) as cant
        FROM public.reporte_precio WHERE reportante_id = :id GROUP BY estado;
    """)
    filas_rep = (await sesion.execute(sql_rep, {"id": usuario_id})).fetchall()
    conteos = {f.estado: int(f.cant) for f in filas_rep}

    datos = dict(perf._mapping)
    datos["reputacion"] = float(datos["reputacion"])
    datos["sanciones"] = sanciones
    datos["conteo_reportes"] = conteos
    return datos
