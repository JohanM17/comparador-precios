"""Prueba de integracion EC-02: 100 repeticiones de actualidad de precio (T-54)."""

from __future__ import annotations

import json
import math
import statistics
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.adaptadores.cache_dos_niveles import CacheDosNiveles
from app.main import app
from app.modulos.precios.api import obtener_puerto_cache
from app.modulos.precios.servicio import limitador_escritura
from tests.integracion.ayudantes_ec02 import (
    desactivar_escenario_ec02,
    preparar_escenario_ec02,
)

URL_COMPARACION = "/v1/productos/{prod_id}/comparacion"


class _RedisMemoriaEC02:
    """Mock L2 en memoria para no consumir cuota de Upstash durante EC-02."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}

    async def hget(self, clave: str, campo: str) -> str | None:
        return self._hashes.get(clave, {}).get(campo)

    async def hset(self, clave: str, campo: str, valor: str) -> int:
        self._hashes.setdefault(clave, {})[campo] = valor
        return 1

    async def expire(self, _clave: str, _ttl: int) -> bool:
        return True

    async def delete(self, *claves: str) -> int:
        return sum(1 for c in claves if self._hashes.pop(c, None) is not None)

    async def aclose(self) -> None:
        self._hashes.clear()


def _percentil(ordenados: list[float], p: float) -> float:
    idx = max(0, min(len(ordenados) - 1, math.ceil(len(ordenados) * p) - 1))
    return ordenados[idx]


def _extraer_precio_tienda(cuerpo: dict[str, Any], est_id: str) -> int | None:
    for item in cuerpo["datos"]["resultados"]:
        if item["establecimiento"]["id"] == est_id:
            return int(item["precio_cop"])
    return None


async def _ejecutar_cambio_y_medir(
    cli: AsyncClient,
    ruta_cmp: str,
    par: dict[str, str | None],
    tok_alto: str,
    tok_mod: str,
    idx: int,
) -> float:
    pres_id = str(par["pres_id"])
    est_id = str(par["est_id"])
    caso_id = par["caso_id"]
    params = {"orden": "precio_unitario", "presentacion_id": pres_id}

    warm = await cli.get(ruta_cmp, params=params)
    assert warm.status_code == 200
    assert _extraer_precio_tienda(warm.json(), est_id) == 5000

    inicio = time.perf_counter()
    if caso_id is None:
        limitador_escritura.limpiar()
        r_w = await cli.post(
            "/v1/reportes",
            headers={"Authorization": f"Bearer {tok_alto}", "Idempotency-Key": str(uuid4())},
            json={
                "presentacion_id": pres_id,
                "establecimiento_id": est_id,
                "precio_cop": 4800,
                "observado_en": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "foto_ruta": None,
            },
        )
        assert r_w.status_code == 201, r_w.text
        esperado = 4800
    else:
        r_m = await cli.post(
            f"/v1/moderacion/casos/{caso_id}/resolver",
            headers={"Authorization": f"Bearer {tok_mod}"},
            json={"decision": "descartar", "nota": f"EC-02 validacion ciclo {idx}"},
        )
        assert r_m.status_code == 200, r_m.text
        esperado = 4700

    actual: int | None = 5000
    while actual == 5000 and (time.perf_counter() - inicio) <= 60.0:
        r_cmp = await cli.get(ruta_cmp, params=params)
        assert r_cmp.status_code == 200
        actual = _extraer_precio_tienda(r_cmp.json(), est_id)

    duracion_ms = (time.perf_counter() - inicio) * 1000.0
    assert actual == esperado, f"Ciclo {idx}: esperado {esperado}, obtenido {actual}"
    return duracion_ms


@pytest.mark.asyncio
async def test_ec02_actualidad_100_repeticiones() -> None:
    """Certifica que 100/100 cambios de precio vigente se reflejan en <= 60 s."""
    datos = await preparar_escenario_ec02()
    cache_mem = CacheDosNiveles(ttl_l1_segundos=60.0, cliente_redis=_RedisMemoriaEC02())
    prev = app.dependency_overrides.get(obtener_puerto_cache)
    app.dependency_overrides[obtener_puerto_cache] = lambda: cache_mem
    tiempos_ms: list[float] = []

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
            ruta_cmp = URL_COMPARACION.format(prod_id=datos["prod_id"])
            for idx, par in enumerate(datos["pares"]):
                duracion_ms = await _ejecutar_cambio_y_medir(
                    cli, ruta_cmp, par, datos["tok_alto"], datos["tok_mod"], idx
                )
                tiempos_ms.append(duracion_ms)
    finally:
        if prev is not None:
            app.dependency_overrides[obtener_puerto_cache] = prev
        else:
            app.dependency_overrides.pop(obtener_puerto_cache, None)
        await desactivar_escenario_ec02(datos)

    ordenados = sorted(tiempos_ms)
    resumen = {
        "repeticiones": len(ordenados),
        "cumplimiento_pct": 100.0 if all(t <= 60_000.0 for t in ordenados) else 0.0,
        "min_ms": round(ordenados[0], 2),
        "media_ms": round(statistics.mean(ordenados), 2),
        "p95_ms": round(_percentil(ordenados, 0.95), 2),
        "p99_ms": round(_percentil(ordenados, 0.99), 2),
        "max_ms": round(ordenados[-1], 2),
    }
    print(f"\n[EC-02 METRICAS] {json.dumps(resumen)}")
    assert len(ordenados) == 100
    assert resumen["max_ms"] <= 60_000.0
