"""Configuracion del motor de base de datos asincrono y gestion de sesiones."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import obtener_configuracion

_motores: dict[asyncio.AbstractEventLoop, tuple[AsyncEngine, async_sessionmaker[AsyncSession]]] = {}


def _obtener_recursos_bd() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Crea o reutiliza los recursos de BD enlazados al event loop actual."""
    bucle = asyncio.get_running_loop()
    if bucle not in _motores:
        cfg = obtener_configuracion()
        url = cfg.DATABASE_URL or cfg.MIGRATIONS_DATABASE_URL
        if not url:
            raise RuntimeError("DATABASE_URL no esta configurada en las variables de entorno.")

        connect_args: dict[str, Any] = {}
        # Compatibilidad con Supavisor (puerto 6543 o 5432 con pooling)
        if ":6543" in url or ":5432" in url:
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_cache_size"] = 0

        motor = create_async_engine(
            url,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=False,
        )
        creador = async_sessionmaker(
            bind=motor,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        _motores[bucle] = (motor, creador)
    return _motores[bucle]


def obtener_motor() -> AsyncEngine:
    """Obtiene el motor de base de datos asincrono para el event loop en curso."""
    motor, _ = _obtener_recursos_bd()
    return motor


def obtener_creador_sesiones() -> async_sessionmaker[AsyncSession]:
    """Retorna el creador de sesiones asincrono inicializado."""
    _, creador = _obtener_recursos_bd()
    return creador


async def obtener_sesion() -> AsyncGenerator[AsyncSession, None]:
    """Generador de sesiones transaccionales con rol de aplicacion app_backend."""
    session_factory = obtener_creador_sesiones()
    async with session_factory() as session, session.begin():
        # Aislamiento de privilegios minimos verificado en T-02 (ADR-012)
        await session.execute(text("SET LOCAL ROLE app_backend;"))
        yield session


async def verificar_conexion_bd() -> bool:
    """Verifica si la base de datos responde a una consulta elemental SELECT 1."""
    try:
        motor = obtener_motor()
        async with motor.connect() as conn:
            resultado = await conn.execute(text("SELECT 1;"))
            return resultado.scalar() == 1
    except Exception:
        return False


async def cerrar_conexiones() -> None:
    """Libera el pool de conexiones del bucle de eventos actual."""
    bucle = asyncio.get_running_loop()
    recursos = _motores.pop(bucle, None)
    if recursos is not None:
        motor, _ = recursos
        await motor.dispose()
