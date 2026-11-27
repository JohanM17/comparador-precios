"""Pruebas unitarias TDD del contraste entre precio oficial y comunidad (D-01, tarea T-64).

Reglas que se verifican, tomadas de la decision D-01 del plan de construccion:

- Sin precio oficial, manda la comunidad y nada cambia.
- Con precio oficial y sin contradiccion, se muestra el oficial con sello `oficial`.
- Hay contradiccion cuando al menos `disputa.min_reportes` reportes aceptados, de al menos
  `disputa.min_cuentas` cuentas distintas, dentro de `disputa.ventana_horas`, tienen una
  mediana que difiere del oficial en `disputa.diferencia_pct` o mas.
- En contradiccion el sello pasa a `en_disputa`, se posiciona con el precio de la comunidad
  y se exponen los dos valores.
- El precio oficial sin cambios por mas de `vigencia.comercio_revalidar_dias` pide revalidacion,
  pero no pierde el sello.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.dominio.contraste import PrecioOficialVigente, contrastar_oficial_con_comunidad
from app.dominio.parametros import ParametrosDominio
from app.dominio.sello import evaluar_sello_y_precio
from app.dominio.vigencia import CandidatoReporte

AHORA = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
CANTIDAD = Decimal("1000.000")
PARAMS = ParametrosDominio()


def _reporte(
    precio_cop: int,
    horas_atras: float = 1.0,
    autor_id: str | None = None,
    estado: str = "aceptado",
    fuente: str = "usuario",
) -> CandidatoReporte:
    """Crea un candidato de reporte en memoria para el dominio puro."""
    return CandidatoReporte(
        id=uuid4(),
        precio_cop=precio_cop,
        observado_en=AHORA - timedelta(hours=horas_atras),
        autor_id=autor_id or str(uuid4()),
        reputacion_autor=0.8,
        tiene_foto=False,
        estado=estado,
        fuente=fuente,
        cantidad_base=CANTIDAD,
    )


def _oficial(precio_cop: int, dias_atras: float = 1.0) -> PrecioOficialVigente:
    """Crea un precio oficial publicado por el comercio."""
    return PrecioOficialVigente(
        precio_cop=precio_cop,
        cantidad_base=CANTIDAD,
        confirmado_en=AHORA - timedelta(days=dias_atras),
    )


def _comunidad(reportes: list[CandidatoReporte]):
    """Evalua el resultado comunitario con el arbol de sellos del nucleo."""
    return evaluar_sello_y_precio(reportes, AHORA, PARAMS)


def test_sin_oficial_ni_comunidad_devuelve_none() -> None:
    assert contrastar_oficial_con_comunidad(None, None, [], AHORA, PARAMS) is None


def test_sin_precio_oficial_manda_la_comunidad() -> None:
    reportes = [_reporte(2600), _reporte(2650), _reporte(2600)]
    comunidad = _comunidad(reportes)

    res = contrastar_oficial_con_comunidad(None, comunidad, reportes, AHORA, PARAMS)

    assert res is not None
    assert res.resultado == comunidad
    assert res.precio_oficial_cop is None
    assert res.diferencia_pct is None
    assert res.hay_disputa is False
    assert res.requiere_revalidacion is False


def test_oficial_sin_reportes_usa_el_precio_del_comercio() -> None:
    res = contrastar_oficial_con_comunidad(_oficial(2890), None, [], AHORA, PARAMS)

    assert res is not None
    assert res.resultado.sello == "oficial"
    assert res.resultado.precio_cop == 2890
    assert res.resultado.precio_por_base == Decimal("2.890000")
    assert res.precio_oficial_cop == 2890
    assert res.diferencia_pct is None
    assert res.hay_disputa is False


def test_oficial_con_comunidad_que_coincide_conserva_el_sello_oficial() -> None:
    # 2900 frente a 2890 oficial: 0,35 % de diferencia, muy por debajo del 10 %.
    reportes = [
        _reporte(2900, autor_id="a"),
        _reporte(2900, autor_id="b"),
        _reporte(2900, autor_id="c"),
    ]
    res = contrastar_oficial_con_comunidad(
        _oficial(2890), _comunidad(reportes), reportes, AHORA, PARAMS
    )

    assert res is not None
    assert res.resultado.sello == "oficial"
    assert res.resultado.precio_cop == 2890
    assert res.hay_disputa is False
    assert res.diferencia_pct is not None
    assert res.diferencia_pct < Decimal("0.10")


def test_contradiccion_comunitaria_pasa_a_en_disputa_y_expone_ambos_precios() -> None:
    # Tres reportes aceptados, tres cuentas distintas, dentro de 48 h, 2600 frente a 3050
    # oficial: 14,75 % de diferencia, por encima del umbral del 10 %.
    reportes = [
        _reporte(2600, horas_atras=5, autor_id="a"),
        _reporte(2600, horas_atras=10, autor_id="b"),
        _reporte(2650, horas_atras=20, autor_id="c"),
    ]
    res = contrastar_oficial_con_comunidad(
        _oficial(3050), _comunidad(reportes), reportes, AHORA, PARAMS
    )

    assert res is not None
    assert res.resultado.sello == "en_disputa"
    # Se posiciona con el precio de la comunidad, no con el del comercio.
    assert res.resultado.precio_cop == 2600
    # Y se exponen los dos valores.
    assert res.precio_oficial_cop == 3050
    assert res.hay_disputa is True
    assert res.diferencia_pct is not None
    assert res.diferencia_pct >= Decimal("0.10")
    assert res.resultado.motivo_sello is not None


def test_dos_reportes_no_alcanzan_el_minimo_para_declarar_disputa() -> None:
    reportes = [_reporte(2600, autor_id="a"), _reporte(2600, autor_id="b")]
    res = contrastar_oficial_con_comunidad(
        _oficial(3050), _comunidad(reportes), reportes, AHORA, PARAMS
    )

    assert res is not None
    assert res.hay_disputa is False
    assert res.resultado.sello == "oficial"
    assert res.resultado.precio_cop == 3050


def test_tres_reportes_de_una_sola_cuenta_no_declaran_disputa() -> None:
    # Defensa contra el comercio competidor o el usuario insistente: una sola voz no basta.
    reportes = [
        _reporte(2600, horas_atras=2, autor_id="a"),
        _reporte(2600, horas_atras=6, autor_id="a"),
        _reporte(2600, horas_atras=9, autor_id="a"),
    ]
    res = contrastar_oficial_con_comunidad(
        _oficial(3050), _comunidad(reportes), reportes, AHORA, PARAMS
    )

    assert res is not None
    assert res.hay_disputa is False
    assert res.resultado.sello == "oficial"


def test_reportes_fuera_de_la_ventana_de_48_horas_no_declaran_disputa() -> None:
    reportes = [
        _reporte(2600, horas_atras=60, autor_id="a"),
        _reporte(2600, horas_atras=72, autor_id="b"),
        _reporte(2650, horas_atras=80, autor_id="c"),
    ]
    res = contrastar_oficial_con_comunidad(
        _oficial(3050), _comunidad(reportes), reportes, AHORA, PARAMS
    )

    assert res is not None
    assert res.hay_disputa is False
    assert res.resultado.sello == "oficial"


def test_reportes_dudosos_no_cuentan_para_la_disputa() -> None:
    reportes = [
        _reporte(2600, autor_id="a", estado="dudoso"),
        _reporte(2600, autor_id="b", estado="dudoso"),
        _reporte(2600, autor_id="c", estado="dudoso"),
    ]
    res = contrastar_oficial_con_comunidad(
        _oficial(3050), _comunidad(reportes), reportes, AHORA, PARAMS
    )

    assert res is not None
    assert res.hay_disputa is False
    assert res.resultado.sello == "oficial"


def test_precio_oficial_sin_cambios_por_mas_de_30_dias_pide_revalidacion() -> None:
    res = contrastar_oficial_con_comunidad(_oficial(2890, dias_atras=31), None, [], AHORA, PARAMS)

    assert res is not None
    assert res.requiere_revalidacion is True
    # Pide revalidacion, pero no pierde el sello: D-02 lo plantea como aviso, no como castigo.
    assert res.resultado.sello == "oficial"
    assert res.resultado.motivo_sello is not None
    assert "revalidar" in res.resultado.motivo_sello.lower()


def test_precio_oficial_reciente_no_pide_revalidacion() -> None:
    res = contrastar_oficial_con_comunidad(_oficial(2890, dias_atras=3), None, [], AHORA, PARAMS)

    assert res is not None
    assert res.requiere_revalidacion is False


def test_la_disputa_tambien_se_declara_cuando_la_comunidad_reporta_mas_caro() -> None:
    # La regla no protege al comercio ni al usuario: protege al dato.
    reportes = [
        _reporte(3600, horas_atras=3, autor_id="a"),
        _reporte(3600, horas_atras=8, autor_id="b"),
        _reporte(3650, horas_atras=12, autor_id="c"),
    ]
    res = contrastar_oficial_con_comunidad(
        _oficial(2890), _comunidad(reportes), reportes, AHORA, PARAMS
    )

    assert res is not None
    assert res.hay_disputa is True
    assert res.resultado.sello == "en_disputa"
    assert res.resultado.precio_cop == 3600
