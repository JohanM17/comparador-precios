"""Servicio de negocio para directorio de establecimientos y moderacion."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.errores import NoEncontradoError
from app.compartido.limites import LimitadorVentanaDeslizante
from app.modulos.establecimientos.esquemas import (
    EstablecimientoDetalleRespuesta,
    EstablecimientoResumen,
    ListaEstablecimientosRespuesta,
    PrecioVigenteResumen,
    SolicitudCorreccionEntrada,
    SolicitudCorreccionRespuesta,
)
from app.modulos.establecimientos.repositorio import (
    listar_establecimientos,
    obtener_establecimiento_por_id,
    registrar_solicitud_correccion,
)

# Limitador de tasa compartido en memoria para prevencion de abuso
limitador_correcciones = LimitadorVentanaDeslizante()


class ServicioEstablecimientos:
    """Coordina busquedas espaciales y recepcion de solicitudes de correccion."""

    def __init__(self, sesion: AsyncSession) -> None:
        self.sesion = sesion

    async def listar(
        self,
        termino: str | None,
        tipo: str | None,
        municipio: str | None,
        lat: float | None,
        lng: float | None,
        radio_km: float = 10.0,
        limite: int = 50,
    ) -> ListaEstablecimientosRespuesta:
        """Obtiene la lista de tiendas filtradas y opcionalmente ordenadas por cercania."""
        filas, total = await listar_establecimientos(
            self.sesion,
            termino=termino,
            tipo=tipo,
            municipio=municipio,
            lat=lat,
            lng=lng,
            radio_km=radio_km,
            limite=limite,
        )
        datos = [EstablecimientoResumen.model_validate(f) for f in filas]
        return ListaEstablecimientosRespuesta(datos=datos, total=total)

    async def obtener_por_id(
        self,
        establecimiento_id: UUID,
        lat: float | None = None,
        lng: float | None = None,
    ) -> EstablecimientoDetalleRespuesta:
        """Retorna la ficha de un establecimiento con sus precios vigentes."""
        est = await obtener_establecimiento_por_id(
            self.sesion, establecimiento_id, lat=lat, lng=lng
        )
        if not est:
            raise NoEncontradoError("El establecimiento solicitado no existe o esta inactivo.")

        precios = [PrecioVigenteResumen.model_validate(p) for p in est.get("precios_vigentes", [])]
        return EstablecimientoDetalleRespuesta(
            id=est["id"],
            nombre=est["nombre"],
            tipo=est["tipo"],
            cadena=est.get("cadena"),
            direccion=est["direccion"],
            barrio=est.get("barrio"),
            municipio=est["municipio"],
            departamento=est["departamento"],
            lat=est["lat"],
            lng=est["lng"],
            distancia_m=est.get("distancia_m"),
            estado_verificacion=est["estado_verificacion"],
            activo=est["activo"],
            precios_vigentes=precios,
        )

    async def procesar_solicitud_correccion(
        self,
        establecimiento_id: UUID,
        entrada: SolicitudCorreccionEntrada,
        ip_cliente: str,
    ) -> SolicitudCorreccionRespuesta:
        """Procesa una solicitud de correccion aplicando filtro honeypot y cuota por IP."""
        # Filtro honeypot: Si el campo trampa tiene valor, simulamos exito sin persistir
        if entrada.sitio_web_trampa:
            return SolicitudCorreccionRespuesta(
                id=None,
                estado="recibido",
                mensaje="Solicitud de correccion recibida exitosamente.",
            )

        # Aplicacion de limite de tasa (10 solicitudes al dia por IP)
        limitador_correcciones.exigir_limite(
            f"correccion_tienda:{ip_cliente}",
            max_solicitudes=10,
            ventana_segundos=86400,
            detalle="Ha superado el limite maximo de solicitudes de correccion por dia.",
        )

        # Verificacion de existencia del establecimiento
        existe = await obtener_establecimiento_por_id(self.sesion, establecimiento_id)
        if not existe:
            raise NoEncontradoError("El establecimiento a corregir no existe.")

        caso_id = await registrar_solicitud_correccion(
            self.sesion,
            establecimiento_id=establecimiento_id,
            correo=entrada.correo,
            mensaje=entrada.mensaje,
        )

        return SolicitudCorreccionRespuesta(
            id=caso_id,
            estado="abierto",
            mensaje="Solicitud de correccion recibida exitosamente.",
        )
