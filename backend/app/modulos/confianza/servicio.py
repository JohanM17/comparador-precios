"""Servicio de evaluacion de anomalias, riesgo de contexto y deteccion de rafagas (T-32)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.huella import calcular_huella_red
from app.compartido.parametros import obtener_parametros_dominio
from app.compartido.seguridad import UsuarioAutenticado
from app.config import obtener_configuracion
from app.dominio.anomalia import CandidatoAnomalia, NivelReferencia
from app.dominio.riesgo import ContextoReporte, EvaluacionReporte, evaluar_reporte


class ServicioConfianza:
    """Orquestador de evaluacion de confianza y deteccion de fraudes en reportes de precios."""

    def __init__(self) -> None:
        self.cfg = obtener_configuracion()

    async def _obtener_municipio(self, sesion: AsyncSession, establecimiento_id: UUID) -> str:
        sql = text("SELECT municipio FROM public.establecimiento WHERE id = :id;")
        fila = (await sesion.execute(sql, {"id": establecimiento_id})).first()
        return str(fila[0]) if fila else "Armenia"

    async def _cargar_niveles_referencia(
        self,
        sesion: AsyncSession,
        presentacion_id: UUID,
        establecimiento_id: UUID,
        producto_id: UUID,
        usuario_id: UUID,
        municipio: str,
        limite_dias: datetime,
        es_demo: bool,
    ) -> NivelReferencia:
        # Nivel 1: presentacion_tienda
        sql_n1 = text("""
            SELECT precio_cop FROM public.reporte_precio
            WHERE presentacion_id = :pres_id AND establecimiento_id = :est_id
              AND observado_en >= :limite AND estado = 'aceptado'
              AND (reportante_id IS NULL OR reportante_id <> :uid)
              AND es_demo = :es_demo
            ORDER BY observado_en DESC;
        """)
        filas_n1 = (
            await sesion.execute(
                sql_n1,
                {
                    "pres_id": presentacion_id,
                    "est_id": establecimiento_id,
                    "limite": limite_dias,
                    "uid": usuario_id,
                    "es_demo": es_demo,
                },
            )
        ).fetchall()
        precios_n1 = [int(f[0]) for f in filas_n1]

        # Nivel 2: presentacion en el mismo municipio
        sql_n2 = text("""
            SELECT rp.precio_cop FROM public.reporte_precio rp
            JOIN public.establecimiento e ON rp.establecimiento_id = e.id
            WHERE rp.presentacion_id = :pres_id
              AND e.municipio = :muni
              AND rp.observado_en >= :limite AND rp.estado = 'aceptado'
              AND (rp.reportante_id IS NULL OR rp.reportante_id <> :uid)
              AND rp.es_demo = :es_demo
            ORDER BY rp.observado_en DESC;
        """)
        filas_n2 = (
            await sesion.execute(
                sql_n2,
                {
                    "pres_id": presentacion_id,
                    "muni": municipio,
                    "limite": limite_dias,
                    "uid": usuario_id,
                    "es_demo": es_demo,
                },
            )
        ).fetchall()
        precios_n2 = [int(f[0]) for f in filas_n2]

        # Nivel 3: producto_unitario en el mismo municipio
        sql_n3 = text("""
            SELECT rp.precio_por_base FROM public.reporte_precio rp
            JOIN public.establecimiento e ON rp.establecimiento_id = e.id
            WHERE rp.producto_id = :prod_id
              AND e.municipio = :muni
              AND rp.observado_en >= :limite AND rp.estado = 'aceptado'
              AND (rp.reportante_id IS NULL OR rp.reportante_id <> :uid)
              AND rp.es_demo = :es_demo
            ORDER BY rp.observado_en DESC;
        """)
        filas_n3 = (
            await sesion.execute(
                sql_n3,
                {
                    "prod_id": producto_id,
                    "muni": municipio,
                    "limite": limite_dias,
                    "uid": usuario_id,
                    "es_demo": es_demo,
                },
            )
        ).fetchall()
        precios_n3 = [Decimal(str(f[0])) for f in filas_n3]

        return NivelReferencia(
            presentacion_tienda=precios_n1,
            presentacion=precios_n2,
            producto_unitario=precios_n3,
        )

    async def _detectar_rafaga(
        self,
        sesion: AsyncSession,
        huella_red: str,
        establecimiento_id: UUID,
        ventana_min: int,
        umbral_cuentas: int,
        ahora: datetime,
    ) -> bool:
        limite_rafaga = ahora - timedelta(minutes=ventana_min)
        sql = text("""
            SELECT count(DISTINCT reportante_id)
            FROM public.reporte_precio
            WHERE huella_red = :huella
              AND establecimiento_id = :est_id
              AND creado_en >= :limite;
        """)
        conteo = (
            await sesion.execute(
                sql,
                {
                    "huella": huella_red,
                    "est_id": establecimiento_id,
                    "limite": limite_rafaga,
                },
            )
        ).scalar() or 0

        # Si el conteo existente mas este usuario alcanza el umbral de cuentas
        return bool((conteo + 1) >= umbral_cuentas)

    async def _cargar_datos_autor(
        self,
        sesion: AsyncSession,
        usuario_id: UUID,
    ) -> tuple[datetime, int, Decimal]:
        sql = text("""
            SELECT creado_en, reportes_corroborados, reputacion
            FROM public.perfil WHERE id = :uid;
        """)
        fila = (await sesion.execute(sql, {"uid": usuario_id})).first()
        if fila:
            return fila[0], int(fila[1]), Decimal(str(fila[2]))
        return datetime.now(UTC), 0, Decimal("0.500")

    async def evaluar_reporte_entrante(
        self,
        sesion: AsyncSession,
        usuario: UsuarioAutenticado,
        presentacion_id: UUID,
        establecimiento_id: UUID,
        producto_id: UUID,
        precio_cop: int,
        precio_por_base: Decimal,
        tiene_foto: bool,
        ip_cliente: str,
        es_demo: bool = False,
        ahora: datetime | None = None,
    ) -> tuple[EvaluacionReporte, str]:
        """Aplica las reglas completas de F2 pasos 5 y 6 retornando la evaluacion y la huella."""
        instante = ahora if ahora is not None else datetime.now(UTC)
        params = await obtener_parametros_dominio(sesion)

        secreto = self.cfg.SUPABASE_JWT_SECRET or "secreto_huella_local_comparador_32_bytes"
        huella_red = calcular_huella_red(ip_cliente, secreto, instante)

        municipio = await self._obtener_municipio(sesion, establecimiento_id)
        limite_referencia = instante - timedelta(days=params.anomalia_ventana_dias)

        niveles = await self._cargar_niveles_referencia(
            sesion=sesion,
            presentacion_id=presentacion_id,
            establecimiento_id=establecimiento_id,
            producto_id=producto_id,
            usuario_id=usuario.id,
            municipio=municipio,
            limite_dias=limite_referencia,
            es_demo=es_demo,
        )

        es_rafaga = await self._detectar_rafaga(
            sesion=sesion,
            huella_red=huella_red,
            establecimiento_id=establecimiento_id,
            ventana_min=params.rafaga_ventana_min,
            umbral_cuentas=params.rafaga_min_cuentas,
            ahora=instante,
        )

        creado_en_autor, corroborados, reputacion = await self._cargar_datos_autor(
            sesion, usuario.id
        )

        contexto = ContextoReporte(
            tiene_foto=tiene_foto,
            creado_en_autor=creado_en_autor,
            reportes_corroborados=corroborados,
            reputacion_autor=reputacion,
            es_rafaga=es_rafaga,
        )

        candidato = CandidatoAnomalia(
            precio_cop=precio_cop,
            precio_por_base=precio_por_base,
        )

        evaluacion = evaluar_reporte(candidato, niveles, contexto, instante, params)
        return evaluacion, huella_red
