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
        caso = await repositorio_casos.obtener_caso_para_resolver_bd(self.sesion, caso_id)
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
        actualizado = await repositorio_sanciones.actualizar_estado_perfil_bd(
            self.sesion, uid, nuevo_est, hasta
        )
        if not actualizado:
            raise ConflictoError("La cuenta fue eliminada; no se puede sancionar.")

    @staticmethod
    def _referencias_disputa(caso: dict[str, Any]) -> tuple[UUID, UUID, UUID | None, int]:
        """Extrae y valida el par, el producto y el precio que vio el moderador."""
        detalle = caso.get("detalle") or {}
        if isinstance(detalle, str):
            try:
                detalle = json.loads(detalle)
            except (TypeError, ValueError) as exc:
                raise ValidacionError("El detalle del caso de disputa no es JSON valido.") from exc
        if not isinstance(detalle, dict):
            raise ValidacionError("El detalle del caso de disputa no tiene el formato esperado.")

        pres_raw = caso.get("referencia_id") or detalle.get("presentacion_id")
        est_raw = detalle.get("establecimiento_id")
        precio_raw = detalle.get("precio_oficial_cop")
        if not pres_raw or not est_raw or precio_raw is None:
            raise ValidacionError(
                "El caso de disputa no tiene las referencias o el precio oficial esperado."
            )

        if isinstance(precio_raw, bool) or (
            isinstance(precio_raw, float) and not precio_raw.is_integer()
        ):
            raise ValidacionError("El precio oficial esperado del caso no es un entero valido.")
        try:
            pres_id = UUID(str(pres_raw))
            est_id = UUID(str(est_raw))
            prod_id = UUID(str(detalle["producto_id"])) if detalle.get("producto_id") else None
            precio_esperado = int(precio_raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidacionError("El caso de disputa tiene referencias malformadas.") from exc

        if precio_esperado <= 0:
            raise ValidacionError("El precio oficial esperado del caso no es valido.")
        detalle_pres_raw = detalle.get("presentacion_id")
        if detalle_pres_raw:
            try:
                detalle_pres_id = UUID(str(detalle_pres_raw))
            except (TypeError, ValueError) as exc:
                raise ValidacionError(
                    "La presentacion del detalle del caso esta malformada."
                ) from exc
            if caso.get("referencia_id") and detalle_pres_id != pres_id:
                raise ValidacionError(
                    "La presentacion del detalle no coincide con la referencia del caso."
                )

        return pres_id, est_id, prod_id, precio_esperado

    @staticmethod
    def _detalle_disputa_refrescado(
        caso: dict[str, Any],
        precio_actual: int,
        ahora: datetime,
    ) -> dict[str, Any]:
        """Copia el detalle y actualiza solo la version del precio oficial."""
        detalle = caso.get("detalle") or {}
        if isinstance(detalle, str):
            detalle = json.loads(detalle)
        actualizado = dict(detalle)
        anterior = actualizado.get("precio_oficial_cop")
        actualizado["precio_oficial_cop"] = precio_actual
        actualizado["precio_oficial_anterior_cop"] = anterior
        actualizado["detalle_actualizado_en"] = ahora.isoformat()
        return actualizado

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

        Si el comercio cambio el precio, se refresca el detalle y se responde 409 una
        sola vez para que el moderador reintente con el valor actual. Si el oficial ya
        no esta activo, `descartar` cierra el caso con la comunidad; `confirmar` no
        tiene nada que confirmar y sugiere descartar.

        No se modifican filas historicas. Si mas adelante vuelve a haber una
        contradiccion, se abrira un caso nuevo (el anterior ya esta resuelto).
        """
        if entrada.decision == "sancionar":
            raise ValidacionError(
                "La decision 'sancionar' no aplica a una disputa de precio: "
                "no hay un unico reporte que sancionar. Use 'confirmar' o 'descartar'."
            )

        pres_id, est_id, prod_id, precio_esperado = self._referencias_disputa(caso)
        oficial = await repositorio_casos.obtener_precio_oficial_para_resolver_bd(
            self.sesion, pres_id, est_id
        )
        producto_id: UUID | None
        mensaje_carrera = (
            "El precio oficial cambio mientras se resolvia el caso; vuelva a abrir el caso."
        )

        if oficial is not None and int(oficial["precio_cop"]) != precio_esperado:
            precio_actual = int(oficial["precio_cop"])
            detalle = self._detalle_disputa_refrescado(caso, precio_actual, ahora)
            await repositorio_casos.actualizar_detalle_disputa_bd(self.sesion, caso["id"], detalle)
            await registrar_auditoria(
                self.sesion,
                mod.id,
                mod.rol,
                "refrescar_detalle_disputa",
                "caso_moderacion",
                str(caso["id"]),
                {"precio_oficial_cop": precio_esperado},
                {
                    "precio_oficial_cop": precio_actual,
                    "precio_oficial_anterior_cop": precio_esperado,
                    "detalle_actualizado_en": detalle["detalle_actualizado_en"],
                },
            )
            # El 409 viaja como excepcion. Sin commit explicito, el cierre de la
            # transaccion desharia el refresco y la auditoria antes de responder.
            await self.sesion.commit()
            raise ConflictoError(
                "El precio oficial cambio desde que se abrio el caso. "
                "El detalle se actualizo; recargue el caso y vuelva a decidir."
            )

        if entrada.decision == "confirmar":
            if oficial is None:
                raise ConflictoError(
                    "Ya no hay un precio oficial activo que confirmar. "
                    "Use 'descartar' si la comunidad debe ganar el caso."
                )
            confirmado = await repositorio_casos.confirmar_disputa_precio_bd(
                self.sesion, pres_id, est_id, ahora, precio_esperado
            )
            if confirmado is None:
                raise ConflictoError(mensaje_carrera)
            producto_id = confirmado or prod_id
            precio_ganador = "oficial"
        elif entrada.decision == "descartar":
            if oficial is None:
                # La comunidad ya gano: no hay nada que apagar ni refrescar.
                producto_id = prod_id
            else:
                desactivado = await repositorio_casos.desactivar_precio_oficial_bd(
                    self.sesion, pres_id, est_id, precio_esperado
                )
                if desactivado is None:
                    raise ConflictoError(mensaje_carrera)
                producto_id = desactivado or prod_id
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
