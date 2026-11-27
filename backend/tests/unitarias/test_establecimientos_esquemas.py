"""Pruebas del resumen de precio vigente que consume el modo rapido (T-67)."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.dominio.orden import ItemComparacion
from app.modulos.establecimientos import repositorio
from app.modulos.establecimientos.esquemas import PrecioVigenteResumen
from app.modulos.precios.servicio_comparacion import _construir_item_dto


def _datos(**cambios: object) -> dict[str, object]:
    base: dict[str, object] = {
        "presentacion_id": uuid4(),
        "producto_id": uuid4(),
        "producto_nombre": "Arroz blanco",
        "presentacion_etiqueta": "Arroz Diana 500 g",
        "precio_cop": 5000,
        "precio_oficial_cop": 4500,
        "precio_por_base": Decimal("9000.000"),
        "sello": "oficial",
        "motivo_sello": "Precio publicado por el comercio",
        "ultimo_reporte_en": datetime.now(UTC),
    }
    base.update(cambios)
    return base


def test_precio_vigente_resumen_expone_el_precio_oficial() -> None:
    """El DTO conserva el precio oficial para que el panel precargue el valor correcto."""
    resumen = PrecioVigenteResumen.model_validate(_datos())

    assert resumen.precio_cop == 5000
    assert resumen.precio_oficial_cop == 4500
    assert resumen.sello == "oficial"


def test_precio_vigente_resumen_sin_precio_oficial_es_nulo() -> None:
    """Sin precio publicado por el comercio el campo queda nulo, no en cero."""
    resumen = PrecioVigenteResumen.model_validate(
        _datos(precio_oficial_cop=None, sello="confiable")
    )

    assert resumen.precio_oficial_cop is None


def test_precio_vigente_resumen_expone_la_revalidacion() -> None:
    """D-02: la ficha publica puede avisar que el precio oficial pide revalidacion."""
    resumen = PrecioVigenteResumen.model_validate(_datos(requiere_revalidacion=True))

    assert resumen.requiere_revalidacion is True


def test_consulta_de_detalle_incluye_precio_oficial() -> None:
    """La consulta de la ficha no puede olvidar la columna que alimenta el DTO."""
    fuente = inspect.getsource(repositorio.obtener_establecimiento_por_id)

    assert "pv.precio_oficial_cop" in fuente


def test_consulta_de_detalle_incluye_la_revalidacion() -> None:
    """D-02: la consulta debe traer la columna que dispara el aviso en la ficha."""
    fuente = inspect.getsource(repositorio.obtener_establecimiento_por_id)

    assert "pv.requiere_revalidacion" in fuente


def test_construir_item_dto_copia_la_revalidacion() -> None:
    """D-02: el comparador no puede perder la columna al armar la fila publica."""
    ahora = datetime.now(UTC)
    establecimiento_id = uuid4()
    item = ItemComparacion(
        establecimiento_id=establecimiento_id,
        establecimiento_nombre="Tienda La Esquina",
        precio_cop=5000,
        precio_por_base=Decimal("5000"),
        sello="oficial",
        ultimo_reporte_en=ahora,
    )
    fila = SimpleNamespace(
        establecimiento_id=establecimiento_id,
        est_nombre="Tienda La Esquina",
        est_tipo="tienda_barrio",
        est_barrio="Centro",
        est_direccion="Cra 14 # 18-22",
        presentacion_id=uuid4(),
        pres_etiqueta="Arroz Diana 1 kg",
        pres_marca="Diana",
        pres_cantidad_base=Decimal("1000"),
        precio_oficial_cop=5000,
        requiere_revalidacion=True,
        motivo_sello="Precio oficial por revalidar: 45 días sin cambios",
        n_reportes_validos=0,
        n_fuentes=0,
        ultimo_reporte_en=ahora,
        con_foto=False,
    )

    dto = _construir_item_dto(item, fila, None, "g")

    assert dto.requiere_revalidacion is True
    assert dto.precio_oficial_cop == 5000
