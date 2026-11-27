"""Servicio de aplicacion para sanciones de usuarios, apelaciones y auditoria (T-33)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.auditoria import registrar_auditoria
from app.compartido.errores import (
    ConflictoError,
    NoAutenticadoError,
    NoEncontradoError,
    ProhibidoError,
)
from app.compartido.seguridad import UsuarioAutenticado
from app.modulos.moderacion import repositorio_auditoria, repositorio_casos, repositorio_sanciones
from app.modulos.moderacion.esquemas_casos import (
    ApelacionSancionEntrada,
    ListaAuditoriaRespuesta,
    ResolverApelacionEntrada,
    SancionDirectaEntrada,
    UsuarioModeracionRespuesta,
)


class ServicioSancionesAuditoria:
    """Orquestador de sanciones a usuarios, gestion de apelaciones y lectura de auditoria."""

    def __init__(self, sesion: AsyncSession) -> None:
        self.sesion = sesion

    async def obtener_usuario_moderacion(self, usuario_id: UUID) -> UsuarioModeracionRespuesta:
        datos = await repositorio_casos.obtener_usuario_moderacion_bd(self.sesion, usuario_id)
        if not datos:
            raise NoEncontradoError(f"Usuario {usuario_id} no encontrado")
        return UsuarioModeracionRespuesta(**datos)

    async def crear_sancion_directa(
        self, entrada: SancionDirectaEntrada, moderador: UsuarioAutenticado
    ) -> UUID:
        ahora = datetime.now(UTC)
        hasta = (
            ahora + timedelta(days=entrada.dias_suspension or 7)
            if entrada.tipo == "suspension"
            else None
        )
        sanc_id = await repositorio_sanciones.insertar_sancion_bd(
            self.sesion,
            entrada.usuario_id,
            entrada.tipo,
            entrada.motivo,
            moderador.id,
            ahora,
            hasta,
        )
        if entrada.tipo == "suspension":
            nuevo_estado = "suspendida"
        elif entrada.tipo == "bloqueo":
            nuevo_estado = "bloqueada"
        else:
            nuevo_estado = "advertencia"
        actualizado = await repositorio_sanciones.actualizar_estado_perfil_bd(
            self.sesion, entrada.usuario_id, nuevo_estado, hasta
        )
        if not actualizado:
            raise ConflictoError("La cuenta fue eliminada; no se puede sancionar.")
        await registrar_auditoria(
            self.sesion,
            actor_id=moderador.id,
            rol=moderador.rol,
            accion="crear_sancion",
            entidad="sancion",
            entidad_id=str(sanc_id),
            antes=None,
            despues={
                "usuario_id": str(entrada.usuario_id),
                "tipo": entrada.tipo,
                "motivo": entrada.motivo,
            },
        )
        await self.sesion.flush()
        return sanc_id

    async def registrar_apelacion(
        self, sancion_id: UUID, entrada: ApelacionSancionEntrada, usuario: UsuarioAutenticado
    ) -> None:
        if usuario.estado == "eliminada":
            raise NoAutenticadoError("La cuenta fue eliminada y no puede apelar sanciones.")
        sancion = await repositorio_sanciones.obtener_sancion_por_id_bd(self.sesion, sancion_id)
        if not sancion:
            raise NoEncontradoError(f"Sancion {sancion_id} no encontrada")
        if sancion["usuario_id"] != usuario.id and usuario.rol not in ("admin", "moderador"):
            raise ProhibidoError("No puedes apelar una sancion ajena")

        await repositorio_sanciones.registrar_apelacion_bd(
            self.sesion, sancion_id, entrada.apelacion
        )
        await self.sesion.flush()

    async def resolver_apelacion(
        self, sancion_id: UUID, entrada: ResolverApelacionEntrada, moderador: UsuarioAutenticado
    ) -> None:
        sancion = await repositorio_sanciones.obtener_sancion_por_id_bd(self.sesion, sancion_id)
        if not sancion:
            raise NoEncontradoError(f"Sancion {sancion_id} no encontrada")

        await repositorio_sanciones.resolver_apelacion_bd(self.sesion, sancion_id, entrada.aprobar)
        if entrada.aprobar and sancion["tipo"] in ("suspension", "bloqueo"):
            reactivada = await repositorio_sanciones.actualizar_estado_perfil_bd(
                self.sesion, sancion["usuario_id"], "activa", None
            )
            if not reactivada:
                raise ConflictoError("La cuenta fue eliminada; la apelacion no puede reactivarla.")

        await registrar_auditoria(
            self.sesion,
            actor_id=moderador.id,
            rol=moderador.rol,
            accion="resolver_apelacion",
            entidad="sancion",
            entidad_id=str(sancion_id),
            antes={"apelacion_resuelta": sancion.get("apelacion_resuelta")},
            despues={"aprobada": entrada.aprobar, "nota": entrada.nota},
        )
        await self.sesion.flush()

    async def listar_auditoria(
        self,
        entidad: str | None = None,
        accion: str | None = None,
        actor_id: UUID | None = None,
        limite: int = 50,
        offset: int = 0,
    ) -> ListaAuditoriaRespuesta:
        filas, total = await repositorio_auditoria.listar_auditoria_bd(
            self.sesion, entidad, accion, actor_id, limite, offset
        )
        return ListaAuditoriaRespuesta(datos=filas, total=total)  # type: ignore[arg-type]
