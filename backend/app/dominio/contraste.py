"""Contraste entre el precio oficial de un comercio y el precio de la comunidad (D-01).

Modulo de dominio puro: no conoce la base de datos ni la red. Recibe el precio oficial
publicado por el comercio, el resultado que el arbol de sellos del nucleo calculo con los
reportes de la comunidad, y los reportes crudos para poder mirar la ventana corta de disputa.

La regla de negocio, decision D-01:

- Sin precio oficial, manda la comunidad y este modulo no interviene.
- Con precio oficial, se muestra el oficial, salvo contradiccion comunitaria.
- Hay contradiccion cuando al menos `disputa_min_reportes` reportes aceptados, de al menos
  `disputa_min_cuentas` cuentas distintas, observados dentro de `disputa_ventana_horas`,
  tienen una mediana que difiere del oficial en `disputa_diferencia_pct` o mas.
- En contradiccion el sello pasa a `en_disputa`, la comparacion se posiciona con el precio
  de la comunidad y se exponen los dos valores. Quien decide quien tiene razon es un
  moderador humano, no este modulo: aqui solo se levanta la mano.

El criterio es simetrico a proposito. Da igual si la comunidad reporta mas barato o mas caro
que el comercio: lo que se protege es el dato, no a una de las dos partes.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.dominio.parametros import ParametrosDominio
from app.dominio.sello import ResultadoSelloYPrecio
from app.dominio.unidades import calcular_precio_por_base
from app.dominio.vigencia import CandidatoReporte


@dataclass(frozen=True)
class PrecioOficialVigente:
    """Precio publicado por el comercio dueno del establecimiento."""

    precio_cop: int
    cantidad_base: Decimal
    actualizado_en: datetime


@dataclass(frozen=True)
class ResultadoContraste:
    """Precio vigente resuelto mas los datos del contraste con el comercio."""

    resultado: ResultadoSelloYPrecio
    precio_oficial_cop: int | None
    diferencia_pct: Decimal | None
    requiere_revalidacion: bool
    hay_disputa: bool


@dataclass(frozen=True)
class _VozComunidad:
    """Resumen de los reportes aceptados dentro de la ventana corta de disputa."""

    mediana_cop: int
    n_reportes: int
    n_cuentas: int
    cantidad_base: Decimal
    ultimo_observado_en: datetime
    reporte_origen_id: UUID


def _escuchar_comunidad(
    reportes: list[CandidatoReporte],
    ahora: datetime,
    params: ParametrosDominio,
) -> _VozComunidad | None:
    """Resume los reportes aceptados de la ventana de disputa; None si no hay ninguno."""
    limite = ahora - timedelta(hours=params.disputa_ventana_horas)
    recientes = [r for r in reportes if r.estado == "aceptado" and r.observado_en >= limite]
    if not recientes:
        return None

    mas_reciente = max(recientes, key=lambda r: r.observado_en)
    return _VozComunidad(
        mediana_cop=int(statistics.median([r.precio_cop for r in recientes])),
        n_reportes=len(recientes),
        n_cuentas=len({r.autor_id for r in recientes if r.autor_id}),
        cantidad_base=mas_reciente.cantidad_base,
        ultimo_observado_en=mas_reciente.observado_en,
        reporte_origen_id=mas_reciente.id,
    )


def _diferencia_relativa(precio_oficial: int, precio_comunidad: int) -> Decimal:
    """Diferencia porcentual entre los dos precios, en valor absoluto."""
    return (
        abs(Decimal(precio_comunidad) - Decimal(precio_oficial)) / Decimal(precio_oficial)
    ).quantize(Decimal("0.0001"))


def _hay_contradiccion(
    voz: _VozComunidad,
    diferencia: Decimal,
    params: ParametrosDominio,
) -> bool:
    """Aplica los tres filtros de D-01: cantidad de reportes, de cuentas y magnitud."""
    return (
        voz.n_reportes >= params.disputa_min_reportes
        and voz.n_cuentas >= params.disputa_min_cuentas
        and diferencia >= Decimal(str(params.disputa_diferencia_pct))
    )


def _resultado_oficial(
    oficial: PrecioOficialVigente,
    comunidad: ResultadoSelloYPrecio | None,
    dias_sin_cambios: int,
    requiere_revalidacion: bool,
) -> ResultadoSelloYPrecio:
    """Arma el precio vigente cuando manda el comercio."""
    motivo = "Precio publicado por el comercio"
    if requiere_revalidacion:
        motivo = f"Precio oficial por revalidar: {dias_sin_cambios} días sin cambios"

    return ResultadoSelloYPrecio(
        sello="oficial",
        motivo_sello=motivo,
        precio_cop=oficial.precio_cop,
        precio_por_base=calcular_precio_por_base(oficial.precio_cop, oficial.cantidad_base),
        cantidad_base=oficial.cantidad_base,
        n_reportes_validos=comunidad.n_reportes_validos if comunidad else 0,
        n_fuentes=comunidad.n_fuentes if comunidad else 0,
        dispersion=comunidad.dispersion if comunidad else None,
        ultimo_reporte_en=oficial.actualizado_en,
        reporte_origen_id=None,
    )


def _resultado_en_disputa(
    oficial: PrecioOficialVigente,
    voz: _VozComunidad,
) -> ResultadoSelloYPrecio:
    """Arma el precio vigente cuando la comunidad contradice al comercio."""
    return ResultadoSelloYPrecio(
        sello="en_disputa",
        motivo_sello=(
            f"La comunidad reporta un precio distinto al oficial de "
            f"${oficial.precio_cop:,.0f}".replace(",", ".")
        ),
        precio_cop=voz.mediana_cop,
        precio_por_base=calcular_precio_por_base(voz.mediana_cop, voz.cantidad_base),
        cantidad_base=voz.cantidad_base,
        n_reportes_validos=voz.n_reportes,
        n_fuentes=voz.n_cuentas,
        dispersion=None,
        ultimo_reporte_en=voz.ultimo_observado_en,
        reporte_origen_id=voz.reporte_origen_id,
    )


def contrastar_oficial_con_comunidad(
    oficial: PrecioOficialVigente | None,
    comunidad: ResultadoSelloYPrecio | None,
    reportes: list[CandidatoReporte],
    ahora: datetime,
    params: ParametrosDominio,
) -> ResultadoContraste | None:
    """Resuelve el precio vigente contrastando al comercio con la comunidad (D-01)."""
    if oficial is None:
        if comunidad is None:
            return None
        return ResultadoContraste(
            resultado=comunidad,
            precio_oficial_cop=None,
            diferencia_pct=None,
            requiere_revalidacion=False,
            hay_disputa=False,
        )

    dias_sin_cambios = int((ahora - oficial.actualizado_en).total_seconds() // 86400)
    requiere_revalidacion = dias_sin_cambios >= params.vigencia_comercio_revalidar_dias

    voz = _escuchar_comunidad(reportes, ahora, params)
    diferencia = (
        _diferencia_relativa(oficial.precio_cop, voz.mediana_cop) if voz is not None else None
    )

    if voz is not None and diferencia is not None and _hay_contradiccion(voz, diferencia, params):
        return ResultadoContraste(
            resultado=_resultado_en_disputa(oficial, voz),
            precio_oficial_cop=oficial.precio_cop,
            diferencia_pct=diferencia,
            requiere_revalidacion=requiere_revalidacion,
            hay_disputa=True,
        )

    return ResultadoContraste(
        resultado=_resultado_oficial(oficial, comunidad, dias_sin_cambios, requiere_revalidacion),
        precio_oficial_cop=oficial.precio_cop,
        diferencia_pct=diferencia,
        requiere_revalidacion=requiere_revalidacion,
        hay_disputa=False,
    )
