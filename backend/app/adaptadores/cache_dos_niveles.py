"""Adaptador concreto de cache de dos niveles L1 (RAM) y L2 (Upstash Redis) para T-25."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.config import obtener_configuracion
from app.puertos.cache import PuertoCache

logger = logging.getLogger("app.cache")


class CacheDosNiveles(PuertoCache):
    """Implementa cache L1 en proceso (5 s) y L2 en Redis (60 s) con degradacion elegante."""

    def __init__(self, ttl_l1_segundos: float = 5.0, cliente_redis: Any = None) -> None:
        self.ttl_l1_segundos = ttl_l1_segundos
        self._l1: dict[str, tuple[float, dict[str, Any]]] = {}
        self._cliente_redis = cliente_redis
        self.cfg = obtener_configuracion()

    async def _obtener_cliente_redis(self) -> Any:
        if self._cliente_redis is not None:
            return self._cliente_redis

        if not self.cfg.REDIS_URL:
            return None

        import redis.asyncio as aioredis

        try:
            self._cliente_redis = aioredis.from_url(  # type: ignore[no-untyped-call]
                self.cfg.REDIS_URL,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
                decode_responses=True,
            )
            return self._cliente_redis
        except Exception as exc:  # noqa: S110
            logger.warning("No fue posible conectar a Redis para L2: %s", exc)
            return None

    def _es_fresco(self, datos: dict[str, Any], max_edad_segundos: float = 60.0) -> bool:
        """Valida que (ahora - generado_en) <= 60 s segun EC-02."""
        meta = datos.get("datos", {}).get("meta", {}) or datos.get("meta", {})
        generado_en_str = meta.get("generado_en")
        if not generado_en_str:
            return True

        try:
            generado_en = datetime.fromisoformat(str(generado_en_str).replace("Z", "+00:00"))
            ahora = datetime.now(UTC)
            return (ahora - generado_en).total_seconds() <= max_edad_segundos
        except Exception:
            return False

    async def obtener(
        self,
        producto_id: UUID | str,
        subllave: str,
    ) -> dict[str, Any] | None:
        p_id = str(producto_id)
        clave_l1 = f"{p_id}:{subllave}"
        ahora = time.time()

        # 1. Verificacion en L1 (RAM del proceso)
        if clave_l1 in self._l1:
            expira, datos = self._l1[clave_l1]
            if ahora < expira and self._es_fresco(datos):
                return datos
            self._l1.pop(clave_l1, None)

        # 2. Verificacion en L2 (Upstash Redis)
        try:
            cliente = await self._obtener_cliente_redis()
            if cliente is not None:
                val_raw = await cliente.hget(f"cmp:{p_id}", subllave)
                if val_raw:
                    datos_redis = json.loads(val_raw)
                    if isinstance(datos_redis, dict) and self._es_fresco(datos_redis):
                        # Promover a L1
                        self._l1[clave_l1] = (ahora + self.ttl_l1_segundos, datos_redis)
                        return datos_redis
        except Exception as exc:  # noqa: S110
            # ADR-015 y ADR-016: Redis fuera del camino critico, falla graciosamente
            logger.warning("Fallo al consultar L2 en Redis para producto %s: %s", p_id, exc)

        return None

    async def guardar(
        self,
        producto_id: UUID | str,
        subllave: str,
        datos: dict[str, Any],
        ttl_segundos: int = 60,
    ) -> None:
        p_id = str(producto_id)
        clave_l1 = f"{p_id}:{subllave}"
        ahora = time.time()

        # Guardar en L1
        self._l1[clave_l1] = (ahora + self.ttl_l1_segundos, datos)

        # Guardar en L2
        try:
            cliente = await self._obtener_cliente_redis()
            if cliente is not None:
                clave_redis = f"cmp:{p_id}"
                await cliente.hset(clave_redis, subllave, json.dumps(datos))
                await cliente.expire(clave_redis, ttl_segundos)
        except Exception as exc:  # noqa: S110
            logger.warning("Fallo al escribir en L2 en Redis para producto %s: %s", p_id, exc)

    async def invalidar_producto(self, producto_id: UUID | str) -> None:
        p_id = str(producto_id)
        prefijo_l1 = f"{p_id}:"

        # Limpiar L1
        a_borrar = [k for k in self._l1 if k.startswith(prefijo_l1)]
        for k in a_borrar:
            self._l1.pop(k, None)

        # Limpiar L2 en Redis
        try:
            cliente = await self._obtener_cliente_redis()
            if cliente is not None:
                await cliente.delete(f"cmp:{p_id}")
        except Exception as exc:  # noqa: S110
            logger.warning("Fallo al invalidar L2 en Redis para producto %s: %s", p_id, exc)

    async def limpiar(self) -> None:
        self._l1.clear()
        if self._cliente_redis is not None:
            try:
                await self._cliente_redis.aclose()
            except Exception:  # noqa: S110
                pass
            self._cliente_redis = None
