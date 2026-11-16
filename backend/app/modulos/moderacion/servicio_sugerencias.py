"""Servicio de moderacion para sugerencias de presentacion de usuarios."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.errores import (
    AutorizacionRequeridaError,
    NoEncontradoError,
    ValidacionError,
)
from app.compartido.seguridad import UsuarioAutenticado
from app.compartido.texto import normalizar_texto
from app.dominio.unidades import ErrorUnidadesIncompatibles, calcular_cantidad_base
from app.modulos.moderacion.auditoria import registrar_auditoria
from app.modulos.moderacion.esquemas import (
    AprobarSugerenciaEntrada,
    RechazarSugerenciaEntrada,
    SugerenciaPresentacionEntrada,
)
from app.modulos.moderacion.repositorio_catalogo import (
    crear_presentacion_bd,
    obtener_producto_por_id,
)
from app.modulos.moderacion.repositorio_sugerencias import (
    crear_sugerencia_presentacion_bd,
    obtener_sugerencia_por_id,
    resolver_sugerencia_bd,
    verificar_autorizacion_vigente,
)


class ServicioSugerenciasModeracion:
    """Reglas de negocio para sugerencias ciudadanas y casos de moderacion."""

    def __init__(self, sesion: AsyncSession) -> None:
        self.sesion = sesion

    async def registrar_sugerencia_presentacion(
        self, entrada: SugerenciaPresentacionEntrada, usuario: UsuarioAutenticado
    ) -> dict[str, Any]:
        """Registra sugerencia previa validacion de autorizacion Ley 1581."""
        autorizado = await verificar_autorizacion_vigente(self.sesion, usuario.id)
        if not autorizado:
            raise AutorizacionRequeridaError(
                "Se requiere autorizacion previa de tratamiento de datos personales (Ley 1581)."
            )

        prod = await obtener_producto_por_id(self.sesion, entrada.producto_id)
        if not prod:
            raise NoEncontradoError("El producto al que sugiere presentacion no existe.")

        sug_id, caso_id = await crear_sugerencia_presentacion_bd(
            self.sesion,
            usuario_id=usuario.id,
            producto_id=entrada.producto_id,
            texto_libre=entrada.texto_libre,
            marca=entrada.marca,
            valor_cantidad=entrada.valor_cantidad,
            unidad=entrada.unidad,
            codigo_barras=entrada.codigo_barras,
        )
        return {
            "id": sug_id,
            "caso_id": caso_id,
            "estado": "pendiente",
            "mensaje": "Sugerencia de presentacion recibida y caso abierto para moderacion.",
        }

    async def aprobar_sugerencia(
        self, id: UUID, entrada: AprobarSugerenciaEntrada, usuario: UsuarioAutenticado
    ) -> dict[str, Any]:
        """Aprueba la sugerencia, crea la presentacion oficial y audita la accion."""
        sug = await obtener_sugerencia_por_id(self.sesion, id)
        if not sug or sug["estado"] != "pendiente":
            raise NoEncontradoError("La sugerencia no existe o ya ha sido resuelta.")

        prod = await obtener_producto_por_id(self.sesion, sug["producto_id"])
        if not prod:
            raise NoEncontradoError("El producto asociado a la sugerencia no existe.")

        try:
            cant_base = calcular_cantidad_base(
                valor_cantidad=entrada.valor_cantidad,
                unidad=entrada.unidad,
                unidad_base=prod["unidad_base"],
                multiplicador=entrada.multiplicador,
            )
        except ErrorUnidadesIncompatibles as exc:
            raise ValidacionError(str(exc)) from exc
        nom_prod = prod["nombre"]
        marca_txt = entrada.marca or ""
        etiqueta = f"{nom_prod} {marca_txt} {entrada.valor_cantidad}{entrada.unidad}".strip()
        etiqueta_norm = normalizar_texto(etiqueta)

        pres = await crear_presentacion_bd(
            self.sesion,
            producto_id=sug["producto_id"],
            marca=entrada.marca,
            valor_cantidad=entrada.valor_cantidad,
            unidad=entrada.unidad,
            multiplicador=entrada.multiplicador,
            cantidad_base=cant_base,
            etiqueta=etiqueta,
            etiqueta_norm=etiqueta_norm,
            codigo_barras=entrada.codigo_barras or sug.get("codigo_barras"),
            fuente_catalogo="manual",
        )
        await resolver_sugerencia_bd(self.sesion, id, "aprobada", usuario.id, "confirmar")
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="aprobar_sugerencia_presentacion",
            entidad="sugerencia_presentacion",
            entidad_id=str(id),
            antes=sug,
            despues={"estado": "aprobada", "presentacion_id": str(pres["id"])},
        )
        return {"sugerencia_id": id, "presentacion_id": pres["id"], "estado": "aprobada"}

    async def rechazar_sugerencia(
        self, id: UUID, entrada: RechazarSugerenciaEntrada, usuario: UsuarioAutenticado
    ) -> dict[str, Any]:
        """Rechaza la sugerencia, actualiza el caso de moderacion y audita."""
        sug = await obtener_sugerencia_por_id(self.sesion, id)
        if not sug or sug["estado"] != "pendiente":
            raise NoEncontradoError("La sugerencia no existe o ya ha sido resuelta.")

        await resolver_sugerencia_bd(
            self.sesion, id, "rechazada", usuario.id, "descartar", nota=entrada.motivo
        )
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="rechazar_sugerencia_presentacion",
            entidad="sugerencia_presentacion",
            entidad_id=str(id),
            antes=sug,
            despues={"estado": "rechazada", "motivo": entrada.motivo},
        )
        return {"sugerencia_id": id, "estado": "rechazada"}
