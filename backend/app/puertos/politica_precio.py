"""Puerto y politica de referencia para el calculo del precio vigente (T-24)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.parametros import obtener_parametros_dominio
from app.dominio.contraste import (
    PrecioOficialVigente,
    ResultadoContraste,
    contrastar_oficial_con_comunidad,
)
from app.dominio.parametros import ParametrosDominio
from app.dominio.sello import ResultadoSelloYPrecio, evaluar_sello_y_precio
from app.dominio.vigencia import CandidatoReporte

_SQL_UPSERT_PV = text("""
    INSERT INTO public.precio_vigente (
        presentacion_id, establecimiento_id, producto_id,
        precio_cop, precio_por_base, cantidad_base,
        sello, motivo_sello, n_reportes_validos, n_fuentes,
        dispersion, ultimo_reporte_en, reporte_origen_id, recalculado_en,
        precio_oficial_cop, diferencia_pct, requiere_revalidacion
    ) VALUES (
        :pres_id, :est_id, :prod_id,
        :precio_cop, :precio_por_base, :cantidad_base,
        CAST(:sello AS sello_precio), :motivo_sello, :n_validos, :n_fuentes,
        :dispersion, :ultimo_rep, :origen_id, now(),
        :precio_oficial_cop, :diferencia_pct, :requiere_revalidacion
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
        recalculado_en = now(),
        precio_oficial_cop = EXCLUDED.precio_oficial_cop,
        diferencia_pct = EXCLUDED.diferencia_pct,
        requiere_revalidacion = EXCLUDED.requiere_revalidacion;
""")

_SQL_DELETE_PV = text("""
    DELETE FROM public.precio_vigente
    WHERE presentacion_id = :pres_id AND establecimiento_id = :est_id;
""")

_SQL_DELETE_PV_PAR = text("""
    DELETE FROM public.precio_vigente
    WHERE presentacion_id = :p AND establecimiento_id = :e;
""")


def _fila_precio_vigente(
    presentacion_id: UUID,
    establecimiento_id: UUID,
    producto_id: UUID,
    resultado: ResultadoSelloYPrecio,
    contraste: ResultadoContraste | None = None,
) -> dict[str, Any]:
    """Arma los parametros del UPSERT. Las dos politicas comparten esta unica forma."""
    return {
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
        "precio_oficial_cop": contraste.precio_oficial_cop if contraste else None,
        "diferencia_pct": contraste.diferencia_pct if contraste else None,
        "requiere_revalidacion": contraste.requiere_revalidacion if contraste else False,
    }


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


_SQL_REPORTES_PAR = text("""
    SELECT id, precio_cop, cantidad_base_snapshot, observado_en,
           reportante_id, fuente::text, foto_prueba_path, estado::text, producto_id
    FROM public.reporte_precio
    WHERE presentacion_id = :pres_id
      AND establecimiento_id = :est_id
      AND observado_en >= :limite
      AND estado IN ('aceptado', 'dudoso')
      AND es_demo = false
      AND fuente <> 'comercio'
    ORDER BY observado_en DESC;
""")

_SQL_PRECIO_OFICIAL_PAR = text("""
    SELECT po.precio_cop, po.revalidado_en, pr.cantidad_base
    FROM public.precio_oficial po
    JOIN public.presentacion pr ON pr.id = po.presentacion_id
    WHERE po.presentacion_id = :pres_id
      AND po.establecimiento_id = :est_id
      AND po.activo = true;
""")

_SQL_PARES_RECALCULO = text("""
    SELECT presentacion_id, establecimiento_id
    FROM public.reporte_precio
    WHERE observado_en >= :limite
      AND estado IN ('aceptado', 'dudoso')
      AND es_demo = false
      AND fuente <> 'comercio'
    UNION
    SELECT presentacion_id, establecimiento_id
    FROM public.precio_oficial
    WHERE activo = true;
""")


async def listar_pares_para_recalculo(
    sesion: AsyncSession,
    limite_inferior: datetime,
) -> list[tuple[UUID, UUID]]:
    """Pares con comunidad vigente o precio oficial activo, sin duplicados.

    El historial oficial (`fuente='comercio'`) no es un voto comunitario y por eso
    no alimenta la evaluacion de reportes. Los pares con solo precio oficial si
    entran: el comercio manda aunque la comunidad no haya reportado (D-01). El
    `UNION` evita recalcular dos veces un par que tiene ambas fuentes.
    """
    filas = (await sesion.execute(_SQL_PARES_RECALCULO, {"limite": limite_inferior})).fetchall()
    return [(f.presentacion_id, f.establecimiento_id) for f in filas]


async def _leer_candidatos(
    sesion: AsyncSession,
    presentacion_id: UUID,
    establecimiento_id: UUID,
    limite_inferior: datetime,
) -> tuple[UUID | None, list[CandidatoReporte]]:
    """Lee los reportes vigentes del par y los convierte en candidatos del dominio puro."""
    filas = (
        await sesion.execute(
            _SQL_REPORTES_PAR,
            {
                "pres_id": presentacion_id,
                "est_id": establecimiento_id,
                "limite": limite_inferior,
            },
        )
    ).fetchall()

    if not filas:
        return None, []

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
    producto_id: UUID = filas[0].producto_id
    return producto_id, candidatos


async def _leer_precio_oficial(
    sesion: AsyncSession,
    presentacion_id: UUID,
    establecimiento_id: UUID,
) -> PrecioOficialVigente | None:
    """Lee el precio que el comercio publico para el par, si existe y esta activo."""
    fila = (
        await sesion.execute(
            _SQL_PRECIO_OFICIAL_PAR,
            {"pres_id": presentacion_id, "est_id": establecimiento_id},
        )
    ).fetchone()

    if fila is None:
        return None

    return PrecioOficialVigente(
        precio_cop=int(fila.precio_cop),
        cantidad_base=fila.cantidad_base,
        confirmado_en=fila.revalidado_en,
    )


class SoloUsuarios:
    """Politica de la Etapa 1: calcula el precio vigente con reportes de usuarios y semilla.

    En Etapa 2 solo se inyecta de forma explicita para pruebas o para conservar el
    comportamiento historico del nucleo. La politica de produccion es
    `OficialConContraste` (D-01).
    """

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

        producto_id, candidatos = await _leer_candidatos(
            sesion, presentacion_id, establecimiento_id, limite_inferior
        )

        if producto_id is None:
            await sesion.execute(
                _SQL_DELETE_PV, {"pres_id": presentacion_id, "est_id": establecimiento_id}
            )
            return None

        resultado = evaluar_sello_y_precio(candidatos, instante, parametros)

        if resultado is None:
            await sesion.execute(
                _SQL_DELETE_PV, {"pres_id": presentacion_id, "est_id": establecimiento_id}
            )
            return None

        await sesion.execute(
            _SQL_UPSERT_PV,
            _fila_precio_vigente(presentacion_id, establecimiento_id, producto_id, resultado),
        )

        return resultado


class OficialConContraste:
    """Politica de la Etapa 2: el precio del comercio manda, salvo que la comunidad lo contradiga.

    Es la segunda implementacion del puerto `PoliticaPrecioReferencia`. El protocolo no cambio
    de firma para que existiera: ese es, en concreto, el gancho que EC-05 pone a prueba.

    La decision de que precio se muestra vive en `app.dominio.contraste`, que es codigo puro y
    comprobable sin base de datos. Esta clase solo lee, pasa los datos a la regla y persiste.
    """

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

        producto_id, candidatos = await _leer_candidatos(
            sesion, presentacion_id, establecimiento_id, limite_inferior
        )
        oficial = await _leer_precio_oficial(sesion, presentacion_id, establecimiento_id)

        comunidad = evaluar_sello_y_precio(candidatos, instante, parametros) if candidatos else None
        contraste = contrastar_oficial_con_comunidad(
            oficial, comunidad, candidatos, instante, parametros
        )

        if contraste is None:
            await sesion.execute(
                _SQL_DELETE_PV, {"pres_id": presentacion_id, "est_id": establecimiento_id}
            )
            return None

        # Con precio oficial y sin ningun reporte, el producto lo determina la publicacion
        # del comercio, no el historial de la comunidad.
        producto_final = (
            producto_id
            if producto_id is not None
            else await _producto_de_oficial(sesion, presentacion_id, establecimiento_id)
        )
        if producto_final is None:
            await sesion.execute(
                _SQL_DELETE_PV, {"pres_id": presentacion_id, "est_id": establecimiento_id}
            )
            return None

        await sesion.execute(
            _SQL_UPSERT_PV,
            _fila_precio_vigente(
                presentacion_id,
                establecimiento_id,
                producto_final,
                contraste.resultado,
                contraste,
            ),
        )

        return contraste.resultado


async def _producto_de_oficial(
    sesion: AsyncSession,
    presentacion_id: UUID,
    establecimiento_id: UUID,
) -> UUID | None:
    """Producto al que pertenece un precio oficial, cuando no hay reportes que lo digan."""
    fila = (
        await sesion.execute(
            text("""
                SELECT producto_id FROM public.precio_oficial
                WHERE presentacion_id = :pres_id
                  AND establecimiento_id = :est_id
                  AND activo = true;
            """),
            {"pres_id": presentacion_id, "est_id": establecimiento_id},
        )
    ).fetchone()
    producto_id: UUID | None = fila.producto_id if fila is not None else None
    return producto_id


def _agrupar_reportes_por_par(filas: list[Any]) -> dict[tuple[UUID, UUID], list[Any]]:
    por_par: dict[tuple[UUID, UUID], list[Any]] = {}
    for f in filas:
        por_par.setdefault((f.presentacion_id, f.establecimiento_id), []).append(f)
    return por_par


def _evaluar_lote_pares(
    por_par: dict[tuple[UUID, UUID], list[Any]],
    instante: datetime,
    parametros: ParametrosDominio,
) -> tuple[list[dict[str, Any]], set[tuple[UUID, UUID]]]:
    lote_upsert: list[dict[str, Any]] = []
    pares_activos: set[tuple[UUID, UUID]] = set()

    for (p_id, e_id), grupo in por_par.items():
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
            for f in grupo
        ]
        resultado = evaluar_sello_y_precio(candidatos, instante, parametros)
        if resultado is not None:
            pares_activos.add((p_id, e_id))
            lote_upsert.append(_fila_precio_vigente(p_id, e_id, grupo[0].producto_id, resultado))
    return lote_upsert, pares_activos


async def _reconstruir_con_politica_personalizada(
    sesion: AsyncSession,
    pol: PoliticaPrecioReferencia,
    limite_inferior: datetime,
    instante: datetime,
    parametros: ParametrosDominio,
) -> int:
    pares = await listar_pares_para_recalculo(sesion, limite_inferior)
    recalculados = 0
    pares_activos: set[tuple[UUID, UUID]] = set()
    for p_id, e_id in pares:
        res = await pol.recalcular_par(sesion, p_id, e_id, instante, parametros)
        if res is not None:
            recalculados += 1
            pares_activos.add((p_id, e_id))
    await _borrar_pares_fuera_de(sesion, pares_activos)
    return recalculados


async def _borrar_pares_fuera_de(
    sesion: AsyncSession,
    pares_activos: set[tuple[UUID, UUID]],
) -> None:
    """Elimina proyecciones que ya no tienen comunidad vigente ni precio oficial."""
    sql_todos_pv = text("SELECT presentacion_id, establecimiento_id FROM public.precio_vigente;")
    filas_pv = (await sesion.execute(sql_todos_pv)).fetchall()
    a_borrar = [
        {"p": p_id, "e": e_id} for p_id, e_id in filas_pv if (p_id, e_id) not in pares_activos
    ]
    if a_borrar:
        await sesion.execute(_SQL_DELETE_PV_PAR, a_borrar)


async def reconstruir_precio_vigente(
    sesion: AsyncSession,
    ahora: datetime | None = None,
    politica: PoliticaPrecioReferencia | None = None,
) -> int:
    """Reconstruye por completo la tabla precio_vigente desde reportes y precios oficiales."""
    instante = ahora if ahora is not None else datetime.now(UTC)
    pol = politica if politica is not None else OficialConContraste()
    parametros = await obtener_parametros_dominio(sesion)
    limite_inferior = instante - timedelta(days=parametros.vigencia_antiguo_dias)

    if not isinstance(pol, SoloUsuarios):
        return await _reconstruir_con_politica_personalizada(
            sesion, pol, limite_inferior, instante, parametros
        )

    sql_reportes = text("""
        SELECT id, presentacion_id, establecimiento_id, producto_id,
               precio_cop, cantidad_base_snapshot, observado_en,
               reportante_id, fuente::text, foto_prueba_path, estado::text
        FROM public.reporte_precio
        WHERE observado_en >= :limite
          AND estado IN ('aceptado', 'dudoso')
          AND es_demo = false
          AND fuente <> 'comercio'
        ORDER BY observado_en DESC;
    """)
    filas = list((await sesion.execute(sql_reportes, {"limite": limite_inferior})).fetchall())
    por_par = _agrupar_reportes_por_par(filas)
    lote_upsert, pares_activos = _evaluar_lote_pares(por_par, instante, parametros)

    if lote_upsert:
        await sesion.execute(_SQL_UPSERT_PV, lote_upsert)

    await _borrar_pares_fuera_de(sesion, pares_activos)

    return len(lote_upsert)
