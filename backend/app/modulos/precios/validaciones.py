"""Validaciones auxiliares y mapeos para el modulo de precios."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from app.compartido.errores import (
    CuentaSuspendidaError,
    FechaInvalidaError,
    PrecioFueraDeRangoError,
    ValidacionError,
)
from app.compartido.limites import LimitadorVentanaDeslizante
from app.compartido.seguridad import UsuarioAutenticado
from app.dominio.parametros import ParametrosDominio
from app.dominio.reputacion import es_cuenta_nueva
from app.modulos.precios.esquemas import CrearReporteEntrada


def determinar_estado_visible(estado: str) -> str:
    """Traduce el estado interno de un reporte al estado visible segun privacidad."""
    if estado == "dudoso":
        return "en_revision"
    if estado == "rechazado":
        return "rechazado"
    return "recibido"


def validar_entrada_reporte(
    entrada: CrearReporteEntrada,
    params: ParametrosDominio,
    instante: datetime,
    idempotency_key: str | None,
) -> UUID:
    """Valida cabeceras, rangos duros y temporalidad del reporte entrante."""
    if not idempotency_key:
        raise ValidacionError("La cabecera 'Idempotency-Key' es obligatoria.")
    try:
        key_uuid = UUID(idempotency_key)
    except ValueError as exc:
        raise ValidacionError("La cabecera 'Idempotency-Key' debe ser un UUID valido.") from exc

    if entrada.precio_cop < params.precio_min_cop or entrada.precio_cop > params.precio_max_cop:
        raise PrecioFueraDeRangoError(
            f"Precio fuera de [{params.precio_min_cop}, {params.precio_max_cop}]."
        )
    if entrada.observado_en > instante + timedelta(seconds=60):
        raise FechaInvalidaError("La fecha de observacion no puede estar en el futuro.")
    if entrada.observado_en < instante - timedelta(hours=params.observado_max_antiguedad_horas):
        raise FechaInvalidaError("El reporte supera la antiguedad maxima permitida.")

    return key_uuid


async def validar_limites_usuario(
    limitador: LimitadorVentanaDeslizante,
    confianza: Any,
    sesion: Any,
    usuario: UsuarioAutenticado,
    ip_cliente: str,
    instante: datetime,
    params: ParametrosDominio,
) -> None:
    """Valida estado de cuenta y limites por IP y usuario por hora."""
    if usuario.estado in ("suspendida", "bloqueada"):
        raise CuentaSuspendidaError()

    limitador.exigir_limite(
        f"ip:{ip_cliente}", params.limite_escrituras_ip_min, 60, "Limite por minuto superado."
    )
    creado_en, _, _ = await confianza._cargar_datos_autor(sesion, usuario.id)
    es_nueva = es_cuenta_nueva(
        creado_en, instante, 0, params.cuenta_nueva_dias, params.cuenta_nueva_min_aceptados
    )
    max_h = params.limite_reportes_hora_nuevo if es_nueva else params.limite_reportes_hora_normal
    limitador.exigir_limite(f"usr:{usuario.id}", max_h, 3600, "Cuota horaria superada.")
