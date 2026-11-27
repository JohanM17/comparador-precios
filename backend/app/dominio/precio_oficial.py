"""Reglas puras del precio oficial publicado por un comercio (D-06, ADR-0019).

Modulo de dominio puro: no conoce la base de datos ni la red. La unica decision que
se toma aqui es si una publicacion deja una version nueva en el historial append-only
de `reporte_precio` o si basta con refrescar la confirmacion del precio existente.
"""

from __future__ import annotations


def requiere_historial_oficial(
    precio_anterior_cop: int | None,
    precio_nuevo_cop: int,
) -> bool:
    """Indica si publicar el precio deja una version nueva en el historial.

    Un precio que no existia se conserva siempre. Republicar o revalidar el mismo
    valor no agrega otra fila, de modo que el historial no duplique la version
    vigente del comercio (ADR-0019).
    """
    return precio_anterior_cop != precio_nuevo_cop
