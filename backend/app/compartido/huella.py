"""Calculo determinista de huella de red rotativa diaria segun Ley 1581."""

from __future__ import annotations

import hashlib
import hmac
from datetime import date, datetime


def calcular_huella_red(
    ip_cliente: str,
    secreto_maestro: str,
    fecha_utc: datetime | date | str,
) -> str:
    """Calcula la huella de red HMAC-SHA256 rotativa diaria para una direccion IP.

    Garantiza que la direccion IP real nunca se guarde en texto plano en la BD.
    Al cambiar la fecha UTC se deriva una nueva clave, facilitando la purga a 30 dias.
    """
    if isinstance(fecha_utc, datetime):
        fecha_str = fecha_utc.strftime("%Y-%m-%d")
    elif isinstance(fecha_utc, date):
        fecha_str = fecha_utc.strftime("%Y-%m-%d")
    else:
        fecha_str = str(fecha_utc)[:10]

    # Derivacion de clave diaria a partir del secreto maestro y la fecha UTC
    clave_diaria = hmac.new(
        secreto_maestro.encode("utf-8"),
        fecha_str.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    # Calculo de la huella irreversible de la IP del cliente
    huella = hmac.new(
        clave_diaria,
        ip_cliente.strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return huella
