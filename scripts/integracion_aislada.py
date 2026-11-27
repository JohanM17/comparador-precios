#!/usr/bin/env python3
"""Ejecuta la suite de integracion en una base aislada de Supabase (sin Docker).

Crea (o recrea) la base ``comparador_pruebas`` en el mismo cluster configurado en
``.env``, aplica las migraciones, ejecuta ``pytest tests/integracion`` contra ella
y elimina la base al terminar. Nunca imprime credenciales.

Uso:
    backend/.venv/bin/python scripts/integracion_aislada.py --recrear
    backend/.venv/bin/python scripts/integracion_aislada.py --recrear --con-semilla -- --maxfail=1
    backend/.venv/bin/python scripts/integracion_aislada.py --eliminar

La base de pruebas es independiente de la base de la aplicacion. Este script no
debe apuntar nunca a la base ``postgres`` ni a produccion.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
NOMBRE_BASE_PRUEBAS = "comparador_pruebas"
SEPARADOR = "=" * 68


def cargar_env(ruta: Path) -> None:
    """Carga variables desde ``.env`` sin sobreescribir las ya definidas."""
    if not ruta.exists():
        print(f"[ERROR] No se encontro el archivo .env en: {ruta}")
        sys.exit(1)
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


def url_base() -> str:
    """Retorna la URL de mantenimiento (driver plano) sin la base de la aplicacion."""
    url = os.getenv("MIGRATIONS_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        print("[ERROR] Ni MIGRATIONS_DATABASE_URL ni DATABASE_URL estan definidas en .env")
        sys.exit(1)
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://") :]
    return url


def url_app(url: str) -> str:
    """Convierte una URL plana de PostgreSQL en URL SQLAlchemy asyncpg."""
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def url_con_base(url: str, nombre_base: str) -> str:
    """Reemplaza el nombre de la base en una URL de PostgreSQL."""
    partes = urlsplit(url)
    return urlunsplit(
        (partes.scheme, partes.netloc, f"/{nombre_base}", partes.query, partes.fragment)
    )


def url_ofuscada(url: str) -> str:
    """Retorna una representacion segura de la URL sin contrasena."""
    partes = urlsplit(url)
    usuario = partes.username or ""
    seguro = f"{usuario}:***" if partes.password else usuario
    host = partes.hostname or ""
    if partes.port:
        host = f"{host}:{partes.port}"
    netloc = f"{seguro}@{host}" if seguro else host
    return urlunsplit((partes.scheme, netloc, partes.path, "", ""))


def validar_nombre_base(nombre_base: str) -> None:
    """Impide operar sobre la base de la aplicacion por error."""
    if nombre_base != NOMBRE_BASE_PRUEBAS:
        raise SystemExit(
            f"[ERROR] Nombre de base no permitido: {nombre_base!r}. "
            f"El unico valor valido es {NOMBRE_BASE_PRUEBAS!r}."
        )


async def crear_base(url_mantenimiento: str, recrear: bool) -> str:
    """Crea la base de pruebas y retorna su URL."""
    validar_nombre_base(NOMBRE_BASE_PRUEBAS)
    dsn_pruebas = url_con_base(url_mantenimiento, NOMBRE_BASE_PRUEBAS)
    conexion = await asyncpg.connect(dsn=url_mantenimiento, statement_cache_size=0)
    try:
        existe = await conexion.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1;", NOMBRE_BASE_PRUEBAS
        )
        if existe and not recrear:
            print(f"[INFO] La base {NOMBRE_BASE_PRUEBAS} ya existe; se reutiliza.")
            return dsn_pruebas

        if existe:
            print(f"[*] Cerrando conexiones y eliminando {NOMBRE_BASE_PRUEBAS}...")
            await conexion.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = $1 AND pid <> pg_backend_pid();
                """,
                NOMBRE_BASE_PRUEBAS,
            )
            await conexion.execute(f'DROP DATABASE IF EXISTS "{NOMBRE_BASE_PRUEBAS}";')

        await conexion.execute(f'CREATE DATABASE "{NOMBRE_BASE_PRUEBAS}";')
        print(f"[OK] Base {NOMBRE_BASE_PRUEBAS} creada en {url_ofuscada(dsn_pruebas)}")
        return dsn_pruebas
    finally:
        await conexion.close()


