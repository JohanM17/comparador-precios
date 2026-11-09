#!/usr/bin/env python3
"""Script para aplicar migraciones SQL en orden secuencial sobre Supabase.

Utiliza MIGRATIONS_DATABASE_URL (o DATABASE_URL) del archivo .env local.
Registra el historial de migraciones aplicadas en la tabla _migraciones_historial.
Ejecuta el script SQL usando asyncpg para soportar múltiples sentencias por archivo.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg

SEPARADOR_DOBLE = "=" * 68
SEPARADOR_SIMPLE = "-" * 68


def cargar_env(ruta_env: Path) -> None:
    """Carga variables desde el archivo .env sin imprimir valores sensibles."""
    if not ruta_env.exists():
        print(f"[ERROR] No se encontro el archivo .env en: {ruta_env}")
        sys.exit(1)

    with open(ruta_env, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            if "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            clave = clave.strip()
            valor = valor.strip()
            if (valor.startswith('"') and valor.endswith('"')) or (
                valor.startswith("'") and valor.endswith("'")
            ):
                valor = valor[1:-1]
            if clave and clave not in os.environ:
                os.environ[clave] = valor


def ofuscar_url(url: str) -> str:
    """Retorna una representacion segura de la URL sin contraseñas."""
    try:
        parsed = urlsplit(url)
        user = parsed.username or ""
        usuario_seguro = f"{user}:***" if parsed.password else user
        host_puerto = parsed.hostname or ""
        if parsed.port:
            host_puerto += f":{parsed.port}"
        netloc = f"{usuario_seguro}@{host_puerto}" if usuario_seguro else host_puerto
        return f"{parsed.scheme}://{netloc}{parsed.path}"
    except Exception:
        return "[URL protegida]"


async def ejecutar_migraciones() -> int:
    print(SEPARADOR_DOBLE)
    print(" Ejecutor de Migraciones SQL — Supabase PostgreSQL")
    print(SEPARADOR_DOBLE)

    raiz = Path(__file__).resolve().parent.parent
    cargar_env(raiz / ".env")

    url_migraciones = os.getenv("MIGRATIONS_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url_migraciones:
        print("[ERROR] Ni MIGRATIONS_DATABASE_URL ni DATABASE_URL estan definidas en .env")
        return 1

    print(f"[*] Conectando a la base de datos: {ofuscar_url(url_migraciones)}")

    # Convertir URL SQLAlchemy a DSN compatible con asyncpg
    dsn = url_migraciones
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = "postgresql://" + dsn[len("postgresql+asyncpg://") :]

    directorio_migraciones = raiz / "supabase" / "migrations"
    if not directorio_migraciones.exists():
        print(f"[ERROR] Directorio de migraciones no existe: {directorio_migraciones}")
        return 1

    archivos_sql = sorted(directorio_migraciones.glob("*.sql"))
    if not archivos_sql:
        print("[AVISO] No se encontraron archivos .sql en supabase/migrations/")
        return 0

    conn: asyncpg.Connection | None = None
    try:
        # statement_cache_size=0 asegura compatibilidad con Poolers (Session o Transaction)
        conn = await asyncpg.connect(dsn=dsn, statement_cache_size=0)

        # 1. Asegurar tabla de historial
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS public._migraciones_historial (
                nombre VARCHAR(255) PRIMARY KEY,
                aplicado_en TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )

        # 2. Consultar migraciones ya aplicadas
        filas = await conn.fetch(
            "SELECT nombre FROM public._migraciones_historial ORDER BY nombre ASC;"
        )
        aplicadas = {fila["nombre"] for fila in filas}

        pendientes = [f for f in archivos_sql if f.name not in aplicadas]
        if not pendientes:
            print("\n[INFO] La base de datos esta al dia. No hay migraciones pendientes.")
            print(SEPARADOR_DOBLE)
            return 0

        print(f"\n[*] Migraciones pendientes por aplicar: {len(pendientes)}")
        for archivo in pendientes:
            nombre = archivo.name
            print(f"    -> Aplicando {nombre}...")
            contenido_sql = archivo.read_text(encoding="utf-8")

            # Ejecutar todas las sentencias DDL del archivo en una transaccion
            async with conn.transaction():
                await conn.execute(contenido_sql)
                await conn.execute(
                    "INSERT INTO public._migraciones_historial (nombre) VALUES ($1);",
                    nombre,
                )
            print(f"       [OK] {nombre} aplicada con exito.")

        print(f"\n{SEPARADOR_SIMPLE}")
        print(f"[EXITO] Se aplicaron {len(pendientes)} migracion(es) correctamente.")
        print(SEPARADOR_DOBLE)
        return 0
    except Exception as exc:
        print(f"\n[ERROR] Fallo durante la ejecucion de migraciones: {exc}")
        print(SEPARADOR_DOBLE)
        return 1
    finally:
        if conn is not None:
            await conn.close()


def main() -> None:
    codigo = asyncio.run(ejecutar_migraciones())
    sys.exit(codigo)


if __name__ == "__main__":
    main()
