"""Pruebas unitarias TDD en rojo de la serie historica de precios (Tarea T-110).

Estas pruebas describen el contrato del modulo puro ``app.dominio.serie_precios``.
La implementacion corresponde a la tarea T-111, por lo que en esta fase deben
fallar por ausencia del modulo.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.dominio.serie_precios import (
    PuntoSeriePrecio,
    ReporteSerie,
    ResultadoSerie,
    construir_serie,
)

# Ventana de referencia de 90 dias, con marcas temporales siempre en UTC.
DESDE = datetime(2026, 8, 1, 0, 0, 0, tzinfo=UTC)
HASTA = DESDE + timedelta(days=90)
MOMENTO_BASE = DESDE + timedelta(days=45)

CAMPOS_PUNTO_SERIE = {
    "id",
    "observado_en",
    "precio_cop",
    "precio_por_base",
    "precio_por_unidad",
    "unidad_visualizacion",
    "origen",
    "estado",
    "es_demo",
    "presentacion_id",
    "cantidad_base",
}

CAMPOS_PROHIBIDOS = {
    "reportante_id",
    "huella_red",
    "foto_prueba_path",
    "lat",
    "lng",
    "alias",
    "email",
    "ip",
}


def _crear_reporte(
    observado_en: datetime,
    *,
    reporte_id: UUID | None = None,
    precio_cop: int = 5000,
    cantidad_base: Decimal = Decimal("1000.000"),
    precio_por_base: Decimal = Decimal("5.000000"),
    origen: str = "usuario",
    estado: str = "aceptado",
    es_demo: bool = False,
    presentacion_id: UUID | None = None,
) -> ReporteSerie:
    """Construye un reporte de entrada con valores validos por defecto."""
    return ReporteSerie(
        id=uuid4() if reporte_id is None else reporte_id,
        observado_en=observado_en,
        precio_cop=precio_cop,
        cantidad_base=cantidad_base,
        precio_por_base=precio_por_base,
        origen=origen,
        estado=estado,
        es_demo=es_demo,
        presentacion_id=presentacion_id,
    )


# 1. Serie vacia


def test_serie_vacia_devuelve_puntos_vacios_y_sin_banderas() -> None:
    """Sin reportes, la serie es una tupla vacia y no esta truncada ni es demo."""
    resultado = construir_serie([], desde=DESDE, hasta=HASTA, unidad_base="g", limite=10)

    assert isinstance(resultado, ResultadoSerie)
    assert isinstance(resultado.puntos, tuple)
    assert resultado.puntos == ()
    assert resultado.truncado is False
    assert resultado.datos_de_demostracion is False


# 2. Ventana inclusiva de 90 dias


def test_ventana_inclusiva_en_los_extremos_y_excluye_un_segundo_afuera() -> None:
    """Incluye reportes exactamente en desde/hasta y excluye los de +/- 1 segundo."""
    en_desde = _crear_reporte(DESDE)
    en_hasta = _crear_reporte(HASTA)
    antes_de_desde = _crear_reporte(DESDE - timedelta(seconds=1))
    despues_de_hasta = _crear_reporte(HASTA + timedelta(seconds=1))

    resultado = construir_serie(
        [antes_de_desde, en_hasta, despues_de_hasta, en_desde],
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    assert [punto.id for punto in resultado.puntos] == [en_desde.id, en_hasta.id]
    assert resultado.truncado is False


# 3. Estados visibles


def test_incluye_aceptado_y_dudoso_y_excluye_rechazado() -> None:
    """La serie solo expone reportes aceptados o dudosos; rechazado nunca aparece."""
    aceptado = _crear_reporte(MOMENTO_BASE, estado="aceptado")
    rechazado = _crear_reporte(MOMENTO_BASE + timedelta(hours=1), estado="rechazado")
    dudoso = _crear_reporte(MOMENTO_BASE + timedelta(hours=2), estado="dudoso")

    resultado = construir_serie(
        [aceptado, rechazado, dudoso],
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    assert [punto.id for punto in resultado.puntos] == [aceptado.id, dudoso.id]
    assert [punto.estado for punto in resultado.puntos] == ["aceptado", "dudoso"]


# 4. Orden y desempate


def test_orden_ascendente_con_desempate_estable_por_id() -> None:
    """Ordena por observado_en y, en empate, por el texto estable del identificador."""
    momento_empate = MOMENTO_BASE + timedelta(hours=1)
    id_temprano = UUID(int=10)
    id_empate_mayor = UUID(int=3)
    id_empate_menor = UUID(int=2)

    temprano = _crear_reporte(MOMENTO_BASE, reporte_id=id_temprano)
    empate_mayor = _crear_reporte(momento_empate, reporte_id=id_empate_mayor)
    empate_menor = _crear_reporte(momento_empate, reporte_id=id_empate_menor)

    resultado = construir_serie(
        [empate_mayor, temprano, empate_menor],
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    assert [punto.id for punto in resultado.puntos] == [
        id_temprano,
        id_empate_menor,
        id_empate_mayor,
    ]
    tiempos = [punto.observado_en for punto in resultado.puntos]
    assert tiempos == sorted(tiempos)


# 5. Limite y truncado


def test_limite_conserva_los_mas_recientes_y_marca_truncado() -> None:
    """Con mas puntos que el limite, conserva los mas recientes en orden ascendente."""
    reportes = [
        _crear_reporte(
            MOMENTO_BASE - timedelta(hours=5 - indice),
            reporte_id=UUID(int=indice + 1),
            precio_cop=1000 + indice,
        )
        for indice in range(5)
    ]

    resultado = construir_serie(
        reportes,
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=3,
    )

    assert [punto.id for punto in resultado.puntos] == [
        UUID(int=3),
        UUID(int=4),
        UUID(int=5),
    ]
    assert resultado.truncado is True


@pytest.mark.parametrize("limite", [3, 10])
def test_limite_sin_exceso_no_marca_truncado(limite: int) -> None:
    """Si la cantidad de puntos no supera el limite, truncado es falso."""
    reportes = [
        _crear_reporte(
            MOMENTO_BASE + timedelta(hours=indice),
            reporte_id=UUID(int=indice + 1),
        )
        for indice in range(3)
    ]

    resultado = construir_serie(
        reportes,
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=limite,
    )

    assert len(resultado.puntos) == 3
    assert resultado.truncado is False


# 6. Datos de demostracion


def test_datos_de_demostracion_verdadero_si_algun_punto_es_demo() -> None:
    """La bandera es verdadera cuando al menos un punto devuelto es demostracion."""
    normal = _crear_reporte(MOMENTO_BASE)
    demo = _crear_reporte(MOMENTO_BASE + timedelta(days=1), es_demo=True)

    resultado = construir_serie(
        [normal, demo],
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    assert resultado.datos_de_demostracion is True


def test_datos_de_demostracion_falso_si_ningun_punto_es_demo() -> None:
    """La bandera es falsa cuando ningun punto devuelto es demostracion."""
    reportes = [
        _crear_reporte(MOMENTO_BASE),
        _crear_reporte(MOMENTO_BASE + timedelta(days=1), es_demo=False),
    ]

    resultado = construir_serie(
        reportes,
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    assert resultado.datos_de_demostracion is False


def test_datos_de_demostracion_ignora_puntos_descartados_por_el_limite() -> None:
    """Un punto demo antiguo descartado por el limite no marca la serie como demo."""
    demo_antiguo = _crear_reporte(MOMENTO_BASE, es_demo=True)
    reciente = _crear_reporte(MOMENTO_BASE + timedelta(days=1), es_demo=False)

    resultado = construir_serie(
        [demo_antiguo, reciente],
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=1,
    )

    assert [punto.id for punto in resultado.puntos] == [reciente.id]
    assert resultado.datos_de_demostracion is False


# 7. Precio por unidad y unidad de visualizacion


@pytest.mark.parametrize(
    (
        "unidad_base",
        "cantidad_base",
        "precio_cop",
        "precio_por_base",
        "precio_por_unidad_esperado",
        "unidad_visualizacion_esperada",
    ),
    [
        ("g", Decimal("500"), 2600, Decimal("5.2"), 5200, "kg"),
        ("ml", Decimal("1000"), 3000, Decimal("3.0"), 3000, "l"),
        ("unidad", Decimal("1"), 1500, Decimal("1500"), 1500, "unidad"),
    ],
    ids=["gramos", "mililitros", "unidad"],
)
def test_precio_por_unidad_y_unidad_visualizacion(
    unidad_base: str,
    cantidad_base: Decimal,
    precio_cop: int,
    precio_por_base: Decimal,
    precio_por_unidad_esperado: int,
    unidad_visualizacion_esperada: str,
) -> None:
    """Convierte el precio por base al precio legible por kg, litro o unidad."""
    reporte = _crear_reporte(
        MOMENTO_BASE,
        precio_cop=precio_cop,
        cantidad_base=cantidad_base,
        precio_por_base=precio_por_base,
    )

    resultado = construir_serie(
        [reporte],
        desde=DESDE,
        hasta=HASTA,
        unidad_base=unidad_base,
        limite=10,
    )

    punto = resultado.puntos[0]
    assert punto.precio_por_unidad == precio_por_unidad_esperado
    assert type(punto.precio_por_unidad) is int
    assert punto.unidad_visualizacion == unidad_visualizacion_esperada
    assert punto.precio_por_base == precio_por_base
    assert isinstance(punto.precio_por_base, Decimal)
    assert punto.cantidad_base == cantidad_base
    assert isinstance(punto.cantidad_base, Decimal)
    assert punto.precio_cop == precio_cop


# 8. Origen preservado


def test_origen_se_preserva_en_cada_punto() -> None:
    """Cada punto conserva el origen usuario, comercio o semilla del reporte."""
    usuario = _crear_reporte(MOMENTO_BASE, reporte_id=UUID(int=1), origen="usuario")
    comercio = _crear_reporte(
        MOMENTO_BASE + timedelta(hours=1), reporte_id=UUID(int=2), origen="comercio"
    )
    semilla = _crear_reporte(
        MOMENTO_BASE + timedelta(hours=2), reporte_id=UUID(int=3), origen="semilla"
    )

    resultado = construir_serie(
        [semilla, usuario, comercio],
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    assert {punto.id: punto.origen for punto in resultado.puntos} == {
        usuario.id: "usuario",
        comercio.id: "comercio",
        semilla.id: "semilla",
    }


def test_punto_conserva_los_datos_publicos_del_reporte() -> None:
    """El punto devuelto conserva identificador, fecha, precios, estado y presentacion."""
    presentacion_id = uuid4()
    reporte = _crear_reporte(
        MOMENTO_BASE,
        precio_cop=4200,
        cantidad_base=Decimal("750.000"),
        precio_por_base=Decimal("5.600000"),
        origen="comercio",
        estado="dudoso",
        es_demo=True,
        presentacion_id=presentacion_id,
    )

    resultado = construir_serie(
        [reporte],
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    punto = resultado.puntos[0]
    assert punto.id == reporte.id
    assert punto.observado_en == reporte.observado_en
    assert punto.precio_cop == reporte.precio_cop
    assert punto.precio_por_base == reporte.precio_por_base
    assert punto.cantidad_base == reporte.cantidad_base
    assert punto.estado == "dudoso"
    assert punto.es_demo is True
    assert punto.presentacion_id == presentacion_id


# 9. Ausencia de campos prohibidos


def test_punto_serie_expone_solo_los_campos_del_contrato() -> None:
    """PuntoSeriePrecio declara exactamente los campos publicos y ninguno prohibido."""
    nombres = {campo.name for campo in fields(PuntoSeriePrecio)}

    assert nombres == CAMPOS_PUNTO_SERIE
    assert nombres.isdisjoint(CAMPOS_PROHIBIDOS)


def test_punto_serie_no_expone_atributos_prohibidos_en_instancias() -> None:
    """Una instancia real no permite acceder a identidad, red, foto ni coordenadas."""
    reporte = _crear_reporte(MOMENTO_BASE)
    resultado = construir_serie(
        [reporte],
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    punto = resultado.puntos[0]
    for prohibido in CAMPOS_PROHIBIDOS:
        assert not hasattr(punto, prohibido)


def test_dataclasses_respetan_el_contrato_de_campos() -> None:
    """ReporteSerie y ResultadoSerie exponen exactamente los campos documentados."""
    assert {campo.name for campo in fields(ReporteSerie)} == {
        "id",
        "observado_en",
        "precio_cop",
        "cantidad_base",
        "precio_por_base",
        "origen",
        "estado",
        "es_demo",
        "presentacion_id",
    }
    assert {campo.name for campo in fields(ResultadoSerie)} == {
        "puntos",
        "truncado",
        "datos_de_demostracion",
    }
    assert not any(
        campo.name in CAMPOS_PROHIBIDOS
        for campo in (*fields(ReporteSerie), *fields(ResultadoSerie))
    )


# 10. Errores de entrada


def test_error_si_desde_es_mayor_que_hasta() -> None:
    """Una ventana invertida es un error de programacion."""
    with pytest.raises(ValueError):
        construir_serie([], desde=HASTA, hasta=DESDE, unidad_base="g", limite=10)


@pytest.mark.parametrize("limite", [0, -1])
def test_error_si_limite_es_menor_a_uno(limite: int) -> None:
    """El limite debe ser al menos uno."""
    with pytest.raises(ValueError):
        construir_serie([], desde=DESDE, hasta=HASTA, unidad_base="g", limite=limite)


def test_error_si_el_origen_es_desconocido() -> None:
    """Un origen fuera de usuario, comercio o semilla es un error."""
    reporte = _crear_reporte(MOMENTO_BASE, origen="importado")

    with pytest.raises(ValueError):
        construir_serie(
            [reporte],
            desde=DESDE,
            hasta=HASTA,
            unidad_base="g",
            limite=10,
        )


def test_error_si_el_estado_es_desconocido() -> None:
    """Un estado fuera de aceptado, dudoso o rechazado es un error."""
    reporte = _crear_reporte(MOMENTO_BASE, estado="pendiente")

    with pytest.raises(ValueError):
        construir_serie(
            [reporte],
            desde=DESDE,
            hasta=HASTA,
            unidad_base="g",
            limite=10,
        )


def test_error_si_la_unidad_base_no_esta_soportada() -> None:
    """Solo se admiten las unidades base g, ml y unidad."""
    reporte = _crear_reporte(MOMENTO_BASE)

    with pytest.raises(ValueError):
        construir_serie(
            [reporte],
            desde=DESDE,
            hasta=HASTA,
            unidad_base="lb",
            limite=10,
        )


def test_error_si_observado_en_no_tiene_zona_horaria() -> None:
    """Una fecha ingenua no es comparable con la ventana UTC y debe rechazarse."""
    reporte = _crear_reporte(datetime(2026, 9, 1, 12, 0, 0))

    with pytest.raises(ValueError):
        construir_serie(
            [reporte],
            desde=DESDE,
            hasta=HASTA,
            unidad_base="g",
            limite=10,
        )


# 11. Determinismo


def test_dos_llamadas_con_la_misma_entrada_producen_el_mismo_resultado() -> None:
    """La construccion de la serie no depende de estado oculto ni aleatoriedad."""
    reportes = [
        _crear_reporte(
            MOMENTO_BASE + timedelta(days=2),
            reporte_id=UUID(int=5),
            precio_cop=5300,
        ),
        _crear_reporte(
            MOMENTO_BASE,
            reporte_id=UUID(int=7),
            precio_cop=4800,
        ),
        _crear_reporte(
            MOMENTO_BASE + timedelta(days=1),
            reporte_id=UUID(int=6),
            estado="dudoso",
            es_demo=True,
        ),
    ]

    primera = construir_serie(
        reportes,
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )
    segunda = construir_serie(
        reportes,
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    assert [punto.id for punto in primera.puntos] == [punto.id for punto in segunda.puntos]
    assert [punto.observado_en for punto in primera.puntos] == [
        punto.observado_en for punto in segunda.puntos
    ]
    assert [punto.precio_cop for punto in primera.puntos] == [
        punto.precio_cop for punto in segunda.puntos
    ]
    assert [punto.precio_por_base for punto in primera.puntos] == [
        punto.precio_por_base for punto in segunda.puntos
    ]
    assert [punto.precio_por_unidad for punto in primera.puntos] == [
        punto.precio_por_unidad for punto in segunda.puntos
    ]
    assert primera.truncado == segunda.truncado
    assert primera.datos_de_demostracion == segunda.datos_de_demostracion
    assert primera.puntos == segunda.puntos


# 12. Sin mutacion y secuencias admitidas


def test_no_modifica_la_lista_de_entrada() -> None:
    """La funcion no reordena, elimina ni altera los reportes recibidos."""
    tercero = _crear_reporte(MOMENTO_BASE + timedelta(days=2), reporte_id=UUID(int=3))
    primero = _crear_reporte(MOMENTO_BASE, reporte_id=UUID(int=1))
    segundo = _crear_reporte(MOMENTO_BASE + timedelta(days=1), reporte_id=UUID(int=2))
    reportes = [tercero, primero, segundo]
    copia = list(reportes)

    construir_serie(reportes, desde=DESDE, hasta=HASTA, unidad_base="g", limite=10)

    assert reportes == copia
    assert [reporte.id for reporte in reportes] == [tercero.id, primero.id, segundo.id]


def test_acepta_una_tupla_como_secuencia_de_entrada() -> None:
    """La entrada es una Sequence: una tupla inmutable debe funcionar igual que una lista."""
    reportes = (
        _crear_reporte(MOMENTO_BASE + timedelta(hours=1), reporte_id=UUID(int=2)),
        _crear_reporte(MOMENTO_BASE, reporte_id=UUID(int=1)),
    )

    resultado = construir_serie(
        reportes,
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    assert [punto.id for punto in resultado.puntos] == [UUID(int=1), UUID(int=2)]


def test_estructuras_de_salida_son_inmutables() -> None:
    """ReporteSerie, PuntoSeriePrecio y ResultadoSerie son dataclasses congeladas."""
    reporte = _crear_reporte(MOMENTO_BASE)
    resultado = construir_serie(
        [reporte],
        desde=DESDE,
        hasta=HASTA,
        unidad_base="g",
        limite=10,
    )

    with pytest.raises(FrozenInstanceError):
        reporte.precio_cop = 1  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        resultado.puntos[0].precio_cop = 1  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        resultado.truncado = True  # type: ignore[misc]
