"""Pruebas unitarias TDD para vigencia, calculo de sellos y ordenamiento neutral (Tarea T-20)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.compartido.reloj import RelojFalso
from app.dominio.orden import ItemComparacion, ordenar_comparacion
from app.dominio.parametros import ParametrosDominio
from app.dominio.sello import evaluar_sello_y_precio
from app.dominio.vigencia import (
    CandidatoReporte,
    calcular_dispersion_mad,
    calcular_mediana_ponderada,
    calcular_peso_reporte,
)


def _crear_reporte(
    precio_cop: int,
    observado_en: datetime,
    autor_id: str | None = None,
    reputacion: float = 0.8,
    tiene_foto: bool = False,
    estado: str = "aceptado",
    fuente: str = "usuario",
    cantidad_base: Decimal = Decimal("1000.000"),
) -> CandidatoReporte:
    """Crea un candidato de reporte en memoria para pruebas de dominio puro."""
    return CandidatoReporte(
        id=uuid4(),
        precio_cop=precio_cop,
        observado_en=observado_en,
        autor_id=autor_id or str(uuid4()),
        reputacion_autor=reputacion,
        tiene_foto=tiene_foto,
        estado=estado,
        fuente=fuente,
        cantidad_base=cantidad_base,
    )


def test_decaimiento_exponencial_exacto_a_120_horas() -> None:
    """A las 120 h (48 + 72), el peso w_i es exactamente la mitad que a las 48 h."""
    ahora = RelojFalso(datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)).ahora_utc()
    params = ParametrosDominio()
    rep_48h = _crear_reporte(5000, ahora - timedelta(hours=48))
    rep_120h = _crear_reporte(5000, ahora - timedelta(hours=120))
    w_48 = calcular_peso_reporte(rep_48h, ahora, params)
    w_120 = calcular_peso_reporte(rep_120h, ahora, params)
    assert pytest.approx(w_48, rel=1e-5) == 0.8
    assert pytest.approx(w_120, rel=1e-5) == 0.4
    assert pytest.approx(w_120, rel=1e-5) == 0.5 * w_48


def test_factor_foto_y_fuente_semilla() -> None:
    """Valida el multiplicador de foto (1.2) y reputacion inicial para semilla."""
    ahora = RelojFalso(datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)).ahora_utc()
    params = ParametrosDominio()
    rep_foto = _crear_reporte(4000, ahora - timedelta(hours=10), reputacion=0.5, tiene_foto=True)
    assert pytest.approx(calcular_peso_reporte(rep_foto, ahora, params), rel=1e-5) == 0.5 * 1.2
    rep_sem = _crear_reporte(4000, ahora - timedelta(hours=10), reputacion=0.99, fuente="semilla")
    peso_sem = calcular_peso_reporte(rep_sem, ahora, params)
    assert pytest.approx(peso_sem, rel=1e-5) == params.reputacion_inicial


def test_mediana_ponderada_corte_mitad() -> None:
    """Verifica que la mediana ponderada acumule pesos hasta alcanzar el 50 %."""
    ahora = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)
    r1, r2, r3 = (
        _crear_reporte(2000, ahora),
        _crear_reporte(3000, ahora),
        _crear_reporte(4000, ahora),
    )
    elegido, precio = calcular_mediana_ponderada([(r1, 0.2), (r2, 0.5), (r3, 0.3)])
    assert elegido.id == r2.id
    assert precio == 3000
    with pytest.raises(ValueError, match="vacia"):
        calcular_mediana_ponderada([])


def test_dispersion_mad_casos_borde() -> None:
    """Verifica calcular_dispersion_mad con listas cortas o vacias."""
    assert calcular_dispersion_mad([]) == 0.0
    assert calcular_dispersion_mad([1000]) == 0.0
    assert calcular_dispersion_mad([0, 0]) == 0.0


def test_sello_desactualizado_reporte_8_dias() -> None:
    """Un reporte aceptado de hace 8 dias genera sello 'desactualizado'."""
    ahora = RelojFalso(datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)).ahora_utc()
    r = _crear_reporte(5200, ahora - timedelta(days=8))
    res = evaluar_sello_y_precio([r], ahora, ParametrosDominio())
    assert res is not None
    assert res.sello == "desactualizado"
    assert res.precio_cop == 5200
    assert "Sin actualizar hace 8 días" in (res.motivo_sello or "")


def test_sello_exclusion_total_reporte_31_dias() -> None:
    """Un reporte de 31 dias sale por completo de precio_vigente (retorna None)."""
    ahora = RelojFalso(datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)).ahora_utc()
    r = _crear_reporte(5200, ahora - timedelta(days=31))
    assert evaluar_sello_y_precio([r], ahora, ParametrosDominio()) is None


def test_sello_dudoso_por_ausencia_de_aceptados() -> None:
    """Si no hay aceptados pero si dudosos recientes, sello es 'dudoso'."""
    ahora = RelojFalso(datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)).ahora_utc()
    r = _crear_reporte(4800, ahora - timedelta(hours=5), estado="dudoso")
    res = evaluar_sello_y_precio([r], ahora, ParametrosDominio())
    assert res is not None
    assert res.sello == "dudoso"
    assert res.motivo_sello == "En revisión: reportes sin confirmar"


def test_sello_confiable_con_3_fuentes_dentro_del_5_porciento() -> None:
    """3 reportes vigentes de 3 cuentas distintas y baja dispersion dan 'confiable'."""
    ahora = RelojFalso(datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)).ahora_utc()
    r1 = _crear_reporte(5000, ahora - timedelta(hours=2), autor_id="u1")
    r2 = _crear_reporte(5100, ahora - timedelta(hours=4), autor_id="u2")
    r3 = _crear_reporte(4950, ahora - timedelta(hours=6), autor_id="u3")
    res = evaluar_sello_y_precio([r1, r2, r3], ahora, ParametrosDominio())
    assert res is not None
    assert res.sello == "confiable"
    assert res.motivo_sello is None
    assert res.n_reportes_validos == 3
    assert res.n_fuentes == 3


def test_sello_pocos_datos_menos_de_3_reportes_o_menos_de_2_fuentes() -> None:
    """2 reportes (n < 3) o 3 reportes de 1 sola cuenta (fuentes < 2) dan 'pocos_datos'."""
    ahora = RelojFalso(datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)).ahora_utc()
    p = ParametrosDominio()
    ra1 = _crear_reporte(5000, ahora - timedelta(hours=2), autor_id="u1")
    ra2 = _crear_reporte(5000, ahora - timedelta(hours=3), autor_id="u2")
    res_a = evaluar_sello_y_precio([ra1, ra2], ahora, p)
    assert res_a is not None
    assert res_a.sello == "pocos_datos"
    rb = [_crear_reporte(5000, ahora - timedelta(hours=i), autor_id="u_sola") for i in (1, 2, 3)]
    res_b = evaluar_sello_y_precio(rb, ahora, p)
    assert res_b is not None
    assert res_b.sello == "pocos_datos"
    assert res_b.n_fuentes == 1


def test_sello_dudoso_por_dispersion_contradictoria() -> None:
    """Dispersion MAD/mediana > 0.15 marca el precio vigente como 'dudoso'."""
    ahora = RelojFalso(datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)).ahora_utc()
    r = [
        _crear_reporte(3000, ahora - timedelta(hours=1), autor_id="u1"),
        _crear_reporte(5000, ahora - timedelta(hours=2), autor_id="u2"),
        _crear_reporte(7000, ahora - timedelta(hours=3), autor_id="u3"),
    ]
    res = evaluar_sello_y_precio(r, ahora, ParametrosDominio())
    assert res is not None
    assert res.sello == "dudoso"
    assert res.motivo_sello == "Reportes contradictorios"


def test_ordenamiento_neutral_en_dos_bloques() -> None:
    """El Bloque 1 precede siempre al Bloque 2; dentro de cada bloque se respeta el criterio."""
    f_rec = datetime(2026, 11, 15, 10, 0, 0, tzinfo=UTC)
    f_ant = datetime(2026, 11, 10, 10, 0, 0, tzinfo=UTC)
    i_a = ItemComparacion(
        uuid4(), "Super Central", 6000, Decimal("6.0"), "confiable", f_rec, distancia_m=500
    )
    i_b = ItemComparacion(
        uuid4(), "Tienda Esquina", 2000, Decimal("2.0"), "dudoso", f_rec, distancia_m=100
    )
    i_c = ItemComparacion(
        uuid4(), "Minimercado Norte", 5500, Decimal("5.5"), "pocos_datos", f_ant, distancia_m=800
    )

    # 1. Criterio precio_unitario: Bloque 1: C ($5.5) < A ($6.0); Bloque 2: B ($2.0)
    ord_pu = ordenar_comparacion([i_a, i_b, i_c], criterio="precio_unitario")
    assert [it.establecimiento_nombre for it in ord_pu] == [
        "Minimercado Norte",
        "Super Central",
        "Tienda Esquina",
    ]
    assert not ord_pu[0].es_bloque_secundario
    assert ord_pu[2].es_bloque_secundario

    # 2. Criterio precio
    ord_p = ordenar_comparacion([i_a, i_b, i_c], criterio="precio")
    assert [it.establecimiento_nombre for it in ord_p] == [
        "Minimercado Norte",
        "Super Central",
        "Tienda Esquina",
    ]

    # 3. Criterio distancia
    ord_d = ordenar_comparacion([i_a, i_b, i_c], criterio="distancia")
    assert [it.establecimiento_nombre for it in ord_d] == [
        "Super Central",
        "Minimercado Norte",
        "Tienda Esquina",
    ]
