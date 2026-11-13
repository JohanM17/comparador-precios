"""Servicio de moderacion de catalogo, tiendas y catalogo externo."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.errores import NoEncontradoError, ValidacionError
from app.compartido.seguridad import UsuarioAutenticado
from app.compartido.texto import normalizar_texto
from app.dominio.unidades import ErrorUnidadesIncompatibles, calcular_cantidad_base
from app.modulos.moderacion.auditoria import registrar_auditoria
from app.modulos.moderacion.esquemas import (
    ConsultaCatalogoExternoRespuesta,
    EstablecimientoActualizarEntrada,
    EstablecimientoCrearEntrada,
    PresentacionActualizarEntrada,
    PresentacionCrearEntrada,
    ProductoActualizarEntrada,
    ProductoCrearEntrada,
)
from app.modulos.moderacion.repositorio_catalogo import (
    actualizar_presentacion_bd,
    actualizar_producto_bd,
    crear_presentacion_bd,
    crear_producto_bd,
    obtener_presentacion_por_id,
    obtener_producto_por_id,
)
from app.modulos.moderacion.repositorio_tiendas import (
    actualizar_establecimiento_bd,
    crear_establecimiento_bd,
    obtener_establecimiento_por_id,
)
from app.puertos.catalogo_externo import PuertoCatalogoExterno


class ServicioCatalogoModeracion:
    """Reglas de negocio para productos, presentaciones y tiendas."""

    def __init__(
        self,
        sesion: AsyncSession,
        puerto_catalogo: PuertoCatalogoExterno | None = None,
    ) -> None:
        self.sesion = sesion
        self.puerto_catalogo = puerto_catalogo

    async def crear_producto(
        self, entrada: ProductoCrearEntrada, usuario: UsuarioAutenticado
    ) -> dict[str, Any]:
        """Crea un producto y asienta registro inmutable en auditoria."""
        nombre_norm = normalizar_texto(entrada.nombre)
        prod = await crear_producto_bd(
            self.sesion,
            nombre=entrada.nombre,
            nombre_norm=nombre_norm,
            categoria_id=entrada.categoria_id,
            unidad_base=entrada.unidad_base,
            imagen_url=entrada.imagen_url,
        )
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="crear_producto",
            entidad="producto",
            entidad_id=str(prod["id"]),
            antes=None,
            despues=prod,
        )
        return prod

    async def actualizar_producto(
        self, id: UUID, entrada: ProductoActualizarEntrada, usuario: UsuarioAutenticado
    ) -> dict[str, Any]:
        """Actualiza atributos mutables de producto y audita cambios."""
        antes = await obtener_producto_por_id(self.sesion, id)
        if not antes:
            raise NoEncontradoError("El producto a modificar no existe.")

        campos = entrada.model_dump(exclude_unset=True)
        if "nombre" in campos and campos["nombre"]:
            campos["nombre_norm"] = normalizar_texto(campos["nombre"])

        despues = await actualizar_producto_bd(self.sesion, id, campos)
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="actualizar_producto",
            entidad="producto",
            entidad_id=str(id),
            antes=antes,
            despues=despues,
        )
        return despues or antes

    async def crear_presentacion(
        self, entrada: PresentacionCrearEntrada, usuario: UsuarioAutenticado
    ) -> dict[str, Any]:
        """Calcula cantidad_base con el dominio puro y crea la presentacion."""
        prod = await obtener_producto_por_id(self.sesion, entrada.producto_id)
        if not prod:
            raise NoEncontradoError("El producto asociado a la presentacion no existe.")

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
            producto_id=entrada.producto_id,
            marca=entrada.marca,
            valor_cantidad=entrada.valor_cantidad,
            unidad=entrada.unidad,
            multiplicador=entrada.multiplicador,
            cantidad_base=cant_base,
            etiqueta=etiqueta,
            etiqueta_norm=etiqueta_norm,
            codigo_barras=entrada.codigo_barras,
            fuente_catalogo=entrada.fuente_catalogo,
        )
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="crear_presentacion",
            entidad="presentacion",
            entidad_id=str(pres["id"]),
            antes=None,
            despues=pres,
        )
        return pres

    async def actualizar_presentacion(
        self, id: UUID, entrada: PresentacionActualizarEntrada, usuario: UsuarioAutenticado
    ) -> dict[str, Any]:
        """Actualiza presentacion rechazando taxativamente alterar cantidad_base."""
        if entrada.cantidad_base is not None or entrada.valor_cantidad is not None:
            raise ValidacionError(
                "No se permite modificar la cantidad base de una presentacion existente."
            )

        antes = await obtener_presentacion_por_id(self.sesion, id)
        if not antes:
            raise NoEncontradoError("La presentacion a modificar no existe.")

        campos = entrada.model_dump(exclude_unset=True, exclude={"cantidad_base", "valor_cantidad"})
        despues = await actualizar_presentacion_bd(self.sesion, id, campos)
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="actualizar_presentacion",
            entidad="presentacion",
            entidad_id=str(id),
            antes=antes,
            despues=despues,
        )
        return despues or antes

    async def crear_establecimiento(
        self, entrada: EstablecimientoCrearEntrada, usuario: UsuarioAutenticado
    ) -> dict[str, Any]:
        """Crea establecimiento con geometria PostGIS y registro de auditoria."""
        est = await crear_establecimiento_bd(
            self.sesion,
            nombre=entrada.nombre,
            tipo=entrada.tipo,
            cadena=entrada.cadena,
            direccion=entrada.direccion,
            barrio=entrada.barrio,
            municipio=entrada.municipio,
            departamento=entrada.departamento,
            lat=entrada.lat,
            lng=entrada.lng,
            activo=entrada.activo,
        )
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="crear_establecimiento",
            entidad="establecimiento",
            entidad_id=str(est["id"]),
            antes=None,
            despues=est,
        )
        return est

    async def actualizar_establecimiento(
        self, id: UUID, entrada: EstablecimientoActualizarEntrada, usuario: UsuarioAutenticado
    ) -> dict[str, Any]:
        """Actualiza atributos de establecimiento y audita cambios."""
        antes = await obtener_establecimiento_por_id(self.sesion, id)
        if not antes:
            raise NoEncontradoError("El establecimiento a modificar no existe.")

        campos = entrada.model_dump(exclude_unset=True, exclude={"lat", "lng"})
        despues = await actualizar_establecimiento_bd(
            self.sesion, id, campos, lat=entrada.lat, lng=entrada.lng
        )
        await registrar_auditoria(
            self.sesion,
            actor_id=usuario.id,
            rol=usuario.rol,
            accion="actualizar_establecimiento",
            entidad="establecimiento",
            entidad_id=str(id),
            antes=antes,
            despues=despues,
        )
        return despues or antes

    async def consultar_catalogo_externo(
        self, codigo_barras: str
    ) -> ConsultaCatalogoExternoRespuesta:
        """Invoca al puerto de catalogo externo bajo proteccion Circuit Breaker."""
        if not self.puerto_catalogo:
            return ConsultaCatalogoExternoRespuesta(encontrado=False, producto=None)

        prod_ext = await self.puerto_catalogo.consultar_por_codigo_barras(codigo_barras)
        if not prod_ext:
            return ConsultaCatalogoExternoRespuesta(encontrado=False, producto=None)

        return ConsultaCatalogoExternoRespuesta(
            encontrado=True,
            producto={
                "codigo_barras": prod_ext.codigo_barras,
                "nombre": prod_ext.nombre,
                "marca": prod_ext.marca,
                "cantidad_valor": str(prod_ext.cantidad_valor) if prod_ext.cantidad_valor else None,
                "unidad": prod_ext.unidad,
                "imagen_url": prod_ext.imagen_url,
            },
        )
