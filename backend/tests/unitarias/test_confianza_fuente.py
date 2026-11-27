"""Pruebas unitarias del origen de los niveles de referencia de confianza.

El historial oficial (`fuente='comercio'`) es evidencia del comercio, no un voto
comunitario. Las tres consultas N1/N2/N3 que alimentan la deteccion de anomalias
deben excluirlo explicitamente.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.modulos.confianza.servicio import ServicioConfianza


class ResultadoVacio:
    """Resultado de consulta sin filas."""

    def fetchall(self) -> list[Any]:
        return []


class SesionEspia:
    """Captura el SQL ejecutado y devuelve resultados vacios."""

    def __init__(self) -> None:
        self.consultas: list[str] = []

    async def execute(self, sentencia: Any, parametros: Any = None) -> ResultadoVacio:
        self.consultas.append(" ".join(str(sentencia).lower().split()))
        return ResultadoVacio()


async def test_niveles_de_referencia_excluyen_el_historial_oficial() -> None:
    """N1, N2 y N3 no pueden usar filas `fuente='comercio'` como referencia."""
    sesion = SesionEspia()

    niveles = await ServicioConfianza()._cargar_niveles_referencia(
        sesion,  # type: ignore[arg-type]
        UUID(int=1),
        UUID(int=2),
        UUID(int=3),
        UUID(int=4),
        "Armenia",
        datetime(2026, 11, 27, tzinfo=UTC),
        False,
    )

    assert niveles.presentacion_tienda == []
    assert niveles.presentacion == []
    assert niveles.producto_unitario == []
    assert len(sesion.consultas) == 3
    for consulta in sesion.consultas:
        assert "fuente <> 'comercio'" in consulta
