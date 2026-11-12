#!/usr/bin/env python3
"""Script para exportar el esquema OpenAPI de FastAPI en docs/api/openapi.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Agregar directorio backend al sys.path para importar app
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from app.main import create_app  # noqa: E402


def exportar_openapi() -> int:
    """Genera y guarda el archivo openapi.json a partir de la aplicacion FastAPI."""
    app = create_app()
    esquema = app.openapi()

    ruta_destino = RAIZ / "docs" / "api" / "openapi.json"
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)

    with open(ruta_destino, "w", encoding="utf-8") as f:
        json.dump(esquema, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")

    print(f"[OK] Esquema OpenAPI exportado exitosamente en: {ruta_destino}")
    return 0


if __name__ == "__main__":
    codigo = exportar_openapi()
    sys.exit(codigo)
