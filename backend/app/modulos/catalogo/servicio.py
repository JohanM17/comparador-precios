"""Servicio de catalogo para busqueda difusa y normalizacion de unidades."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.errores import NoEncontradoError
from app.compartido.texto import normalizar_texto
from app.dominio.unidades import (
    calcular_precio_visualizacion,
    parsear_cantidad,
)
from app.modulos.catalogo.esquemas import (
    CategoriaRespuesta,
    ListaProductosRespuesta,
    PresentacionResumen,
    ProductoDetalleRespuesta,
    ProductoResumen,
)
from app.modulos.catalogo.repositorio import (
    buscar_productos,
    listar_categorias,
    obtener_producto_por_id,
)

UNIDADES_VISUALIZACION = {
    "g": "kg",
    "ml": "l",
    "unidad": "unidad",
}


def resolver_unidad_visualizacion(unidad_base: str) -> str:
    """Retorna la unidad estandar de comparacion para el usuario."""
    return UNIDADES_VISUALIZACION.get(unidad_base, unidad_base)


def _extraer_termino_y_cantidad(texto_crudo: str) -> tuple[str | None, Decimal | None]:
    """Separa la expresion de cantidad del termino textual de busqueda."""
    palabras = texto_crudo.split()
    for tam in (2, 1):
        for i in range(len(palabras) - tam + 1):
            sub_frase = " ".join(palabras[i : i + tam])
            cant = parsear_cantidad(sub_frase)
            if cant is not None:
                restantes = palabras[:i] + palabras[i + tam :]
                termino_aislado = " ".join(restantes).strip()
                termino_limpio = normalizar_texto(termino_aislado) if termino_aislado else None
                return termino_limpio, cant.cantidad_base

    return normalizar_texto(texto_crudo), None


def _mapear_producto_resumen(p: dict[str, Any]) -> ProductoResumen:
    """Transforma una fila cruda de base de datos a ProductoResumen."""
    ub = p["unidad_base"]
    uv = resolver_unidad_visualizacion(ub)
    precio_desde: int | None = None
    if p.get("min_precio_base") is not None:
        precio_valor, _ = calcular_precio_visualizacion(Decimal(str(p["min_precio_base"])), ub)
        precio_desde = precio_valor

    presentaciones = [PresentacionResumen.model_validate(pr) for pr in p.get("presentaciones", [])]
    return ProductoResumen(
        id=p["id"],
        nombre=p["nombre"],
        categoria_id=p["categoria_id"],
        unidad_base=ub,
        unidad_visualizacion=uv,
        imagen_url=p.get("imagen_url"),
        precio_desde_por_unidad_cop=precio_desde,
        n_tiendas_con_precio=p.get("n_tiendas_con_precio", 0),
        presentaciones=presentaciones,
    )


class ServicioCatalogo:
    """Coordina la logica de catalogo de productos y categorias."""

    def __init__(self, sesion: AsyncSession) -> None:
        self.sesion = sesion

    async def obtener_categorias(self) -> list[CategoriaRespuesta]:
        """Retorna todas las categorias activas del sistema."""
        filas = await listar_categorias(self.sesion)
        return [CategoriaRespuesta.model_validate(f) for f in filas]

    async def buscar(
        self,
        q: str | None,
        categoria_id: int | None,
        limite: int = 24,
        cursor: str | None = None,
    ) -> ListaProductosRespuesta:
        """Busca productos resolviendo terminos difusos y fracciones de cantidad."""
        offset = int(cursor) if (cursor and cursor.isdigit()) else 0

        termino_limpio: str | None = None
        cantidad_filtro: Decimal | None = None
        if q and q.strip():
            termino_limpio, cantidad_filtro = _extraer_termino_y_cantidad(q.strip())

        productos_raw, total = await buscar_productos(
            self.sesion,
            termino=termino_limpio,
            categoria_id=categoria_id,
            cantidad_filtro=cantidad_filtro,
            limite=limite,
            offset=offset,
        )

        datos = [_mapear_producto_resumen(p) for p in productos_raw]
        siguiente_offset = offset + len(datos)
        siguiente_cursor = str(siguiente_offset) if siguiente_offset < total else None

        return ListaProductosRespuesta(
            datos=datos,
            siguiente_cursor=siguiente_cursor,
            total_estimado=total,
        )

    async def obtener_por_id(self, producto_id: UUID) -> ProductoDetalleRespuesta:
        """Retorna la ficha de un producto o lanza NoEncontradoError."""
        p = await obtener_producto_por_id(self.sesion, producto_id)
        if not p:
            raise NoEncontradoError("El producto solicitado no existe o esta inactivo.")

        ub = p["unidad_base"]
        uv = resolver_unidad_visualizacion(ub)
        presentaciones = [
            PresentacionResumen.model_validate(pr) for pr in p.get("presentaciones", [])
        ]
        return ProductoDetalleRespuesta(
            id=p["id"],
            nombre=p["nombre"],
            categoria_id=p["categoria_id"],
            unidad_base=ub,
            unidad_visualizacion=uv,
            imagen_url=p.get("imagen_url"),
            activo=p["activo"],
            presentaciones=presentaciones,
        )
