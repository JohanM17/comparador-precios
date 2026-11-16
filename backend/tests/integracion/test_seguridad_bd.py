"""Pruebas de integracion de seguridad y privilegios minimos de base de datos.

Verifica:
1. Extensiones requeridas (postgis, pg_trgm, unaccent, pgcrypto).
2. Existencia del rol app_backend.
3. Existencia de la funcion de trigger actualizar_columna_timestamp.
4. Revocacion efectiva de privilegios sobre tablas publicas a anon y authenticated.
5. Permisos de lectura y escritura para el rol app_backend.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
import pytest


def _obtener_dsn() -> str:
    """Obtiene y formatea el DSN de conexion desde el archivo .env."""
    raiz = Path(__file__).resolve().parent.parent.parent.parent
    ruta_env = raiz / ".env"
    if ruta_env.exists():
        with open(ruta_env, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                clave, valor = linea.split("=", 1)
                clave = clave.strip()
                valor = valor.strip().strip("'\"")
                if clave not in os.environ:
                    os.environ[clave] = valor

    url = os.getenv("MIGRATIONS_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        pytest.fail("Ni MIGRATIONS_DATABASE_URL ni DATABASE_URL estan definidas en .env")

    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://") :]
    return url


@pytest.fixture
async def conexion_bd() -> AsyncGenerator[asyncpg.Connection, None]:
    """Fixture que provee una conexion directa asincrona con statement_cache_size=0."""
    dsn = _obtener_dsn()
    conn = await asyncpg.connect(dsn=dsn, statement_cache_size=0)
    try:
        yield conn
    finally:
        await conn.close()


async def test_extensiones_instaladas(conexion_bd: asyncpg.Connection) -> None:
    """Verifica que las extensiones postgis, pg_trgm, unaccent y pgcrypto esten activas."""
    extensiones_esperadas = {"postgis", "pg_trgm", "unaccent", "pgcrypto"}
    filas = await conexion_bd.fetch(
        "SELECT extname FROM pg_extension WHERE extname = ANY($1::text[]);",
        list(extensiones_esperadas),
    )
    instaladas = {fila["extname"] for fila in filas}
    faltantes = extensiones_esperadas - instaladas
    assert not faltantes, f"Faltan extensiones por instalar: {faltantes}"


async def test_rol_app_backend_existe(conexion_bd: asyncpg.Connection) -> None:
    """Verifica que el rol de aplicacion app_backend exista en pg_roles."""
    fila = await conexion_bd.fetchrow("SELECT rolname FROM pg_roles WHERE rolname = 'app_backend';")
    assert fila is not None, "El rol 'app_backend' no existe en pg_roles"
    assert fila["rolname"] == "app_backend"


async def test_funcion_actualizar_timestamp_existe(conexion_bd: asyncpg.Connection) -> None:
    """Verifica que la funcion de trigger actualizar_columna_timestamp exista."""
    fila = await conexion_bd.fetchrow(
        """
        SELECT proname, prosecdef
        FROM pg_proc
        JOIN pg_namespace ON pg_namespace.oid = pg_proc.pronamespace
        WHERE pg_namespace.nspname = 'public'
          AND pg_proc.proname = 'actualizar_columna_timestamp';
        """
    )
    assert fila is not None, "La funcion 'actualizar_columna_timestamp' no existe en schema public"


async def test_seguridad_privilegios_roles(conexion_bd: asyncpg.Connection) -> None:
    """Verifica revocacion de tablas a anon/authenticated y operacion de app_backend."""
    # Preparar tabla de prueba
    await conexion_bd.execute("DROP TABLE IF EXISTS public._test_seguridad_privilegios;")
    await conexion_bd.execute(
        """
        CREATE TABLE public._test_seguridad_privilegios (
            id SERIAL PRIMARY KEY,
            clave VARCHAR(50) NOT NULL,
            actualizado_en TIMESTAMPTZ DEFAULT now()
        );
        """
    )

    try:
        # 1. Probar que app_backend puede insertar, leer, actualizar y borrar
        async with conexion_bd.transaction():
            await conexion_bd.execute("SET LOCAL ROLE app_backend;")
            await conexion_bd.execute(
                "INSERT INTO public._test_seguridad_privilegios (clave) VALUES ('dato_backend');"
            )
            fila = await conexion_bd.fetchrow(
                "SELECT clave FROM public._test_seguridad_privilegios WHERE clave = 'dato_backend';"
            )
            assert fila is not None
            assert fila["clave"] == "dato_backend"

            await conexion_bd.execute(
                "UPDATE public._test_seguridad_privilegios "
                "SET clave = 'dato_modificado' WHERE clave = 'dato_backend';"
            )
            fila_upd = await conexion_bd.fetchrow(
                "SELECT clave FROM public._test_seguridad_privilegios "
                "WHERE clave = 'dato_modificado';"
            )
            assert fila_upd is not None
            assert fila_upd["clave"] == "dato_modificado"

            await conexion_bd.execute(
                "DELETE FROM public._test_seguridad_privilegios WHERE clave = 'dato_modificado';"
            )

        # 2. Probar que el rol anon TIENE DENEGADO el SELECT
        async with conexion_bd.transaction():
            await conexion_bd.execute("SET LOCAL ROLE anon;")
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await conexion_bd.fetch("SELECT * FROM public._test_seguridad_privilegios;")

        # 3. Probar que el rol anon TIENE DENEGADO el INSERT
        async with conexion_bd.transaction():
            await conexion_bd.execute("SET LOCAL ROLE anon;")
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await conexion_bd.execute(
                    "INSERT INTO public._test_seguridad_privilegios (clave) "
                    "VALUES ('intruso_anon');"
                )

        # 4. Probar que el rol authenticated TIENE DENEGADO el SELECT
        async with conexion_bd.transaction():
            await conexion_bd.execute("SET LOCAL ROLE authenticated;")
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await conexion_bd.fetch("SELECT * FROM public._test_seguridad_privilegios;")

        # 5. Probar que el rol authenticated TIENE DENEGADO el INSERT
        async with conexion_bd.transaction():
            await conexion_bd.execute("SET LOCAL ROLE authenticated;")
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await conexion_bd.execute(
                    "INSERT INTO public._test_seguridad_privilegios (clave) "
                    "VALUES ('intruso_auth');"
                )

    finally:
        await conexion_bd.execute("DROP TABLE IF EXISTS public._test_seguridad_privilegios;")
