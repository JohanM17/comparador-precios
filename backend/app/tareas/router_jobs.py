"""Endpoints internos para ejecucion de tareas programadas con X-Job-Token (T-34)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bd import obtener_sesion
from app.compartido.dependencias import obtener_puerto_cache
from app.compartido.errores import NoAutenticadoError
from app.config import obtener_configuracion
from app.dominio.reputacion import calcular_reputacion_bayesiana
from app.puertos.cache import PuertoCache
from app.puertos.politica_precio import OficialConContraste, reconstruir_precio_vigente

router = APIRouter(prefix="/internal/jobs", tags=["Jobs Internos"], include_in_schema=False)


def verificar_job_token(
    x_job_token: Annotated[str | None, Header(alias="X-Job-Token")] = None,
) -> None:
    cfg = obtener_configuracion()
    if not x_job_token or x_job_token != cfg.JOB_TOKEN:
        raise NoAutenticadoError("Token de ejecucion de tareas internas invalido o ausente.")


@router.post("/ping_bd", summary="Ping elemental a la base de datos")
async def job_ping_bd(
    _token: Annotated[None, Depends(verificar_job_token)],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> dict[str, Any]:
    res = (await sesion.execute(text("SELECT 1;"))).scalar()
    return {"ok": res == 1, "servicio": "bd"}


@router.post("/recalcular_reputacion", summary="Recalculo periodico de reputacion de perfiles")
async def job_recalcular_reputacion(
    _token: Annotated[None, Depends(verificar_job_token)],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> dict[str, int]:
    sql_perfiles = text("""
        SELECT id, reportes_corroborados, reportes_malos_confirmados
        FROM public.perfil
        WHERE estado = 'activa';
    """)
    filas = (await sesion.execute(sql_perfiles)).fetchall()
    for f in filas:
        rep = float(
            calcular_reputacion_bayesiana(
                int(f.reportes_corroborados), int(f.reportes_malos_confirmados)
            )
        )
        sql_upd = text(
            "UPDATE public.perfil SET reputacion = :rep, actualizado_en = now() WHERE id = :id;"
        )
        await sesion.execute(sql_upd, {"id": f.id, "rep": rep})

    await sesion.flush()
    return {"procesados": len(filas)}


@router.post("/reconstruir_precio_vigente", summary="Reconstruccion masiva de precio_vigente")
async def job_reconstruir_precio_vigente(
    _token: Annotated[None, Depends(verificar_job_token)],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
    cache: Annotated[PuertoCache, Depends(obtener_puerto_cache)],
) -> dict[str, int]:
    """Reconstruye con la politica de Etapa 2, incluidos pares con solo precio oficial."""
    ahora = datetime.now(UTC)
    reconstruidos = await reconstruir_precio_vigente(
        sesion, ahora=ahora, politica=OficialConContraste()
    )

    await cache.limpiar()
    await sesion.flush()
    return {"reconstruidos": reconstruidos}


@router.post("/limpiar_huellas", summary="Anonimizacion de huella_red segun Ley 1581")
async def job_limpiar_huellas(
    _token: Annotated[None, Depends(verificar_job_token)],
    sesion: Annotated[AsyncSession, Depends(obtener_sesion)],
) -> dict[str, int]:
    sql_dias = text(
        "SELECT valor FROM public.config_parametro WHERE clave = 'huella.retencion_dias';"
    )
    res_dias = (await sesion.execute(sql_dias)).scalar()
    dias = int(res_dias) if res_dias is not None else 30
    limite = datetime.now(UTC) - timedelta(days=dias)

    sql_upd = text("""
        UPDATE public.reporte_precio
        SET huella_red = NULL
        WHERE observado_en < :limite
          AND huella_red IS NOT NULL;
    """)
    res = await sesion.execute(sql_upd, {"limite": limite})
    await sesion.flush()
    cant = getattr(res, "rowcount", 0) or 0
    return {"huellas_limpiadas": int(cant)}
