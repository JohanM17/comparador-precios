"""Puerto abstracto para consultas a catalogos externos de alimentos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ProductoExterno:
    """Informacion normalizada obtenida de un proveedor externo de catalogo."""

    codigo_barras: str
    nombre: str
    marca: str | None = None
    cantidad_valor: Decimal | None = None
    unidad: str | None = None
    imagen_url: str | None = None


class PuertoCatalogoExterno(Protocol):
    """Protocolo que desacopla la logica de negocio de APIs externas."""

    async def consultar_por_codigo_barras(self, codigo_barras: str) -> ProductoExterno | None:
        """Consulta un producto por su codigo GTIN/EAN."""
        ...
