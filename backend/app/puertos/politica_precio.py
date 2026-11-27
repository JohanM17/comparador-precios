"""Puerto y politica de referencia para el calculo del precio vigente (T-24)."""

from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)

# Forma unica de una fila del UPSERT: (columna, parametro, requiere cast de enum).
# `recalculado_en` no lleva parametro porque siempre es `now()`.
_COLUMNAS_UPSERT_PV: tuple[tuple[str, str | None, bool], ...] = (
    ("presentacion_id", "pres_id", False),
    ("establecimiento_id", "est_id", False),
    ("producto_id", "prod_id", False),
    ("precio_cop", "precio_cop", False),
    ("precio_por_base", "precio_por_base", False),
    ("cantidad_base", "cantidad_base", False),
    ("sello", "sello", True),
    ("motivo_sello", "motivo_sello", False),
    ("n_reportes_validos", "n_validos", False),
    ("n_fuentes", "n_fuentes", False),
    ("dispersion", "dispersion", False),
    ("ultimo_reporte_en", "ultimo_rep", False),
    ("reporte_origen_id", "origen_id", False),
    ("recalculado_en", None, False),
    ("precio_oficial_cop", "precio_oficial_cop", False),
    ("diferencia_pct", "diferencia_pct", False),
    ("requiere_revalidacion", "requiere_revalidacion", False),
)

_SQL_UPSERT_PV_CONFLICTO = """
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
        requiere_revalidacion = EXCLUDED.requiere_revalidacion
"""


def _expresion_upsert(
    columna: tuple[str, str | None, bool],
    sufijo: str,
) -> str:
    """Expresion SQL de una columna para una fila del UPSERT."""
    _, parametro, castear = columna
    if parametro is None:
        return "now()"
    valor = f":{parametro}{sufijo}"
    return f"CAST({valor} AS sello_precio)" if castear else valor


_COLUMNAS_SQL_UPSERT_PV = ", ".join(columna for columna, _, _ in _COLUMNAS_UPSERT_PV)
_VALORES_SQL_UPSERT_PV = ", ".join(
    _expresion_upsert(columna, "") for columna in _COLUMNAS_UPSERT_PV
)

_SQL_UPSERT_PV_TEXTO = f"""
    INSERT INTO public.precio_vigente ({_COLUMNAS_SQL_UPSERT_PV}) VALUES (
        {_VALORES_SQL_UPSERT_PV}
    ){_SQL_UPSERT_PV_CONFLICTO};
"""  # noqa: S608
_SQL_UPSERT_PV = text(_SQL_UPSERT_PV_TEXTO)

# El lote viaja como un unico JSON y PostgreSQL lo expande con `jsonb_to_recordset`.
# Un VALUES multi-fila obliga a un parametro por celda y asyncpg corta en 32767
# argumentos; con 16 columnas el limite serian ~2047 pares. Esta forma mantiene un
# solo UPSERT para cualquier tamano, con una sola ida y vuelta al pooler.
_SQL_UPSERT_PV_LOTE_TEXTO = f"""
    INSERT INTO public.precio_vigente ({_COLUMNAS_SQL_UPSERT_PV})
    SELECT
        x.pres_id, x.est_id, x.prod_id,
        x.precio_cop, x.precio_por_base, x.cantidad_base,
        CAST(x.sello AS sello_precio), x.motivo_sello,
        x.n_validos, x.n_fuentes, x.dispersion, x.ultimo_rep,
        x.origen_id, now(), x.precio_oficial_cop, x.diferencia_pct,
        x.requiere_revalidacion
    FROM jsonb_to_recordset(CAST(:lote AS jsonb)) AS x(
        pres_id uuid, est_id uuid, prod_id uuid,
        precio_cop integer, precio_por_base numeric, cantidad_base numeric,
        sello text, motivo_sello text, n_validos integer, n_fuentes integer,
        dispersion double precision, ultimo_rep timestamptz, origen_id uuid,
        precio_oficial_cop integer, diferencia_pct numeric,
        requiere_revalidacion boolean
    ){_SQL_UPSERT_PV_CONFLICTO};
"""  # noqa: S608
_SQL_UPSERT_PV_LOTE = text(_SQL_UPSERT_PV_LOTE_TEXTO)


