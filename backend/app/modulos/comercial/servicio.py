"""Servicio de aplicacion del modulo comercial (Etapa 2, tareas T-62, T-63 y T-65)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.auditoria import registrar_auditoria
from app.compartido.errores import (
    ConflictoError,
    NoEncontradoError,
    ProhibidoError,
    ValidacionError,
)
from app.compartido.parametros import obtener_parametros_dominio
from app.compartido.seguridad import UsuarioAutenticado
from app.dominio.precio_oficial import requiere_historial_oficial
from app.dominio.promocion import ReglaPromocion, esta_vigente, validar_promocion
from app.dominio.unidades import calcular_precio_por_base
from app.modulos.comercial import repositorio
from app.modulos.comercial.esquemas import (
    PrecioRechazado,
    PreciosLoteEntrada,
    PromocionEntrada,
    ReclamoComercioEntrada,
    VerificarComercioEntrada,
)
from app.puertos.cache import PuertoCache
from app.puertos.politica_precio import OficialConContraste, PoliticaPrecioReferencia


class ServicioComercial:
    """Reclamo de titularidad, precios oficiales y promociones de un comercio verificado."""

    def __init__(
        self,
        sesion: AsyncSession,
        puerto_cache: PuertoCache,
        politica_precio: PoliticaPrecioReferencia | None = None,
    ) -> None:
        self.sesion = sesion
        self.cache = puerto_cache
        # En Etapa 2 el precio vigente se resuelve contrastando comercio y comunidad (D-01).
        self.politica = politica_precio if politica_precio is not None else OficialConContraste()

    async def _establecimiento_propio(
        self,
        establecimiento_id: UUID,
        usuario: UsuarioAutenticado,
    ) -> dict[str, Any]:
        """Devuelve el establecimiento solo si el usuario es su dueno verificado (FR-022)."""
        est = await repositorio.obtener_establecimiento(self.sesion, establecimiento_id)
        if est is None or not est["activo"]:
            raise NoEncontradoError("El establecimiento no existe.")
        if est["comercio_id"] != usuario.id:
            # Se responde 404 y no 403 para no revelar quien es dueno de que.
            raise NoEncontradoError("El establecimiento no existe.")
        if est["estado_verificacion"] != "verificado":
            raise ProhibidoError("El establecimiento aun no esta verificado.")
        return est

    async def reclamar_titularidad(
        self,
        entrada: ReclamoComercioEntrada,
        usuario: UsuarioAutenticado,
    ) -> dict[str, Any]:
        """Registra el reclamo de un establecimiento para que lo revise un moderador (D-09)."""
        est = await repositorio.obtener_establecimiento(self.sesion, entrada.establecimiento_id)
        if est is None or not est["activo"]:
            raise NoEncontradoError("El establecimiento no existe.")
        if est["comercio_id"] is not None:
            raise ConflictoError("El establecimiento ya tiene un dueno verificado.")
        if await repositorio.existe_reclamo_abierto(self.sesion, entrada.establecimiento_id):
            raise ConflictoError("Ya hay un reclamo en revision para este establecimiento.")

        reclamo = await repositorio.crear_reclamo(
            self.sesion,
            usuario.id,
            entrada.establecimiento_id,
            entrada.telefono_contacto,
            entrada.mensaje,
        )
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="comercio.reclamar",
            entidad="solicitud_verificacion_comercio",
            entidad_id=str(reclamo["id"]),
            antes=None,
            despues={"establecimiento_id": str(entrada.establecimiento_id)},
        )
        return reclamo

    async def listar_solicitudes_pendientes(
        self,
        usuario: UsuarioAutenticado,
        limite: int = 50,
    ) -> list[dict[str, Any]]:
        """Cola de reclamos sin resolver. Solo la consume un moderador.

        Sin esta lista un reclamo seria un callejon sin salida: se registra y
        nadie puede verlo para resolverlo.
        """
        del usuario  # El rol ya lo exige la ruta; aqui no se decide permiso.
        return await repositorio.listar_solicitudes_pendientes(self.sesion, limite)

    async def verificar_comercio(
        self,
        solicitud_id: UUID,
        entrada: VerificarComercioEntrada,
        moderador: UsuarioAutenticado,
    ) -> dict[str, Any]:
        """Decision humana sobre un reclamo de titularidad. Ninguna regla la automatiza."""
        solicitud = await repositorio.obtener_solicitud(self.sesion, solicitud_id)
        if solicitud is None:
            raise NoEncontradoError("La solicitud no existe.")
        if solicitud["estado"] != "pendiente":
            raise ConflictoError("La solicitud ya fue resuelta.")

        await repositorio.resolver_solicitud(
            self.sesion, solicitud_id, moderador.id, entrada.aprobar
        )
        comercio_id: UUID | None = None
        if entrada.aprobar:
            comercio_id = solicitud["usuario_id"]
            await repositorio.enlazar_comercio(
                self.sesion, solicitud["establecimiento_id"], solicitud["usuario_id"]
            )
            await repositorio.asignar_rol_comercio(self.sesion, solicitud["usuario_id"])

        await registrar_auditoria(
            self.sesion,
            actor_id=moderador.id,
            rol=moderador.rol,
            accion="comercio.verificar",
            entidad="solicitud_verificacion_comercio",
            entidad_id=str(solicitud_id),
            antes={"estado": "pendiente"},
            despues={"aprobada": entrada.aprobar, "nota": entrada.nota},
        )
        return {
            "solicitud_id": solicitud_id,
            "establecimiento_id": solicitud["establecimiento_id"],
            "estado": "verificado" if entrada.aprobar else "sin_dueno",
            "comercio_id": comercio_id,
        }

    async def listar_establecimientos(self, usuario: UsuarioAutenticado) -> list[dict[str, Any]]:
        """Establecimientos verificados del comercio autenticado."""
        params = await obtener_parametros_dominio(self.sesion)
        return await repositorio.listar_establecimientos_de_comercio(
            self.sesion, usuario.id, params.vigencia_comercio_revalidar_dias
        )

    async def _refrescar_pares(
        self,
        establecimiento_id: UUID,
        presentaciones: list[UUID],
        productos: dict[UUID, UUID],
        ahora: datetime | None = None,
    ) -> None:
        """Recalcula el precio vigente de cada par e invalida la cache del producto.

        El recalculo entra en la misma transaccion que la escritura del precio oficial, y la
        invalidacion de cache ocurre despues. Es la secuencia que EC-02 exige para que el
        precio anterior deje de mostrarse como vigente dentro del plazo.
        """
        instante = ahora if ahora is not None else datetime.now(UTC)
        params = await obtener_parametros_dominio(self.sesion)
        for presentacion_id in presentaciones:
            await self.politica.recalcular_par(
                self.sesion, presentacion_id, establecimiento_id, instante, params
            )
        for producto_id in set(productos.values()):
            await self.cache.invalidar_producto(producto_id)

    async def publicar_precios(
        self,
        establecimiento_id: UUID,
        entrada: PreciosLoteEntrada,
        usuario: UsuarioAutenticado,
    ) -> dict[str, Any]:
        """Publica un lote de precios oficiales y recalcula el precio vigente de cada par."""
        await self._establecimiento_propio(establecimiento_id, usuario)

        ids = [p.presentacion_id for p in entrada.precios]
        presentaciones = await repositorio.obtener_presentaciones(self.sesion, ids)
        precios_anteriores = await repositorio.obtener_precios_oficiales_cop(
            self.sesion, establecimiento_id, ids
        )
        instante = datetime.now(UTC)

        rechazados: list[PrecioRechazado] = []
        aplicados: list[UUID] = []
        productos: dict[UUID, UUID] = {}

        for item in entrada.precios:
            pres = presentaciones.get(item.presentacion_id)
            if pres is None:
                rechazados.append(
                    PrecioRechazado(
                        presentacion_id=item.presentacion_id,
                        motivo="La presentacion no existe o esta inactiva.",
                    )
                )
                continue

            precio_por_base = calcular_precio_por_base(item.precio_cop, pres["cantidad_base"])
            await repositorio.upsert_precio_oficial(
                self.sesion,
                presentacion_id=item.presentacion_id,
                establecimiento_id=establecimiento_id,
                producto_id=pres["producto_id"],
                comercio_id=usuario.id,
                precio_cop=item.precio_cop,
                precio_por_base=precio_por_base,
            )
            if requiere_historial_oficial(
                precios_anteriores.get(item.presentacion_id), item.precio_cop
            ):
                await repositorio.insertar_reporte_oficial(
                    self.sesion,
                    presentacion_id=item.presentacion_id,
                    establecimiento_id=establecimiento_id,
                    producto_id=pres["producto_id"],
                    precio_cop=item.precio_cop,
                    cantidad_base=pres["cantidad_base"],
                    precio_por_base=precio_por_base,
                    observado_en=instante,
                )
            precios_anteriores[item.presentacion_id] = item.precio_cop
            aplicados.append(item.presentacion_id)
            productos[item.presentacion_id] = pres["producto_id"]

        await self._refrescar_pares(establecimiento_id, aplicados, productos, instante)
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="comercio.publicar_precios",
            entidad="precio_oficial",
            entidad_id=str(establecimiento_id),
            antes=None,
            despues={"actualizados": len(aplicados), "rechazados": len(rechazados)},
        )
        return {"actualizados": len(aplicados), "rechazados": rechazados}

    async def revalidar(
        self,
        establecimiento_id: UUID,
        usuario: UsuarioAutenticado,
    ) -> dict[str, Any]:
        """Accion «Todo sigue igual»: confirma los precios sin cambiar sus valores (D-06)."""
        await self._establecimiento_propio(establecimiento_id, usuario)

        cuantos, momento = await repositorio.revalidar_precios(
            self.sesion, establecimiento_id, usuario.id
        )
        if cuantos == 0:
            raise ConflictoError("No hay precios oficiales que revalidar.")

        presentaciones = await repositorio.listar_presentaciones_con_precio_oficial(
            self.sesion, establecimiento_id
        )
        mapa = await repositorio.obtener_presentaciones(self.sesion, presentaciones)
        productos = {pres_id: datos["producto_id"] for pres_id, datos in mapa.items()}
        await self._refrescar_pares(establecimiento_id, presentaciones, productos)

        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="comercio.revalidar",
            entidad="precio_oficial",
            entidad_id=str(establecimiento_id),
            antes=None,
            despues={"revalidados": cuantos},
        )
        return {"revalidados": cuantos, "revalidado_en": momento}

    @staticmethod
    def _a_regla(entrada: PromocionEntrada) -> ReglaPromocion:
        return ReglaPromocion(
            tipo=entrada.tipo,
            porcentaje_descuento=entrada.porcentaje_descuento,
            precio_especial_cop=entrada.precio_especial_cop,
            pague_x=entrada.pague_x,
            lleve_y=entrada.lleve_y,
            condiciones=entrada.condiciones,
            vigente_desde=entrada.vigente_desde,
            vigente_hasta=entrada.vigente_hasta,
            hasta_revocar=entrada.hasta_revocar,
        )

    async def crear_promocion(
        self,
        establecimiento_id: UUID,
        entrada: PromocionEntrada,
        usuario: UsuarioAutenticado,
    ) -> dict[str, Any]:
        """Publica una promocion, previa validacion del articulo 33 de la Ley 1480."""
        await self._establecimiento_propio(establecimiento_id, usuario)

        motivos = validar_promocion(self._a_regla(entrada))
        if motivos:
            raise ValidacionError(" ".join(motivos))

        fila = await repositorio.insertar_promocion(
            self.sesion,
            {
                "est_id": establecimiento_id,
                "prod_id": entrada.producto_id,
                "pres_id": entrada.presentacion_id,
                "comercio_id": usuario.id,
                "titulo": entrada.titulo,
                "tipo": entrada.tipo,
                "porcentaje": entrada.porcentaje_descuento,
                "precio_especial": entrada.precio_especial_cop,
                "pague_x": entrada.pague_x,
                "lleve_y": entrada.lleve_y,
                "condiciones": entrada.condiciones,
                "vigente_desde": entrada.vigente_desde,
                "vigente_hasta": entrada.vigente_hasta,
                "hasta_revocar": entrada.hasta_revocar,
            },
        )
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="comercio.crear_promocion",
            entidad="promocion",
            entidad_id=str(fila["id"]),
            antes=None,
            despues={"tipo": entrada.tipo, "titulo": entrada.titulo},
        )
        # La promocion no toca el precio vigente ni el orden (ADR-018 y ADR-022), pero si
        # cambia el bloque separado que la comparacion devuelve, asi que su cache caduca.
        await self.cache.invalidar_producto(entrada.producto_id)
        return self._con_vigencia(fila)

    @staticmethod
    def _con_vigencia(fila: dict[str, Any]) -> dict[str, Any]:
        """Agrega la vigencia calculada y la marca de contenido comercial (FR-025)."""
        regla = ReglaPromocion(
            tipo=fila["tipo"],
            porcentaje_descuento=fila["porcentaje_descuento"],
            precio_especial_cop=fila["precio_especial_cop"],
            pague_x=fila["pague_x"],
            lleve_y=fila["lleve_y"],
            condiciones=fila["condiciones"],
            vigente_desde=fila["vigente_desde"],
            vigente_hasta=fila["vigente_hasta"],
            hasta_revocar=fila["hasta_revocar"],
        )
        return {
            **fila,
            "vigente": bool(fila["activa"]) and esta_vigente(regla, datetime.now(UTC)),
            "es_promocion": True,
        }

    async def listar_promociones(
        self,
        establecimiento_id: UUID,
        usuario: UsuarioAutenticado,
    ) -> list[dict[str, Any]]:
        """Promociones del establecimiento, incluidas las revocadas, para el panel del comercio."""
        await self._establecimiento_propio(establecimiento_id, usuario)
        filas = await repositorio.listar_promociones_de_establecimiento(
            self.sesion, establecimiento_id, solo_activas=False
        )
        return [self._con_vigencia(f) for f in filas]

    async def revocar_promocion(
        self,
        establecimiento_id: UUID,
        promocion_id: UUID,
        usuario: UsuarioAutenticado,
    ) -> None:
        """Revoca una promocion propia. La fila queda, marcada como inactiva."""
        await self._establecimiento_propio(establecimiento_id, usuario)
        producto_id = await repositorio.revocar_promocion(self.sesion, promocion_id, usuario.id)
        if producto_id is None:
            raise NoEncontradoError("La promocion no existe o ya fue revocada.")
        await self.cache.invalidar_producto(producto_id)
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="comercio.revocar_promocion",
            entidad="promocion",
            entidad_id=str(promocion_id),
            antes={"activa": True},
            despues={"activa": False},
        )
