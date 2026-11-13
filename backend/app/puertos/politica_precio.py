"""Puerto y politica de referencia para el calculo del precio vigente (T-24)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.parametros import obtener_parametros_dominio
from app.dominio.parametros import ParametrosDominio
from app.dominio.sello import ResultadoSelloYPrecio, evaluar_sello_y_precio
from app.dominio.vigencia import CandidatoReporte


class PoliticaPrecioReferencia(Protocol):
    """Protocolo de calculo y actualizacion del precio de referencia vigente."""

    async def recalcular_par(
        self,
        sesion: AsyncSession,
        presentacion_id: UUID,
        establecimiento_id: UUID,
        ahora: datetime | None = None,
        params: ParametrosDominio | None = None,
    ) -> ResultadoSelloYPrecio | None:
        """Calcula y persiste en BD el precio vigente para el par especificado."""
        ...


class SoloUsuarios:
    """Politica de la Etapa 1: Calcula el precio vigente con reportes de usuarios y semilla."""

    async def recalcular_par(
        self,
        sesion: AsyncSession,
        presentacion_id: UUID,
        establecimiento_id: UUID,
        ahora: datetime | None = None,
        params: ParametrosDominio | None = None,
    ) -> ResultadoSelloYPrecio | None:
        instante = ahora if ahora is not None else datetime.now(UTC)
        parametros = params if params is not None else await obtener_parametros_dominio(sesion)

        limite_inferior = instante - timedelta(days=parametros.vigencia_antiguo_dias)

        sql_reportes = text("""
            SELECT id, precio_cop, cantidad_base_snapshot, observado_en,
                   reportante_id, fuente::text, foto_prueba_path, estado::text, producto_id
            FROM public.reporte_precio
            WHERE presentacion_id = :pres_id
              AND establecimiento_id = :est_id
              AND observado_en >= :limite
              AND estado IN ('aceptado', 'dudoso')
            ORDER BY observado_en DESC;
        """)

        filas = (
            await sesion.execute(
                sql_reportes,
                {
                    "pres_id": presentacion_id,
                    "est_id": establecimiento_id,
                    "limite": limite_inferior,
                },
            )
        ).fetchall()

        if not filas:
            sql_del = text("""
                DELETE FROM public.precio_vigente
                WHERE presentacion_id = :pres_id AND establecimiento_id = :est_id;
            """)
            await sesion.execute(
                sql_del, {"pres_id": presentacion_id, "est_id": establecimiento_id}
            )
            return None

        producto_id = filas[0].producto_id

        candidatos = [
            CandidatoReporte(
                id=f.id,
                precio_cop=int(f.precio_cop),
                cantidad_base=f.cantidad_base_snapshot,
                observado_en=f.observado_en,
                autor_id=str(f.reportante_id) if f.reportante_id else None,
                reputacion_autor=0.5,
                tiene_foto=bool(f.foto_prueba_path),
                estado=f.estado,
                fuente=f.fuente,
            )
            for f in filas
        ]

        resultado = evaluar_sello_y_precio(candidatos, instante, parametros)

        if resultado is None:
            sql_del = text("""
                DELETE FROM public.precio_vigente
                WHERE presentacion_id = :pres_id AND establecimiento_id = :est_id;
            """)
            await sesion.execute(
                sql_del, {"pres_id": presentacion_id, "est_id": establecimiento_id}
            )
            return None

        sql_upsert = text("""
            INSERT INTO public.precio_vigente (
                presentacion_id, establecimiento_id, producto_id,
                precio_cop, precio_por_base, cantidad_base,
                sello, motivo_sello, n_reportes_validos, n_fuentes,
                dispersion, ultimo_reporte_en, reporte_origen_id, recalculado_en
            ) VALUES (
                :pres_id, :est_id, :prod_id,
                :precio_cop, :precio_por_base, :cantidad_base,
                CAST(:sello AS sello_precio), :motivo_sello, :n_validos, :n_fuentes,
                :dispersion, :ultimo_rep, :origen_id, now()
            )
            ON CONFLICT (presentacion_id, establecimiento_id) DO UPDATE SET
                producto_id = EXCLUDED.producto_id,
                precio_cop = EXCLUDED.precio_cop,
                precio_por_base = EXCLUDED.precio_por_base,
                cantidad_base = EXCLUDED.cantidad_base,
                sello = EXCLUDED.sello,
                motivo_sello = EXCLUDED.motivo_sello,
                n_reportes_validos = EXCLUDED.n_reportes_validos,
                n_fuentes = EXCLUDED.n_fuentes,
                dispersion = EXCLUDED.dispersion,
                ultimo_reporte_en = EXCLUDED.ultimo_reporte_en,
                reporte_origen_id = EXCLUDED.reporte_origen_id,
                recalculado_en = now();
        """)

        await sesion.execute(
            sql_upsert,
            {
                "pres_id": presentacion_id,
                "est_id": establecimiento_id,
                "prod_id": producto_id,
                "precio_cop": resultado.precio_cop,
                "precio_por_base": resultado.precio_por_base,
                "cantidad_base": resultado.cantidad_base,
                "sello": resultado.sello,
                "motivo_sello": resultado.motivo_sello,
                "n_validos": resultado.n_reportes_validos,
                "n_fuentes": resultado.n_fuentes,
                "dispersion": resultado.dispersion,
                "ultimo_rep": resultado.ultimo_reporte_en,
                "origen_id": resultado.reporte_origen_id,
            },
        )

        return resultado


async def reconstruir_precio_vigente(
    sesion: AsyncSession,
    ahora: datetime | None = None,
    politica: PoliticaPrecioReferencia | None = None,
) -> int:
    """Reconstruye por completo la tabla precio_vigente desde los reportes historicos."""
    instante = ahora if ahora is not None else datetime.now(UTC)
    pol = politica if politica is not None else SoloUsuarios()
    parametros = await obtener_parametros_dominio(sesion)

    limite_inferior = instante - timedelta(days=parametros.vigencia_antiguo_dias)

    # 1. Obtener todos los pares con actividad en los ultimos 30 dias
    sql_pares = text("""
        SELECT DISTINCT presentacion_id, establecimiento_id
        FROM public.reporte_precio
        WHERE observado_en >= :limite
          AND estado IN ('aceptado', 'dudoso');
    """)
    pares = (await sesion.execute(sql_pares, {"limite": limite_inferior})).fetchall()

    recalculados = 0
    pares_activos: set[tuple[UUID, UUID]] = set()

    for p_id, e_id in pares:
        pares_activos.add((p_id, e_id))
        res = await pol.recalcular_par(sesion, p_id, e_id, instante, parametros)
        if res is not None:
            recalculados += 1

    # 2. Limpiar pares obsoletos en precio_vigente que ya no tienen reportes
    sql_todos_pv = text("SELECT presentacion_id, establecimiento_id FROM public.precio_vigente;")
    filas_pv = (await sesion.execute(sql_todos_pv)).fetchall()
    for p_id, e_id in filas_pv:
        if (p_id, e_id) not in pares_activos:
            sql_del = text("""
                DELETE FROM public.precio_vigente
                WHERE presentacion_id = :p AND establecimiento_id = :e;
            """)
            await sesion.execute(sql_del, {"p": p_id, "e": e_id})

    return recalculados
