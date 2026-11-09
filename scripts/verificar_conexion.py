#!/usr/bin/env python3
"""Script de verificacion de conexion en vivo con Supabase y Upstash Redis.

Este script valida la conectividad asincrona con PostgreSQL y el comando PING en Redis
respetando estrictamente la privacidad y seguridad: NUNCA imprime contraseñas ni secretos.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

SEPARADOR_DOBLE = "=" * 68
SEPARADOR_SIMPLE = "-" * 68


def cargar_env(ruta_env: Path) -> None:
    """Carga variables desde el archivo .env sin imprimir valores sensibles."""
    if not ruta_env.exists():
        print(f"[ERROR] No se encontro el archivo .env en: {ruta_env}")
        sys.exit(1)

    with open(ruta_env, "r", encoding="utf-8") as f:
        for num_linea, linea in enumerate(f, start=1):
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
    """Retorna una representacion segura de una URL de conexion sin contraseñas."""
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


async def verificar_postgres(nombre_var: str, url: str) -> bool:
    """Prueba la conexion asincrona a PostgreSQL en Supabase ejecutando una consulta real."""
    print(f"\n[*] Probando conexion asincrona a PostgreSQL ({nombre_var})...")
    print(f"    Destino: {ofuscar_url(url)}")

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    connect_args: dict[str, int] = {}
    if ":6543" in url:
        # Requerido para Transaction Pooler en Supabase (ADR-012)
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0

    engine = None
    try:
        engine = create_async_engine(
            url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        async with engine.connect() as conn:
            resultado = await conn.execute(text("SELECT version();"))
            version = resultado.scalar()
            res_num = await conn.execute(text("SELECT 1;"))
            num = res_num.scalar()
            if num == 1:
                version_corta = (str(version).split(",")[0] if version else "PostgreSQL").strip()
                print(f"    [OK] Conexion exitosa. Version: {version_corta}")
                return True
            else:
                print(f"    [ERROR] Consulta SELECT 1 devolvio: {num}")
                return False
    except Exception as exc:
        print(f"    [ERROR] Fallo la conexion a PostgreSQL ({nombre_var}): {exc}")
        return False
    finally:
        if engine is not None:
            await engine.dispose()


async def verificar_redis(url: str) -> bool:
    """Prueba la conexion a Upstash Redis ejecutando un PING."""
    print("\n[*] Probando conexion a Upstash Redis (comando PING)...")
    print(f"    Destino: {ofuscar_url(url)}")

    import redis.asyncio as aioredis

    cliente = None
    try:
        cliente = aioredis.from_url(
            url,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
        )
        respuesta = await cliente.ping()
        if respuesta is True or respuesta == "PONG":
            print("    [OK] PING respondio PONG exitosamente.")
            return True
        else:
            print(f"    [ERROR] Respuesta inesperada del PING: {respuesta}")
            return False
    except Exception as exc:
        print(f"    [ERROR] Fallo la conexion a Redis: {exc}")
        return False
    finally:
        if cliente is not None:
            await cliente.aclose()


async def main() -> int:
    print(SEPARADOR_DOBLE)
    print(" Verificacion de Conectividad en Vivo (Supabase y Upstash Redis)")
    print(SEPARADOR_DOBLE)

    raiz = Path(__file__).resolve().parent.parent
    ruta_env = raiz / ".env"
    cargar_env(ruta_env)

    database_url = os.getenv("DATABASE_URL")
    migrations_url = os.getenv("MIGRATIONS_DATABASE_URL")
    redis_url = os.getenv("REDIS_URL")

    if not database_url:
        print("[ERROR] DATABASE_URL no esta definida en el archivo .env")
        return 1

    if not redis_url:
        print("[ERROR] REDIS_URL no esta definida en el archivo .env")
        return 1

    todo_ok = True

    # 1. Verificar DATABASE_URL
    ok_db = await verificar_postgres("DATABASE_URL", database_url)
    if not ok_db:
        todo_ok = False

    # 2. Verificar MIGRATIONS_DATABASE_URL si esta definida y es distinta
    if migrations_url and migrations_url != database_url:
        ok_mig = await verificar_postgres("MIGRATIONS_DATABASE_URL", migrations_url)
        if not ok_mig:
            todo_ok = False

    # 3. Verificar Upstash Redis
    ok_redis = await verificar_redis(redis_url)
    if not ok_redis:
        todo_ok = False

    print(f"\n{SEPARADOR_SIMPLE}")
    if todo_ok:
        print("[EXITO] Todas las conexiones a servicios externos estan operativas.")
        print(SEPARADOR_DOBLE)
        return 0
    else:
        print("[FALLO] Una o mas conexiones fallaron. Revisa tus credenciales en .env.")
        print(SEPARADOR_DOBLE)
        return 1


if __name__ == "__main__":
    codigo = asyncio.run(main())
    sys.exit(codigo)

