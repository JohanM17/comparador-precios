"""Servicio de aplicacion para registro de reportes, historial y comparaciones (T-23 a T-26)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.errores import NoEncontradoError
from app.compartido.limites import LimitadorVentanaDeslizante
from app.compartido.parametros import obtener_parametros_dominio
from app.compartido.seguridad import UsuarioAutenticado
from app.dominio.parametros import ParametrosDominio
from app.dominio.unidades import calcular_precio_por_base
from app.modulos.confianza.servicio import ServicioConfianza
from app.modulos.precios import repositorio
from app.modulos.precios.esquemas import (
    CrearReporteEntrada,
    CrearReporteRespuesta,
    DatosReporteRespuesta,
    ElementoReportePropio,
    MisReportesRespuesta,
)
from app.modulos.precios.validaciones import (
    determinar_estado_visible,
    validar_entrada_reporte,
    validar_limites_usuario,
)
from app.puertos.cache import PuertoCache
from app.puertos.politica_precio import PoliticaPrecioReferencia, SoloUsuarios

limitador_escritura = LimitadorVentanaDeslizante()


class ServicioPrecios:
    """Orquestador integral de logica de precios, comparacion y evaluacion comunitaria."""

    def __init__(
        self,
        sesion: AsyncSession,
        puerto_cache: PuertoCache,
        politica_precio: PoliticaPrecioReferencia | None = None,
        servicio_confianza: ServicioConfianza | None = None,
    ) -> None:
        self.sesion = sesion
        self.cache = puerto_cache
        self.politica = politica_precio if politica_precio is not None else SoloUsuarios()
        self.confianza = servicio_confianza or ServicioConfianza()

    async def _aplicar_efectos_post_insercion(
        self,
        reporte_id: UUID,
        entrada: CrearReporteEntrada,
        eval_estado: str,
        senales: list[str],
        puntaje: float | None,
        huella: str,
        usuario_id: UUID,
        instante: datetime,
        params: ParametrosDominio,
    ) -> None:
        if eval_estado == "aceptado":
            await self.politica.recalcular_par(
                self.sesion, entrada.presentacion_id, entrada.establecimiento_id, instante, params
            )
            lim_7d = instante - timedelta(days=7)
            await repositorio.corroborar_reportes_previos(
                self.sesion,
                entrada.presentacion_id,
                entrada.establecimiento_id,
                entrada.precio_cop,
                usuario_id,
                lim_7d,
            )
        elif eval_estado == "dudoso":
            await repositorio.insertar_caso_moderacion(
                self.sesion,
                tipo="reporte_dudoso",
                referencia_tabla="reporte_precio",
                referencia_id=reporte_id,
                detalle={"senales": senales, "puntaje": puntaje},
                prioridad=3,
            )
            await self.politica.recalcular_par(
                self.sesion, entrada.presentacion_id, entrada.establecimiento_id, instante, params
            )

        if "rafaga" in senales:
            await repositorio.insertar_caso_moderacion(
                self.sesion,
                tipo="rafaga",
                referencia_tabla="reporte_precio",
                referencia_id=reporte_id,
                detalle={
                    "huella_red": huella,
                    "establecimiento_id": str(entrada.establecimiento_id),
                },
                prioridad=1,
            )
            lim_raf = instante - timedelta(minutes=params.rafaga_ventana_min)
            pares = await repositorio.reclasificar_rafaga_hacia_atras(
                self.sesion, huella, entrada.establecimiento_id, lim_raf
            )
            for p_id, e_id in pares:
                await self.politica.recalcular_par(self.sesion, p_id, e_id, instante, params)

    async def registrar_reporte(
        self,
        usuario: UsuarioAutenticado,
        idempotency_key: str | None,
        entrada: CrearReporteEntrada,
        ip_cliente: str,
        ahora: datetime | None = None,
    ) -> tuple[CrearReporteRespuesta, bool]:
        instante = ahora if ahora is not None else datetime.now(UTC)
        params = await obtener_parametros_dominio(self.sesion)

        await validar_limites_usuario(
            limitador_escritura, self.confianza, self.sesion, usuario, ip_cliente, instante, params
        )
        key_uuid = validar_entrada_reporte(entrada, params, instante, idempotency_key)

        pres = await repositorio.obtener_presentacion_con_producto(
            self.sesion, entrada.presentacion_id
        )
        if not pres:
            raise NoEncontradoError("Presentacion no encontrada o inactiva.")
        if not await repositorio.verificar_establecimiento_activo(
            self.sesion, entrada.establecimiento_id
        ):
            raise NoEncontradoError("Establecimiento no encontrado o inactivo.")

        rep_previo = await repositorio.buscar_reporte_idempotente(self.sesion, usuario.id, key_uuid)
        if rep_previo:
            vis_prev = determinar_estado_visible(rep_previo["estado"])
            return (
                CrearReporteRespuesta(
                    datos=DatosReporteRespuesta(
                        id=rep_previo["id"],
                        estado_visible=vis_prev,
                        mensaje="Registrado previamente.",
                    )
                ),
                False,
            )

        ppb = calcular_precio_por_base(entrada.precio_cop, pres["cantidad_base"])
        evaluacion, huella = await self.confianza.evaluar_reporte_entrante(
            sesion=self.sesion,
            usuario=usuario,
            presentacion_id=entrada.presentacion_id,
            establecimiento_id=entrada.establecimiento_id,
            producto_id=pres["producto_id"],
            precio_cop=entrada.precio_cop,
            precio_por_base=ppb,
            tiene_foto=bool(entrada.foto_ruta),
            ip_cliente=ip_cliente,
            ahora=instante,
        )

        reporte_id = uuid4()
        datos_insert: dict[str, Any] = {
            "id": reporte_id,
            "producto_id": pres["producto_id"],
            "presentacion_id": entrada.presentacion_id,
            "establecimiento_id": entrada.establecimiento_id,
            "precio_cop": entrada.precio_cop,
            "cantidad_base": pres["cantidad_base"],
            "precio_por_base": ppb,
            "reportante_id": usuario.id,
            "observado_en": entrada.observado_en,
            "foto_ruta": entrada.foto_ruta,
            "estado": evaluacion.estado,
            "estado_original": evaluacion.estado,
            "senales": evaluacion.senales,
            "puntaje_anomalia": evaluacion.puntaje_anomalia,
            "riesgo_contexto": evaluacion.riesgo_contexto,
            "conjunto_referencia": evaluacion.conjunto_referencia,
            "huella_red": huella,
            "idempotency_key": key_uuid,
            "es_demo": False,
        }
        await repositorio.insertar_reporte_precio(self.sesion, datos_insert)

        await self._aplicar_efectos_post_insercion(
            reporte_id=reporte_id,
            entrada=entrada,
            eval_estado=evaluacion.estado,
            senales=evaluacion.senales,
            puntaje=evaluacion.puntaje_anomalia,
            huella=huella,
            usuario_id=usuario.id,
            instante=instante,
            params=params,
        )

        await self.cache.invalidar_producto(pres["producto_id"])

        vis = determinar_estado_visible(evaluacion.estado)
        msg = (
            "Gracias, tu precio quedó registrado."
            if evaluacion.estado == "aceptado"
            else "Tu precio fue recibido y está en revisión comunitaria."
        )
        return (
            CrearReporteRespuesta(
                datos=DatosReporteRespuesta(id=reporte_id, estado_visible=vis, mensaje=msg)
            ),
            True,
        )

    async def obtener_mis_reportes(
        self,
        usuario: UsuarioAutenticado,
        pagina: int = 1,
        limite: int = 20,
    ) -> MisReportesRespuesta:
        offset = max(0, (pagina - 1) * limite)
        filas, total = await repositorio.listar_mis_reportes(
            self.sesion, usuario.id, limite, offset
        )
        elementos = [
            ElementoReportePropio(
                id=f["id"],
                producto_nombre=f["producto_nombre"],
                presentacion_etiqueta=f["presentacion_etiqueta"],
                establecimiento_nombre=f["establecimiento_nombre"],
                precio_cop=f["precio_cop"],
                observado_en=f["observado_en"],
                creado_en=f["creado_en"],
                estado_visible=determinar_estado_visible(f["estado"]),
            )
            for f in filas
        ]
        return MisReportesRespuesta(datos=elementos, total=total, pagina=pagina, limite=limite)
