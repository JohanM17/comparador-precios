"""Servicio de negocio para gestion de cuentas de usuario y derechos ARCO (Ley 1581)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.auditoria import registrar_auditoria
from app.compartido.errores import (
    AutorizacionRequeridaError,
    ConflictoError,
    NoEncontradoError,
    ValidacionError,
)
from app.compartido.seguridad import UsuarioAutenticado
from app.config import obtener_configuracion
from app.modulos.cuentas.esquemas import (
    ActualizarAliasEntrada,
    AutorizacionEntrada,
    AutorizacionRespuesta,
    EliminarCuentaRespuesta,
    PerfilUsuarioRespuesta,
    PoliticaTratamientoRespuesta,
)
from app.modulos.cuentas.repositorio import (
    actualizar_alias_bd,
    anonimizar_y_dar_de_baja_cuenta,
    crear_o_actualizar_autorizacion,
    obtener_perfil_con_autorizacion,
    verificar_alias_disponible,
)
from app.puertos.almacenamiento import PuertoAlmacenamientoFotos

VERSION_POLITICA_VIGENTE = "1.0"
FINALIDAD_DEFAULT = (
    "Consentimiento expreso e informado para el reporte colaborativo de precios, "
    "auditoría de integridad, detección de anomalías y cálculo estadístico en Armenia."
)


class ServicioCuentas:
    """Reglas de negocio y coordinacion de derechos de datos personales."""

    def __init__(
        self,
        sesion: AsyncSession,
        puerto_almacenamiento: PuertoAlmacenamientoFotos | None = None,
    ) -> None:
        self.sesion = sesion
        self.puerto_almacenamiento = puerto_almacenamiento
        self.cfg = obtener_configuracion()

    def obtener_politica_tratamiento(self) -> PoliticaTratamientoRespuesta:
        """Retorna la version vigente y texto oficial de politica de tratamiento de datos."""
        return PoliticaTratamientoRespuesta(
            version=VERSION_POLITICA_VIGENTE,
            texto_completo=(
                "En cumplimiento de la Ley Estatutaria 1581 de 2012 y el Decreto 1074 de 2015, "
                "la Plataforma de Precios de Armenia informa que los datos suministrados "
                "se usaran con fines de transparencia comunitaria y calidad de precios. "
                "Las coordenadas GPS se procesan solo en memoria y no se guardan en BD. "
                "El titular podra conocer, actualizar, rectificar y suprimir sus datos."
            ),
            finalidades=[
                "Registro de reportes colaborativos de precios en Armenia.",
                "Cálculo de reputación bayesiana comunitaria.",
                "Auditoría inmutable de integridad del catálogo.",
                "Prevención de anomalías y fraudes coordinados.",
            ],
            contacto_legal_email=self.cfg.CONTACTO_LEGAL_EMAIL,
            derechos_arco=[
                "Conocer los datos personales almacenados.",
                "Actualizar y rectificar el alias público.",
                "Revocar la autorización concedida.",
                "Suprimir la cuenta con anonimización irreversible de reportes.",
            ],
        )

    async def registrar_autorizacion(
        self,
        usuario: UsuarioAutenticado,
        entrada: AutorizacionEntrada,
    ) -> AutorizacionRespuesta:
        """Registra el consentimiento expreso y crea/actualiza el perfil del usuario."""
        if not entrada.acepta:
            raise ValidacionError(
                "Debe aceptar expresamente la política de tratamiento de datos personales."
            )

        alias_libre = await verificar_alias_disponible(self.sesion, entrada.alias, usuario.id)
        if not alias_libre:
            raise ConflictoError("El alias ya se encuentra en uso por otro usuario.")

        res = await crear_o_actualizar_autorizacion(
            self.sesion,
            usuario_id=usuario.id,
            alias=entrada.alias,
            version_politica=entrada.version_politica,
            finalidad=FINALIDAD_DEFAULT,
        )

        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="autorizar_datos_personales",
            entidad="perfil",
            entidad_id=str(usuario.id),
            antes=None,
            despues={"alias": entrada.alias, "version": entrada.version_politica},
        )

        aut = res["autorizacion"]
        return AutorizacionRespuesta(
            usuario_id=usuario.id,
            alias=res["alias"],
            version_politica=aut["version_politica"],
            aceptada_en=aut["aceptada_en"],
            mensaje="Autorización de tratamiento de datos registrada exitosamente.",
        )

    async def obtener_mi_cuenta(self, usuario: UsuarioAutenticado) -> PerfilUsuarioRespuesta:
        """Obtiene la ficha del usuario; exige consentimiento previo activo segun Ley 1581."""
        perfil = await obtener_perfil_con_autorizacion(self.sesion, usuario.id)
        if not perfil or not perfil.get("autorizacion_vigente"):
            raise AutorizacionRequeridaError(
                "Se requiere autorización previa de tratamiento de datos personales (Ley 1581)."
            )

        return PerfilUsuarioRespuesta(
            usuario_id=perfil["id"],
            alias=perfil["alias"],
            email=usuario.email,
            rol=perfil["rol"],
            estado=perfil["estado"],
            reputacion=perfil["reputacion"],
            reportes_corroborados=perfil["reportes_corroborados"],
            reportes_malos_confirmados=perfil["reportes_malos_confirmados"],
            autorizacion_vigente=perfil["autorizacion_vigente"],
            creado_en=perfil["creado_en"],
        )

    async def actualizar_mi_alias(
        self,
        usuario: UsuarioAutenticado,
        entrada: ActualizarAliasEntrada,
    ) -> PerfilUsuarioRespuesta:
        """Actualiza el alias público tras validar autorización y disponibilidad."""
        perfil = await obtener_perfil_con_autorizacion(self.sesion, usuario.id)
        if not perfil or not perfil.get("autorizacion_vigente"):
            raise AutorizacionRequeridaError(
                "Se requiere autorización previa de tratamiento de datos personales (Ley 1581)."
            )

        alias_libre = await verificar_alias_disponible(self.sesion, entrada.alias, usuario.id)
        if not alias_libre:
            raise ConflictoError("El alias ya se encuentra en uso por otro usuario.")

        antes = {"alias": perfil["alias"]}
        perfil_act = await actualizar_alias_bd(self.sesion, usuario.id, entrada.alias)

        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="actualizar_alias",
            entidad="perfil",
            entidad_id=str(usuario.id),
            antes=antes,
            despues={"alias": entrada.alias},
        )

        return PerfilUsuarioRespuesta(
            usuario_id=perfil_act["id"],
            alias=perfil_act["alias"],
            email=usuario.email,
            rol=perfil_act["rol"],
            estado=perfil_act["estado"],
            reputacion=perfil_act["reputacion"],
            reportes_corroborados=perfil_act["reportes_corroborados"],
            reportes_malos_confirmados=perfil_act["reportes_malos_confirmados"],
            autorizacion_vigente=perfil["autorizacion_vigente"],
            creado_en=perfil_act["creado_en"],
        )

    async def eliminar_mi_cuenta(self, usuario: UsuarioAutenticado) -> EliminarCuentaRespuesta:
        """Anonimiza reportes, fotos, revoca autorizaciones y marca perfil como eliminada."""
        perfil = await obtener_perfil_con_autorizacion(self.sesion, usuario.id)
        if not perfil:
            raise NoEncontradoError("La cuenta que desea eliminar no existe.")

        perfil_anon, rutas_fotos = await anonimizar_y_dar_de_baja_cuenta(self.sesion, usuario.id)

        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="eliminar_cuenta_anonimizar",
            entidad="perfil",
            entidad_id=str(usuario.id),
            antes=perfil,
            despues=perfil_anon,
        )

        if self.puerto_almacenamiento and rutas_fotos:
            try:
                await self.puerto_almacenamiento.eliminar_fotos(rutas_fotos)
            except Exception:  # noqa: S110
                pass

        return EliminarCuentaRespuesta(
            mensaje="Cuenta anonimizada y dada de baja exitosamente según Ley 1581.",
            usuario_id=usuario.id,
            estado="eliminada",
        )
