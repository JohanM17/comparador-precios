"""Control de tasa de peticiones mediante ventana deslizante en memoria."""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque

from app.compartido.errores import LimiteExcedidoError


class LimitadorVentanaDeslizante:
    """Implementacion en memoria de ventana deslizante para proteccion de cuotas."""

    def __init__(self) -> None:
        self._registros: dict[str, deque[float]] = defaultdict(deque)

    def verificar(
        self,
        clave: str,
        max_solicitudes: int,
        ventana_segundos: int,
        ahora: float | None = None,
    ) -> tuple[bool, int]:
        """Evalua si una clave puede realizar una peticion dentro de la ventana de tiempo.

        Retorna:
            (permitido: bool, retry_after: int)
        """
        instante = ahora if ahora is not None else time.time()
        cola = self._registros[clave]
        limite_inferior = instante - ventana_segundos

        # Eviccion de marcas de tiempo fuera de la ventana
        while cola and cola[0] <= limite_inferior:
            cola.popleft()

        if len(cola) < max_solicitudes:
            cola.append(instante)
            return True, 0

        primer_evento = cola[0]
        tiempo_restante = (primer_evento + ventana_segundos) - instante
        retry_after = max(1, math.ceil(tiempo_restante))
        return False, retry_after

    def exigir_limite(
        self,
        clave: str,
        max_solicitudes: int,
        ventana_segundos: int,
        detalle: str = "Ha superado el limite de solicitudes permitido.",
    ) -> None:
        """Verifica el limite y lanza LimiteExcedidoError si es superado."""
        permitido, retry_after = self.verificar(clave, max_solicitudes, ventana_segundos)
        if not permitido:
            raise LimiteExcedidoError(detalle, retry_after=retry_after)

    def limpiar(self) -> None:
        """Reinicia todos los contadores de la memoria."""
        self._registros.clear()
