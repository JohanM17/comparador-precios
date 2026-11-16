"""Utilidades para normalizacion de texto y busqueda difusa."""

from __future__ import annotations

import re
import unicodedata


def normalizar_texto(texto: str) -> str:
    """Convierte a minusculas, retira acentos y tildes, y compacta espacios.

    Ejemplo: ' Arroz Diana 500g (Población) ' -> 'arroz diana 500g (poblacion)'
    """
    if not texto:
        return ""

    # Normalizacion de forma descompuesta para separar caracteres base y marcas de acento
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Conversion a minusculas y limpieza de espacios en blanco
    limpio = sin_tildes.lower().strip()
    return re.sub(r"\s+", " ", limpio)
