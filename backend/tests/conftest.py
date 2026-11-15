"""Configuracion global de fixtures para la suite de pruebas del backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio

from app.bd import cerrar_conexiones


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cerrar_pool_al_finalizar_sesion() -> AsyncGenerator[None, None]:
    """Garantiza el cierre limpio del pool de Supabase al terminar pytest."""
    yield
    await cerrar_conexiones()