async def eliminar_base(url_mantenimiento: str) -> None:
    """Elimina la base de pruebas y sus conexiones activas."""
    validar_nombre_base(NOMBRE_BASE_PRUEBAS)
    conexion = await asyncpg.connect(dsn=url_mantenimiento, statement_cache_size=0)
    try:
        await conexion.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid();
            """,
            NOMBRE_BASE_PRUEBAS,
        )
        await conexion.execute(f'DROP DATABASE IF EXISTS "{NOMBRE_BASE_PRUEBAS}";')
        print(f"[OK] Base {NOMBRE_BASE_PRUEBAS} eliminada.")
    finally:
        await conexion.close()


def entorno_pruebas(dsn_pruebas: str) -> dict[str, str]:
    """Construye el entorno de los subprocesos apuntando a la base aislada.

    ``DATABASE_URL`` usa el driver asyncpg que espera SQLAlchemy; los scripts de
    migracion reciben la URL plana compatible con asyncpg directo.
    """
    entorno = dict(os.environ)
    entorno["DATABASE_URL"] = url_app(dsn_pruebas)
    entorno["MIGRATIONS_DATABASE_URL"] = dsn_pruebas
    entorno["ENTORNO"] = "pruebas"
    return entorno


def ejecutar(comando: list[str], entorno: dict[str, str], cwd: Path) -> int:
    """Ejecuta un subproceso mostrando su salida y retorna el codigo de salida."""
    print(f"[*] Ejecutando: {' '.join(comando)}")
    # El comando se construye internamente con sys.executable y rutas del repo.
    proceso = subprocess.run(comando, cwd=cwd, env=entorno, check=False)  # noqa: S603
    return proceso.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta la suite de integracion en una base aislada de Supabase."
    )
    parser.add_argument(
        "--recrear",
        action="store_true",
        help="Elimina y vuelve a crear la base de pruebas antes de migrar.",
    )
    parser.add_argument(
        "--con-semilla",
        action="store_true",
        help="Ejecuta scripts/semilla.py antes de las pruebas.",
    )
    parser.add_argument(
        "--mantener",
        action="store_true",
        help="No elimina la base al terminar (util para depurar).",
    )
    parser.add_argument(
        "--eliminar",
        action="store_true",
        help="Solo elimina la base de pruebas y termina.",
    )
    parser.add_argument(
        "--solo-preparar",
        action="store_true",
        help="Crea la base y aplica migraciones, sin ejecutar pytest.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Argumentos adicionales para pytest (despues de --).",
    )
    args = parser.parse_args()

    print(SEPARADOR)
    print(" Integracion aislada — base comparador_pruebas")
    print(SEPARADOR)

    cargar_env(RAIZ / ".env")
    dsn_mantenimiento = url_base()

    if args.eliminar:
        asyncio.run(eliminar_base(dsn_mantenimiento))
        return

    dsn_pruebas = asyncio.run(crear_base(dsn_mantenimiento, recrear=args.recrear))
    entorno = entorno_pruebas(dsn_pruebas)

    codigo_migraciones = ejecutar(
        [sys.executable, str(RAIZ / "scripts" / "migrar.py")],
        entorno,
        RAIZ,
    )
    if codigo_migraciones != 0:
        print("[ERROR] Las migraciones fallaron; no se ejecutan las pruebas.")
        sys.exit(codigo_migraciones)

    if args.con_semilla:
        codigo_semilla = ejecutar(
            [sys.executable, str(RAIZ / "scripts" / "semilla.py")],
            entorno,
            RAIZ,
        )
        if codigo_semilla != 0:
            print("[ERROR] La semilla fallo; no se ejecutan las pruebas.")
            sys.exit(codigo_semilla)

    if args.solo_preparar:
        print(f"[OK] Base preparada. Mantenida: {'si' if args.mantener else 'no'}")
        if not args.mantener:
            asyncio.run(eliminar_base(dsn_mantenimiento))
        return

    argumentos_pytest = [arg for arg in args.pytest_args if arg != "--"]
    comando = [sys.executable, "-m", "pytest", "tests/integracion", "-q", *argumentos_pytest]
    codigo_pruebas = ejecutar(comando, entorno, BACKEND)

    if codigo_pruebas == 0 and not args.mantener:
        asyncio.run(eliminar_base(dsn_mantenimiento))
    elif codigo_pruebas != 0:
        print(
            f"\n[AVISO] La base {NOMBRE_BASE_PRUEBAS} se conserva para depuracion.\n"
            "        Para eliminarla: backend/.venv/bin/python "
            "scripts/integracion_aislada.py --eliminar"
        )

    print(SEPARADOR)
    print(f" Resultado: {'EXITO' if codigo_pruebas == 0 else 'FALLO'}")
    print(SEPARADOR)
    sys.exit(codigo_pruebas)


if __name__ == "__main__":
    main()
