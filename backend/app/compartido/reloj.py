"""Protocolo de reloj abstracto e implementaciones para pruebas deterministas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Reloj(Protocol):
    """Protocolo abstracto para obtencion de la hora actual en UTC."""

    def ahora_utc(self) -> datetime:
        """Retorna la fecha y hora actual en zona horaria UTC."""
        ...


class RelojSistema:
    """Implementacion real basada en el reloj del sistema operativo."""

    def ahora_utc(self) -> datetime:
        return datetime.now(UTC)


class RelojFalso:
    """Implementacion controlada para pruebas unitarias deterministas sin I/O."""

    def __init__(self, instante_inicial: datetime | None = None) -> None:
        if instante_inicial is None:
            self._actual = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
        elif instante_inicial.tzinfo is None:
            self._actual = instante_inicial.replace(tzinfo=UTC)
        else:
            self._actual = instante_inicial

    def ahora_utc(self) -> datetime:
        return self._actual

    def fijar(self, nuevo_instante: datetime) -> None:
        """Fija el reloj en un instante arbitrario."""
        if nuevo_instante.tzinfo is None:
            self._actual = nuevo_instante.replace(tzinfo=UTC)
        else:
            self._actual = nuevo_instante

    def avanzar(
        self,
        segundos: float = 0,
        minutos: float = 0,
        horas: float = 0,
        dias: float = 0,
    ) -> None:
        """Avanza el tiempo relativo la cantidad indicada."""
        delta = timedelta(days=dias, hours=horas, minutes=minutos, seconds=segundos)
        self._actual += delta
