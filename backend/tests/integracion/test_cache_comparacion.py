"""Pruebas de integracion y resiliencia para el cache de dos niveles L1/L2 (T-25)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.adaptadores.cache_dos_niveles import CacheDosNiveles


class ClienteRedisMemoria:
    """Mock en memoria de Redis para validar L1/L2 sin gastar cuota en Upstash."""

    def __init__(self) -> None:
        self.almacen: dict[str, dict[str, str]] = {}

    async def hget(self, key: str, field: str) -> str | None:
        return self.almacen.get(key, {}).get(field)

    async def hset(self, key: str, field: str, value: str) -> int:
        if key not in self.almacen:
            self.almacen[key] = {}
        self.almacen[key][field] = value
        return 1

    async def delete(self, key: str) -> int:
        return 1 if self.almacen.pop(key, None) is not None else 0

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def aclose(self) -> None:
        self.almacen.clear()


class ClienteRedisFallido:
    """Simula una caida o timeout de Upstash Redis."""

    async def hget(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("Timeout al conectar a Redis en la nube")

    async def hset(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("Fallo de red hacia Redis")

    async def delete(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("Redis no responde")

    async def expire(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("Redis no responde")


@pytest.mark.asyncio
async def test_cache_dos_niveles_acierto_l1_e_invalidacion() -> None:
    redis_mem = ClienteRedisMemoria()
    cache = CacheDosNiveles(ttl_l1_segundos=10.0, cliente_redis=redis_mem)
    prod_id = uuid4()
    subllave = "armenia:todas:precio_unitario"

    ahora_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    datos: dict[str, Any] = {
        "datos": {
            "producto": {"id": str(prod_id), "nombre": "Cafe Quindio"},
            "resultados": [],
            "promociones": [],
            "meta": {"generado_en": ahora_iso},
        }
    }

    # 1. Guardar y comprobar acierto en L1 y L2
    await cache.guardar(prod_id, subllave, datos, ttl_segundos=60)
    obtenido = await cache.obtener(prod_id, subllave)
    assert obtenido is not None
    assert obtenido["datos"]["producto"]["nombre"] == "Cafe Quindio"

    # Verificar presencia en L2
    clave_redis = f"cmp:{prod_id}"
    assert clave_redis in redis_mem.almacen

    # 2. Invalidar producto
    await cache.invalidar_producto(prod_id)
    post_inval = await cache.obtener(prod_id, subllave)
    assert post_inval is None
    assert clave_redis not in redis_mem.almacen


@pytest.mark.asyncio
async def test_cache_descarta_datos_mayores_a_60_segundos_ec02() -> None:
    redis_mem = ClienteRedisMemoria()
    cache = CacheDosNiveles(ttl_l1_segundos=10.0, cliente_redis=redis_mem)
    prod_id = uuid4()
    subllave = "armenia:todas:precio_unitario"

    # Generado hace 70 segundos (obsoleto segun EC-02)
    hace_70s = (datetime.now(UTC) - timedelta(seconds=70)).strftime("%Y-%m-%dT%H:%M:%SZ")
    datos_viejos: dict[str, Any] = {
        "datos": {
            "producto": {"id": str(prod_id), "nombre": "Panela"},
            "meta": {"generado_en": hace_70s},
        }
    }

    await cache.guardar(prod_id, subllave, datos_viejos, ttl_segundos=60)
    obtenido = await cache.obtener(prod_id, subllave)
    assert obtenido is None


@pytest.mark.asyncio
async def test_cache_degradacion_elegante_falla_redis() -> None:
    redis_mock = ClienteRedisFallido()
    cache = CacheDosNiveles(ttl_l1_segundos=0.01, cliente_redis=redis_mock)
    prod_id = uuid4()
    subllave = "armenia:todas:precio_unitario"

    # No debe lanzar excepcion 500, degrada silenciosamente retornando None
    obtenido = await cache.obtener(prod_id, subllave)
    assert obtenido is None

    # Guardar tampoco debe explotar
    ahora_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    await cache.guardar(
        prod_id,
        subllave,
        {"datos": {"meta": {"generado_en": ahora_iso}}},
    )
