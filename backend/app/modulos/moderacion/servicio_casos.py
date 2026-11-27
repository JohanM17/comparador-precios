"""Servicio de aplicacion para la gestion de casos de moderacion (T-33)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.auditoria import registrar_auditoria
from app.compartido.errores import ConflictoError, NoEncontradoError, ValidacionError
from app.compartido.parametros import obtener_parametros_dominio
from app.compartido.seguridad import UsuarioAutenticado
from app.modulos.moderacion import repositorio_casos, repositorio_sanciones
from app.modulos.moderacion.esquemas_casos import (
    CasoDetalleRespuesta,
    ListaCasosRespuesta,
    ResolverCasoEntrada,
)
from app.puertos.cache import PuertoCache
from app.puertos.politica_precio import (
    OficialConContraste,
    PoliticaPrecioReferencia,
    listar_pares_para_recalculo,
)


class ServicioCasosModeracion:
    """Orquestador de casos de moderacion y recálculos manuales."""

    def __init__(
        self,
        sesion: AsyncSession,
        cache: PuertoCache,
        politica: PoliticaPrecioReferencia | None = None,
    ) -> None:
        self.sesion = sesion
        self.cache = cache
        # Etapa 2: un recalculo manual debe respetar el contraste oficial/comunidad (D-01).
        self.politica = politica if politica is not None else OficialConContraste()

    async def listar_casos(
        self,
        estado: str | None = None,
        tipo: str | None = None,
        prioridad: int | None = None,
        limite: int = 20,
        offset: int = 0,
    ) -> ListaCasosRespuesta:
        filas, total = await repositorio_casos.listar_casos_bd(
            self.sesion, estado, tipo, prioridad, limite, offset
        )
        return ListaCasosRespuesta(datos=[CasoDetalleRespuesta(**f) for f in filas], total=total)

    async def obtener_caso(self, caso_id: UUID) -> CasoDetalleRespuesta:
        caso = await repositorio_casos.obtener_caso_por_id_bd(self.sesion, caso_id)
        if not caso:
            raise NoEncontradoError(f"Caso de moderacion {caso_id} no encontrado")
        ref_datos = await repositorio_casos.obtener_datos_referencia_bd(
            self.sesion, caso["referencia_tabla"], caso["referencia_id"]
        )
        caso["referencia_datos"] = ref_datos
        return CasoDetalleRespuesta(**caso)

    async def resolver_caso(
        self, caso_id: UUID, entrada: ResolverCasoEntrada, moderador: UsuarioAutenticado
    ) -> CasoDetalleRespuesta:
        caso = await repositorio_casos.obtener_caso_por_id_bd(self.sesion, caso_id)
        if not caso:
            raise NoEncontradoError(f"Caso {caso_id} no encontrado")
        if caso["estado"] == "resuelto":
            raise ConflictoError("El caso ya se encuentra resuelto")

        ahora = datetime.now(UTC)
        params = await obtener_parametros_dominio(self.sesion)

        # D-01: una disputa de precio no cuelga de un reporte concreto. El caso guarda
        # el par y los dos precios en `detalle`, asi que se resuelve antes del flujo
        # generico de `reporte_precio`.
        if caso["tipo"] == "disputa_precio":
            await self._resolver_disputa_precio(caso, entrada, moderador, ahora, params)
            await self.sesion.flush()
            return await self.obtener_caso(caso_id)

        rep = await repositorio_casos.obtener_datos_referencia_bd(
            self.sesion, caso["referencia_tabla"], caso["referencia_id"]
        )

        if entrada.decision == "descartar":
            await self._descartar(caso, rep, moderador, entrada.nota, ahora, params)
        elif entrada.decision == "confirmar":
            await self._confirmar(caso, rep, moderador, entrada.nota, ahora, params)
        elif entrada.decision == "sancionar":
            await self._sancionar(caso, rep, entrada, moderador, ahora, params)

        await self.sesion.flush()
        return await self.obtener_caso(caso_id)

    async def _descartar(
        self,
        caso: dict[str, Any],
        rep: dict[str, Any] | None,
        mod: UsuarioAutenticado,
        nota: str,
        ahora: datetime,
        params: Any,
    ) -> None:
        if rep:
            await repositorio_casos.actualizar_estado_reporte_bd(
                self.sesion, rep["id"], "aceptado", mod.id, ahora
            )
            await self.politica.recalcular_par(
                self.sesion, rep["presentacion_id"], rep["establecimiento_id"], ahora, params
            )
            await self.cache.invalidar_producto(rep["producto_id"])

        await repositorio_casos.actualizar_caso_resuelto_bd(
            self.sesion, caso["id"], "descartar", nota, mod.id, ahora
        )
        await registrar_auditoria(
            self.sesion,
            mod.id,
            mod.rol,
            "resolver_caso_descartar",
            "caso_moderacion",
            str(caso["id"]),
            {"estado": caso["estado"]},
            {"estado": "resuelto", "decision": "descartar", "nota": nota},
        )

    async def _confirmar(
        self,
        caso: dict[str, Any],
        rep: dict[str, Any] | None,
        mod: UsuarioAutenticado,
        nota: str,
        ahora: datetime,
        params: Any,
    ) -> None:
        if rep:
            await repositorio_casos.actualizar_estado_reporte_bd(
                self.sesion, rep["id"], "rechazado", mod.id, ahora
            )
            if rep.get("reportante_id"):
                await repositorio_casos.penalizar_reputacion_autor_bd(
                    self.sesion, rep["reportante_id"]
                )
            await self.politica.recalcular_par(
                self.sesion, rep["presentacion_id"], rep["establecimiento_id"], ahora, params
            )
            await self.cache.invalidar_producto(rep["producto_id"])

        await repositorio_casos.actualizar_caso_resuelto_bd(
            self.sesion, caso["id"], "confirmar", nota, mod.id, ahora
        )
        await registrar_auditoria(
            self.sesion,
            mod.id,
            mod.rol,
            "resolver_caso_confirmar",
            "caso_moderacion",
            str(caso["id"]),
            {"estado": caso["estado"]},
            {"estado": "resuelto", "decision": "confirmar", "nota": nota},
        )

    async def _sancionar(
        self,
        caso: dict[str, Any],
        rep: dict[str, Any] | None,
        entrada: ResolverCasoEntrada,
        mod: UsuarioAutenticado,
        ahora: datetime,
        params: Any,
    ) -> None:
        if not entrada.sancion:
            raise ValidacionError("Debe incluir datos de sancion para resolver como 'sancionar'")
        await self._confirmar(caso, rep, mod, entrada.nota, ahora, params)
        uid = rep["reportante_id"] if rep and rep.get("reportante_id") else None
        if not uid:
            raise ValidacionError("No se pudo identificar el usuario a sancionar desde el caso")
        sanc = entrada.sancion
        hasta = (
            ahora + timedelta(days=sanc.dias_suspension or 7) if sanc.tipo == "suspension" else None
        )
        await repositorio_sanciones.insertar_sancion_bd(
            self.sesion, uid, sanc.tipo, sanc.motivo, mod.id, ahora, hasta
        )
        if sanc.tipo == "suspension":
            nuevo_est = "suspendida"
        elif sanc.tipo == "bloqueo":
            nuevo_est = "bloqueada"
        else:
            nuevo_est = "advertencia"
        await repositorio_sanciones.actualizar_estado_perfil_bd(self.sesion, uid, nuevo_est, hasta)

    @staticmethod
    def _referencias_disputa(caso: dict[str, Any]) -> tuple[UUID, UUID, UUID | None]:
        """Extrae el par y el producto del `detalle` guardado al abrir el caso."""
        detalle = caso.get("detalle") or {}
        if isinstance(detalle, str):
            detalle = json.loads(detalle)

        pres_raw = caso.get("referencia_id") or detalle.get("presentacion_id")
        est_raw = detalle.get("establecimiento_id")
        if not pres_raw or not est_raw:
            raise ValidacionError("El caso de disputa no tiene las referencias del par.")
        prod_raw = detalle.get("producto_id")
        return (
            UUID(str(pres_raw)),
            UUID(str(est_raw)),
            UUID(str(prod_raw)) if prod_raw else None,
        )

    async def _resolver_disputa_precio(
        self,
        caso: dict[str, Any],
        entrada: ResolverCasoEntrada,
        mod: UsuarioAutenticado,
        ahora: datetime,
        params: Any,
    ) -> None:
        """Resuelve una disputa D-01 entre el precio oficial y la comunidad.

        - `confirmar`: gana el comercio; se revalida el oficial y se fija la proyeccion.
        - `descartar`: gana la comunidad; se apaga el oficial y se recalcula sin el.
        - `sancionar`: no aplica, porque no hay un unico reporte que sancionar.

        No se modifican filas historicas. Si mas adelante vuelve a haber una
        contradiccion, se abrira un caso nuevo (el anterior ya esta resuelto).
        """
        if entrada.decision == "sancionar":
            raise ValidacionError(
                "La decision 'sancionar' no aplica a una disputa de precio: "
                "no hay un unico reporte que sancionar. Use 'confirmar' o 'descartar'."
            )

        pres_id, est_id, prod_id = self._referencias_disputa(caso)
        producto_id: UUID | None

        if entrada.decision == "confirmar":
            producto_id = (
                await repositorio_casos.confirmar_disputa_precio_bd(
                    self.sesion, pres_id, est_id, ahora
                )
                or prod_id
            )
            precio_ganador = "oficial"
        elif entrada.decision == "descartar":
            producto_id = (
                await repositorio_casos.desactivar_precio_oficial_bd(self.sesion, pres_id, est_id)
                or prod_id
            )
            await self.politica.recalcular_par(self.sesion, pres_id, est_id, ahora, params)
            precio_ganador = "comunidad"
        else:  # pragma: no cover - Literal de Pydantic ya limita las decisiones
            raise ValidacionError(f"Decision de disputa no soportada: {entrada.decision}")

        if producto_id is not None:
            await self.cache.invalidar_producto(producto_id)

        await repositorio_casos.actualizar_caso_resuelto_bd(
            self.sesion, caso["id"], entrada.decision, entrada.nota, mod.id, ahora
        )
        await registrar_auditoria(
            self.sesion,
            mod.id,
            mod.rol,
            f"resolver_caso_{entrada.decision}",
            "caso_moderacion",
            str(caso["id"]),
            {"estado": caso["estado"], "tipo": caso["tipo"]},
            {
                "estado": "resuelto",
                "decision": entrada.decision,
                "nota": entrada.nota,
                "tipo": "disputa_precio",
                "precio_ganador": precio_ganador,
                "presentacion_id": str(pres_id),
                "establecimiento_id": str(est_id),
            },
        )

    async def recalcular_precio_vigente_manual(
        self, _mod: UsuarioAutenticado, pres_id: UUID | None = None, est_id: UUID | None = None
    ) -> dict[str, Any]:
        ahora = datetime.now(UTC)
        params = await obtener_parametros_dominio(self.sesion)
        if pres_id and est_id:
            res = await self.politica.recalcular_par(self.sesion, pres_id, est_id, ahora, params)
            await self.cache.limpiar()
            await self.sesion.flush()
            return {"recalculados": 1, "sello": res.sello if res else None}
        limite = ahora - timedelta(days=params.vigencia_antiguo_dias)
        pares = await listar_pares_para_recalculo(self.sesion, limite)
        recalculados = 0
        for p_id, e_id in pares:
            res = await self.politica.recalcular_par(self.sesion, p_id, e_id, ahora, params)
            if res is not None:
                recalculados += 1
        await self.cache.limpiar()
        await self.sesion.flush()
        return {"recalculados": recalculados}