_SQL_DELETE_PV = text("""
    DELETE FROM public.precio_vigente
    WHERE presentacion_id = :pres_id AND establecimiento_id = :est_id;
""")

_SQL_DELETE_PV_FUERA_DE = text("""
    DELETE FROM public.precio_vigente pv
    WHERE NOT EXISTS (
        SELECT 1
        FROM jsonb_to_recordset(CAST(:pares AS jsonb)) AS activo(pres_id uuid, est_id uuid)
        WHERE activo.pres_id = pv.presentacion_id
          AND activo.est_id = pv.establecimiento_id
    );
""")

# D-01: una contradiccion comunitaria abre un caso para que lo resuelva una persona.
# El NOT EXISTS evita duplicar mientras el caso siga abierto o en revision. Si ya fue
# resuelto, una nueva contradiccion puede abrir uno nuevo; el historial no se toca.
_SQL_ABRIR_CASO_DISPUTA = text("""
    INSERT INTO public.caso_moderacion (
        tipo, referencia_tabla, referencia_id, detalle, prioridad, estado
    )
    SELECT
        CAST('disputa_precio' AS tipo_caso),
        'presentacion',
        :pres_id,
        CAST(:detalle AS jsonb),
        2,
        CAST('abierto' AS estado_caso)
    WHERE NOT EXISTS (
        SELECT 1
        FROM public.caso_moderacion c
        WHERE c.tipo = CAST('disputa_precio' AS tipo_caso)
          AND c.referencia_tabla = 'presentacion'
          AND c.referencia_id = :pres_id
          AND c.estado IN ('abierto', 'en_revision')
          AND c.detalle ->> 'establecimiento_id' = :est_id_txt
    );
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


def _serializar_lote(lote: list[dict[str, Any]]) -> str:
    """Convierte el lote en el JSON que `jsonb_to_recordset` expande en la base."""

    def convertir(valor: Any) -> str:
        return valor.isoformat() if isinstance(valor, datetime) else str(valor)

    return json.dumps(lote, ensure_ascii=False, default=convertir)


async def _escribir_upsert_lote(sesion: AsyncSession, lote: list[dict[str, Any]]) -> None:
    """Escribe el lote completo en un solo UPSERT y en una sola ida y vuelta."""
    await sesion.execute(_SQL_UPSERT_PV_LOTE, {"lote": _serializar_lote(lote)})


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
    ORDER BY observado_en DESC, id DESC;
""")

_SQL_PRECIO_OFICIAL_PAR = text("""
    SELECT po.precio_cop, po.revalidado_en, pr.cantidad_base
    FROM public.precio_oficial po
    JOIN public.presentacion pr ON pr.id = po.presentacion_id
    WHERE po.presentacion_id = :pres_id
      AND po.establecimiento_id = :est_id
      AND po.activo = true;
""")

# D-01 durable: una disputa confirmada por un moderador vale como corte. Los reportes
# anteriores a esa resolucion ya fueron juzgados y no pueden reabrir el mismo caso.
# No se tocan ni se rechazan: solo dejan de alimentar la ventana de contradiccion.
_SQL_CORTE_DISPUTA_CONFIRMADA = text("""
    SELECT max(c.resuelto_en) AS corte
    FROM public.caso_moderacion c
    WHERE c.tipo = CAST('disputa_precio' AS tipo_caso)
      AND c.referencia_tabla = 'presentacion'
      AND c.referencia_id = :pres_id
      AND c.estado = CAST('resuelto' AS estado_caso)
      AND c.decision = CAST('confirmar' AS decision_caso)
      AND c.resuelto_en IS NOT NULL
      AND c.detalle ->> 'establecimiento_id' = :est_id_txt;
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

# Las tres consultas del lote traen todo lo que la politica necesita en memoria: los
# reportes vigentes, los precios oficiales activos y los cortes de disputa confirmada.
# Antes se repetian por cada par; con cientos de pares eso dominaba el costo del job.
_SQL_REPORTES_LOTE = text("""
    SELECT id, presentacion_id, establecimiento_id, producto_id,
           precio_cop, cantidad_base_snapshot, observado_en,
           reportante_id, fuente::text, foto_prueba_path, estado::text
    FROM public.reporte_precio
    WHERE observado_en >= :limite
      AND estado IN ('aceptado', 'dudoso')
      AND es_demo = false
      AND fuente <> 'comercio'
    ORDER BY observado_en DESC, id DESC;
""")

_SQL_OFICIALES_LOTE = text("""
    SELECT po.presentacion_id, po.establecimiento_id, po.producto_id,
           po.precio_cop, po.revalidado_en, pr.cantidad_base
    FROM public.precio_oficial po
    JOIN public.presentacion pr ON pr.id = po.presentacion_id
    WHERE po.activo = true;
""")

_SQL_CORTES_CONFIRMADOS_LOTE = text("""
    SELECT c.referencia_id,
           c.detalle ->> 'establecimiento_id' AS est_id_txt,
           max(c.resuelto_en) AS corte
    FROM public.caso_moderacion c
    WHERE c.tipo = CAST('disputa_precio' AS tipo_caso)
      AND c.referencia_tabla = 'presentacion'
      AND c.estado = CAST('resuelto' AS estado_caso)
      AND c.decision = CAST('confirmar' AS decision_caso)
      AND c.resuelto_en IS NOT NULL
    GROUP BY c.referencia_id, c.detalle ->> 'establecimiento_id';
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


def _candidato_desde_fila(fila: Any) -> CandidatoReporte:
    """Convierte una fila de `reporte_precio` en el candidato que entiende el dominio."""
    return CandidatoReporte(
        id=fila.id,
        precio_cop=int(fila.precio_cop),
        cantidad_base=fila.cantidad_base_snapshot,
        observado_en=fila.observado_en,
        autor_id=str(fila.reportante_id) if fila.reportante_id else None,
        reputacion_autor=0.5,
        tiene_foto=bool(fila.foto_prueba_path),
        estado=fila.estado,
        fuente=fila.fuente,
    )


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

    candidatos = [_candidato_desde_fila(f) for f in filas]
    producto_id: UUID = filas[0].producto_id
    return producto_id, candidatos


def _precio_oficial_desde_fila(fila: Any) -> PrecioOficialVigente:
    """Convierte una fila activa de `precio_oficial` en el valor del dominio."""
    return PrecioOficialVigente(
        precio_cop=int(fila.precio_cop),
        cantidad_base=fila.cantidad_base,
        confirmado_en=fila.revalidado_en,
    )


def _cortes_confirmados_por_par(filas: list[Any]) -> dict[tuple[UUID, UUID], datetime]:
    """Indexa el ultimo corte de disputa confirmada por `(presentacion, establecimiento)`.

    Un detalle historico corrupto no puede tumbar la reconstruccion completa: se ignora
    igual que en la ruta par a par, donde el `WHERE` del SQL tampoco lo encontraria.
    """
    cortes: dict[tuple[UUID, UUID], datetime] = {}
    for fila in filas:
        corte = fila.corte
        if not isinstance(corte, datetime):
            continue
        try:
            establecimiento_id = UUID(str(fila.est_id_txt))
        except (TypeError, ValueError):
            continue
        cortes[(fila.referencia_id, establecimiento_id)] = corte
    return cortes


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


async def _leer_corte_disputa_confirmada(
    sesion: AsyncSession,
    presentacion_id: UUID,
    establecimiento_id: UUID,
) -> datetime | None:
    """Ultima resolucion `confirmar` del par, o None si nunca se confirmo una disputa."""
    fila = (
        await sesion.execute(
            _SQL_CORTE_DISPUTA_CONFIRMADA,
            {"pres_id": presentacion_id, "est_id_txt": str(establecimiento_id)},
        )
    ).first()
    if fila is None:
        return None
    corte = fila.corte
    return corte if isinstance(corte, datetime) else None


def filtrar_candidatos_post_corte(
    candidatos: list[CandidatoReporte],
    corte: datetime | None,
) -> list[CandidatoReporte]:
    """Conserva solo los reportes posteriores a una disputa confirmada.

    El corte es estrictamente posterior: un reporte observado en el mismo instante
    de la resolucion ya estaba a la vista del moderador y no puede reabrir el caso.
    Sin corte se conserva la lista completa, que es el comportamiento historico.
    """
    if corte is None:
        return list(candidatos)
    return [c for c in candidatos if c.observado_en > corte]


def _detalle_caso_disputa(
    presentacion_id: UUID,
    establecimiento_id: UUID,
    producto_id: UUID,
    contraste: ResultadoContraste,
) -> dict[str, Any]:
    """Datos que el moderador necesita para decidir sin volver a reconstruir el contraste."""
    return {
        "presentacion_id": str(presentacion_id),
        "establecimiento_id": str(establecimiento_id),
        "producto_id": str(producto_id),
        "precio_oficial_cop": contraste.precio_oficial_cop,
        "precio_comunidad_cop": contraste.resultado.precio_cop,
        "diferencia_pct": (
            float(contraste.diferencia_pct) if contraste.diferencia_pct is not None else None
        ),
        "n_reportes_validos": contraste.resultado.n_reportes_validos,
        "n_fuentes": contraste.resultado.n_fuentes,
        "sello": contraste.resultado.sello,
    }


async def _abrir_caso_disputa(
    sesion: AsyncSession,
    presentacion_id: UUID,
    establecimiento_id: UUID,
    producto_id: UUID,
    contraste: ResultadoContraste,
) -> None:
    """Abre el caso de moderacion de una disputa sin poder tumbar el calculo del precio.

    La insercion va dentro de un SAVEPOINT: si la tabla de casos falla, PostgreSQL
    deshace solo ese INSERT y la transaccion que guarda `precio_vigente` sigue viva.
    El precio es la funcion principal; el caso es una tarea de moderacion que puede
    reintentarse en el siguiente recalculo.
    """
    detalle = json.dumps(
        _detalle_caso_disputa(presentacion_id, establecimiento_id, producto_id, contraste),
        ensure_ascii=False,
    )
    parametros = {
        "pres_id": presentacion_id,
        "est_id_txt": str(establecimiento_id),
        "detalle": detalle,
    }
    try:
        async with sesion.begin_nested():
            await sesion.execute(_SQL_ABRIR_CASO_DISPUTA, parametros)
    except Exception as exc:  # noqa: BLE001
        # Solo el tipo de error: sin IDs, SQL ni coordenadas en el log (Ley 1581).
        logger.warning(
            "No se pudo abrir el caso de disputa (%s); el precio vigente se calculo igual.",
            type(exc).__name__,
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

        # La comunidad completa alimenta el precio y los conteos del resultado oficial;
        # solo la ventana de contradiccion ignora lo que un moderador ya confirmo.
        comunidad = evaluar_sello_y_precio(candidatos, instante, parametros) if candidatos else None
        corte = (
            await _leer_corte_disputa_confirmada(sesion, presentacion_id, establecimiento_id)
            if oficial is not None
            else None
        )
        candidatos_contraste = filtrar_candidatos_post_corte(candidatos, corte)
        contraste = contrastar_oficial_con_comunidad(
            oficial, comunidad, candidatos_contraste, instante, parametros
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

        if contraste.hay_disputa:
            await _abrir_caso_disputa(
                sesion,
                presentacion_id,
                establecimiento_id,
                producto_final,
                contraste,
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
        candidatos = [_candidato_desde_fila(f) for f in grupo]
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


async def _reconstruir_oficial_con_contraste(
    sesion: AsyncSession,
    limite_inferior: datetime,
    instante: datetime,
    parametros: ParametrosDominio,
) -> int:
    """Reconstruye toda la tabla con tres consultas y un solo UPSERT.

    El costo de la version par a par era una consulta de reportes, una de precio
    oficial y otra de corte por cada par. Aqui se traen los tres conjuntos completos,
    se agrupan en memoria y solo se abre un savepoint para los pocos pares que de
    verdad quedan en disputa.
    """
    filas_reportes = list(
        (await sesion.execute(_SQL_REPORTES_LOTE, {"limite": limite_inferior})).fetchall()
    )
    filas_oficiales = list((await sesion.execute(_SQL_OFICIALES_LOTE)).fetchall())
    filas_cortes = list((await sesion.execute(_SQL_CORTES_CONFIRMADOS_LOTE)).fetchall())

    por_par = _agrupar_reportes_por_par(filas_reportes)
    oficiales = {(f.presentacion_id, f.establecimiento_id): f for f in filas_oficiales}
    cortes = _cortes_confirmados_por_par(filas_cortes)

    lote: list[dict[str, Any]] = []
    pares_activos: set[tuple[UUID, UUID]] = set()
    disputas: list[tuple[UUID, UUID, UUID, ResultadoContraste]] = []

    for par in set(por_par) | set(oficiales):
        pres_id, est_id = par
        grupo = por_par.get(par, [])
        fila_oficial = oficiales.get(par)

        candidatos = [_candidato_desde_fila(f) for f in grupo]
        comunidad = evaluar_sello_y_precio(candidatos, instante, parametros) if candidatos else None
        oficial = _precio_oficial_desde_fila(fila_oficial) if fila_oficial is not None else None
        candidatos_contraste = filtrar_candidatos_post_corte(candidatos, cortes.get(par))
        contraste = contrastar_oficial_con_comunidad(
            oficial, comunidad, candidatos_contraste, instante, parametros
        )
        if contraste is None:
            continue

        producto_id: UUID | None = grupo[0].producto_id if grupo else None
        if producto_id is None and fila_oficial is not None:
            producto_id = fila_oficial.producto_id
        if producto_id is None:
            continue

        pares_activos.add(par)
        lote.append(
            _fila_precio_vigente(
                pres_id,
                est_id,
                producto_id,
                contraste.resultado,
                contraste,
            )
        )
        if contraste.hay_disputa:
            disputas.append((pres_id, est_id, producto_id, contraste))

    if lote:
        await _escribir_upsert_lote(sesion, lote)

    # El precio ya esta guardado; el caso es una tarea de moderacion aparte y cada uno
    # lleva su propio savepoint para que un fallo no tumbe el lote completo.
    for pres_id, est_id, producto_id, contraste in disputas:
        await _abrir_caso_disputa(sesion, pres_id, est_id, producto_id, contraste)

    await _borrar_pares_fuera_de(sesion, pares_activos)
    return len(lote)


def _serializar_pares_activos(pares: set[tuple[UUID, UUID]]) -> str:
    """Convierte el conjunto activo en el JSON que expande `jsonb_to_recordset`."""
    return json.dumps(
        [{"pres_id": str(pres_id), "est_id": str(est_id)} for pres_id, est_id in pares],
        ensure_ascii=False,
    )


async def _borrar_pares_fuera_de(
    sesion: AsyncSession,
    pares_activos: set[tuple[UUID, UUID]],
) -> None:
    """Elimina proyecciones que ya no tienen comunidad vigente ni precio oficial."""
    await sesion.execute(
        _SQL_DELETE_PV_FUERA_DE,
        {"pares": _serializar_pares_activos(pares_activos)},
    )


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

    if isinstance(pol, OficialConContraste):
        return await _reconstruir_oficial_con_contraste(
            sesion, limite_inferior, instante, parametros
        )
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
