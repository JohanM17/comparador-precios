"""Certificacion de EC-02 con precio oficial y EC-06 con promociones activas (T-68).

La prueba se ejecuta en la base aislada `comparador_pruebas` a traves de
`scripts/integracion_aislada.py`. Cubre tres frentes:

1. La migracion `0007_diferencia_pct_amplia.sql`: un contraste valido de
   $1.000 contra $200.000 produce 199,0000 y debe caber en
   `precio_vigente.diferencia_pct` sin desbordar.
2. EC-02 con precio oficial: 100 comparaciones consecutivas deben devolver el
   precio publicado por el comercio, con sello `oficial`, y un p95 <= 60 s.
3. EC-06 con promociones activas: el orden de `resultados` debe ser identico
   con y sin promociones, y las promociones deben viajar en el bloque separado
   `promociones`. La frontera que lo hace posible la verifica `lint-imports`
   («Precios nunca importa el modulo comercial»), que corre en la misma
   verificacion de T-68.

Cada escenario usa identificadores unicos y limpia lo que crea. El contraste
de la migracion se ejecuta en una transaccion que termina en rollback porque
`reporte_precio` es inmutable por diseno (sus triggers prohiben DELETE).

Requiere la semilla de `scripts/semilla.py` (categoria_id=1) y una base aislada
creada con `scripts/integracion_aislada.py --con-semilla`.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.bd import obtener_creador_sesiones, sesion_transaccional
from app.compartido.dependencias import obtener_puerto_cache
from app.main import app
from app.puertos.politica_precio import OficialConContraste

URL_COMPARACION = "/v1/productos/{prod_id}/comparacion"
PRECIO_OFICIAL_EC02 = 1250
PRECIO_COMUNIDAD_CONTRASTE = 200_000
PRECIO_OFICIAL_CONTRASTE = 1_000


class CacheMemoria:
    """Cache L1 en RAM para no consumir la cuota de Upstash durante T-68."""

    def __init__(self) -> None:
        self._datos: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _clave(producto_id: UUID | str, subllave: str) -> str:
        return f"{producto_id}:{subllave}"

    async def obtener(self, producto_id: UUID | str, subllave: str) -> dict[str, Any] | None:
        return self._datos.get(self._clave(producto_id, subllave))

    async def guardar(
        self,
        producto_id: UUID | str,
        subllave: str,
        datos: dict[str, Any],
        ttl_segundos: int = 60,
    ) -> None:
        self._datos[self._clave(producto_id, subllave)] = datos

    async def invalidar_producto(self, producto_id: UUID | str) -> None:
        prefijo = f"{producto_id}:"
        for clave in [k for k in self._datos if k.startswith(prefijo)]:
            self._datos.pop(clave, None)

    async def limpiar(self) -> None:
        self._datos.clear()


def _percentil(ordenados: list[float], p: float) -> float:
    """Percentil por rango mas cercano, igual que la prueba EC-02 del nucleo."""
    idx = max(0, min(len(ordenados) - 1, math.ceil(len(ordenados) * p) - 1))
    return ordenados[idx]


def _sufijo() -> str:
    return uuid4().hex[:10]


async def _exigir_base_aislada() -> None:
    """Evita que T-68 escriba por accidente en la base compartida."""
    async with sesion_transaccional() as sesion:
        nombre = (await sesion.execute(text("SELECT current_database();"))).scalar_one()
    if nombre != "comparador_pruebas":
        pytest.skip(f"T-68 solo escribe en comparador_pruebas; base actual: {nombre}.")


async def _insertar_catalogo(
    sesion: Any,
    sufijo: str,
    *,
    n_establecimientos: int,
    n_perfiles: int,
) -> dict[str, Any]:
    """Inserta un producto, una presentacion, tiendas y perfiles unicos."""
    producto_id = (
        await sesion.execute(
            text("""
                INSERT INTO public.producto
                    (nombre, nombre_norm, categoria_id, unidad_base)
                VALUES (:nombre, :nombre_norm, 1, 'g')
                RETURNING id;
            """),
            {"nombre": f"T68 {sufijo}", "nombre_norm": f"t68 {sufijo}"},
        )
    ).scalar_one()
    presentacion_id = (
        await sesion.execute(
            text("""
                INSERT INTO public.presentacion
                    (producto_id, marca, valor_cantidad, unidad, multiplicador,
                     cantidad_base, etiqueta, etiqueta_norm)
                VALUES (:prod, :marca, 1000, 'g', 1, 1000, :etiqueta, :etiqueta_norm)
                RETURNING id;
            """),
            {
                "prod": producto_id,
                "marca": f"Marca {sufijo}",
                "etiqueta": f"Paquete T68 {sufijo} 1 kg",
                "etiqueta_norm": f"paquete t68 {sufijo} 1 kg",
            },
        )
    ).scalar_one()

    establecimiento_ids: list[UUID] = []
    for indice in range(n_establecimientos):
        establecimiento_ids.append(
            (
                await sesion.execute(
                    text("""
                        INSERT INTO public.establecimiento
                            (nombre, tipo, direccion, ubicacion)
                        VALUES (
                            :nombre, 'tienda_barrio', :direccion,
                            ST_SetSRID(ST_MakePoint(-75.6811, 4.5339), 4326)::geography
                        )
                        RETURNING id;
                    """),
                    {
                        "nombre": f"Tienda T68 {sufijo} {indice}",
                        "direccion": f"Calle T68 {sufijo} {indice}",
                    },
                )
            ).scalar_one()
        )

    perfiles_ids: list[UUID] = []
    for indice in range(n_perfiles):
        perfil_id = uuid4()
        await sesion.execute(
            text("""
                INSERT INTO public.perfil (id, alias, rol, estado, reputacion)
                VALUES (:id, :alias, 'reportante', 'activa', 0.700);
            """),
            {"id": perfil_id, "alias": f"t68_{sufijo}_{indice}"},
        )
        perfiles_ids.append(perfil_id)

    return {
        "producto_id": producto_id,
        "presentacion_id": presentacion_id,
        "establecimiento_ids": establecimiento_ids,
        "perfiles_ids": perfiles_ids,
    }


async def _limpiar_escenario(datos: dict[str, Any]) -> None:
    """Borra lo creado por un escenario committed, en orden de dependencias."""
    establecimientos = datos["establecimiento_ids"]
    async with sesion_transaccional() as sesion:
        # app_backend no puede borrar reportes; el rol de sesion si puede limpiar
        # las tablas mutables que crea esta prueba.
        await sesion.execute(text("RESET ROLE;"))
        await sesion.execute(
            text("DELETE FROM public.caso_moderacion WHERE referencia_id = :pres;"),
            {"pres": datos["presentacion_id"]},
        )
        await sesion.execute(
            text("DELETE FROM public.precio_vigente WHERE producto_id = :prod;"),
            {"prod": datos["producto_id"]},
        )
        await sesion.execute(
            text("DELETE FROM public.promocion WHERE producto_id = :prod;"),
            {"prod": datos["producto_id"]},
        )
        await sesion.execute(
            text("DELETE FROM public.precio_oficial WHERE producto_id = :prod;"),
            {"prod": datos["producto_id"]},
        )
        await sesion.execute(
            text("DELETE FROM public.presentacion WHERE producto_id = :prod;"),
            {"prod": datos["producto_id"]},
        )
        await sesion.execute(
            text("DELETE FROM public.establecimiento WHERE id = ANY(CAST(:ids AS uuid[]));"),
            {"ids": establecimientos},
        )
        await sesion.execute(
            text("DELETE FROM public.producto WHERE id = :prod;"),
            {"prod": datos["producto_id"]},
        )
        await sesion.execute(
            text("DELETE FROM public.perfil WHERE id = ANY(CAST(:ids AS uuid[]));"),
            {"ids": datos["perfiles_ids"]},
        )


async def _sembrar_precio_oficial_ec02(sufijo: str) -> dict[str, Any]:
    """Crea el par con precio oficial y proyecta la fila de `precio_vigente`."""
    async with sesion_transaccional() as sesion:
        datos = await _insertar_catalogo(sesion, sufijo, n_establecimientos=1, n_perfiles=1)
        establecimiento_id = datos["establecimiento_ids"][0]
        await sesion.execute(
            text("""
                INSERT INTO public.precio_oficial (
                    presentacion_id, establecimiento_id, producto_id, comercio_id,
                    precio_cop, precio_por_base
                ) VALUES (
                    :pres, :est, :prod, :comercio, :precio, :precio_base
                );
            """),
            {
                "pres": datos["presentacion_id"],
                "est": establecimiento_id,
                "prod": datos["producto_id"],
                "comercio": datos["perfiles_ids"][0],
                "precio": PRECIO_OFICIAL_EC02,
                "precio_base": Decimal(PRECIO_OFICIAL_EC02) / Decimal(1000),
            },
        )
        resultado = await OficialConContraste().recalcular_par(
            sesion, datos["presentacion_id"], establecimiento_id
        )
        assert resultado is not None
        assert resultado.sello == "oficial"
        assert resultado.precio_cop == PRECIO_OFICIAL_EC02
    return datos


@pytest.mark.asyncio
async def test_migracion_0007_persiste_contraste_1000_contra_200000_sin_overflow() -> None:
    """Un contraste 199,0000 cabe en numeric(14,4) y queda en `precio_vigente`."""
    await _exigir_base_aislada()
    sufijo = _sufijo()
    ahora = datetime.now(UTC)
    observado = ahora - timedelta(hours=1)

    creador = obtener_creador_sesiones()
    async with creador() as sesion:
        transaccion = await sesion.begin()
        await sesion.execute(text("SET LOCAL ROLE app_backend;"))
        try:
            tipo = (
                await sesion.execute(
                    text("""
                        SELECT numeric_precision, numeric_scale
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'precio_vigente'
                          AND column_name = 'diferencia_pct';
                    """)
                )
            ).first()
            assert tipo is not None
            assert (tipo.numeric_precision, tipo.numeric_scale) == (14, 4)
            # `_migraciones_historial` no esta entre las tablas que usa app_backend;
            # se consulta con el rol de sesion y se vuelve al rol de la aplicacion.
            await sesion.execute(text("RESET ROLE;"))
            historial = (
                await sesion.execute(text("SELECT nombre FROM public._migraciones_historial;"))
            ).scalars()
            assert "0007_diferencia_pct_amplia.sql" in set(historial)
            await sesion.execute(text("SET LOCAL ROLE app_backend;"))

            datos = await _insertar_catalogo(sesion, sufijo, n_establecimientos=1, n_perfiles=4)
            presentacion_id = datos["presentacion_id"]
            establecimiento_id = datos["establecimiento_ids"][0]
            producto_id = datos["producto_id"]
            comercio_id = datos["perfiles_ids"][0]
            reportantes = datos["perfiles_ids"][1:]

            await sesion.execute(
                text("""
                    INSERT INTO public.precio_oficial (
                        presentacion_id, establecimiento_id, producto_id, comercio_id,
                        precio_cop, precio_por_base
                    ) VALUES (
                        :pres, :est, :prod, :comercio, :precio, :precio_base
                    );
                """),
                {
                    "pres": presentacion_id,
                    "est": establecimiento_id,
                    "prod": producto_id,
                    "comercio": comercio_id,
                    "precio": PRECIO_OFICIAL_CONTRASTE,
                    "precio_base": Decimal(PRECIO_OFICIAL_CONTRASTE) / Decimal(1000),
                },
            )
            await sesion.execute(
                text("""
                    INSERT INTO public.reporte_precio (
                        presentacion_id, establecimiento_id, producto_id,
                        precio_cop, cantidad_base_snapshot, precio_por_base,
                        fuente, reportante_id, observado_en, estado,
                        estado_original, conjunto_referencia
                    ) VALUES (
                        :pres, :est, :prod, :precio, 1000, :precio_base,
                        'usuario', :uid, :observado, 'aceptado',
                        'aceptado', 'sin_referencia'
                    );
                """),
                [
                    {
                        "pres": presentacion_id,
                        "est": establecimiento_id,
                        "prod": producto_id,
                        "precio": PRECIO_COMUNIDAD_CONTRASTE,
                        "precio_base": Decimal(PRECIO_COMUNIDAD_CONTRASTE) / Decimal(1000),
                        "uid": reportante,
                        "observado": observado,
                    }
                    for reportante in reportantes
                ],
            )

            resultado = await OficialConContraste().recalcular_par(
                sesion, presentacion_id, establecimiento_id, ahora
            )
            assert resultado is not None
            assert resultado.sello == "en_disputa"

            fila = (
                await sesion.execute(
                    text("""
                        SELECT precio_cop, precio_oficial_cop, diferencia_pct, sello::text
                        FROM public.precio_vigente
                        WHERE presentacion_id = :pres AND establecimiento_id = :est;
                    """),
                    {"pres": presentacion_id, "est": establecimiento_id},
                )
            ).first()
            assert fila is not None
            assert fila.precio_cop == PRECIO_COMUNIDAD_CONTRASTE
            assert fila.precio_oficial_cop == PRECIO_OFICIAL_CONTRASTE
            assert fila.sello == "en_disputa"
            assert fila.diferencia_pct == Decimal("199.0000")
        finally:
            await transaccion.rollback()


@pytest.mark.asyncio
async def test_ec02_precio_oficial_100_comparaciones_p95_menor_60_s() -> None:
    """EC-02: 100 comparaciones devuelven el precio oficial con p95 <= 60 s."""
    await _exigir_base_aislada()
    sufijo = _sufijo()
    datos = await _sembrar_precio_oficial_ec02(sufijo)
    prod_id = str(datos["producto_id"])
    pres_id = str(datos["presentacion_id"])
    est_id = str(datos["establecimiento_ids"][0])
    params = {"orden": "precio_unitario", "presentacion_id": pres_id}
    cache = CacheMemoria()
    previo = app.dependency_overrides.get(obtener_puerto_cache)
    app.dependency_overrides[obtener_puerto_cache] = lambda: cache
    tiempos_ms: list[float] = []

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
            for indice in range(100):
                # Cada comparacion vuelve a leer la base: el cache no puede ocultar
                # que el precio oficial proyectado sea el que responde la API.
                await cache.invalidar_producto(prod_id)
                inicio = time.perf_counter()
                respuesta = await cli.get(URL_COMPARACION.format(prod_id=prod_id), params=params)
                tiempos_ms.append((time.perf_counter() - inicio) * 1000.0)

                assert respuesta.status_code == 200, respuesta.text
                resultados = respuesta.json()["datos"]["resultados"]
                assert len(resultados) == 1, f"Ciclo {indice}: {resultados}"
                item = resultados[0]
                assert item["establecimiento"]["id"] == est_id
                assert item["precio_cop"] == PRECIO_OFICIAL_EC02
                assert item["precio_oficial_cop"] == PRECIO_OFICIAL_EC02
                assert item["sello"] == "oficial"
    finally:
        if previo is not None:
            app.dependency_overrides[obtener_puerto_cache] = previo
        else:
            app.dependency_overrides.pop(obtener_puerto_cache, None)
        await _limpiar_escenario(datos)

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
    print(f"\n[EC-02 ETAPA2 METRICAS] {json.dumps(resumen)}")
    assert len(ordenados) == 100
    assert resumen["p95_ms"] <= 60_000.0


async def _sembrar_resultados_ec06(sufijo: str, ahora: datetime) -> dict[str, Any]:
    """Crea cuatro resultados vigentes con precios distintos y sin promociones."""
    async with sesion_transaccional() as sesion:
        datos = await _insertar_catalogo(sesion, sufijo, n_establecimientos=4, n_perfiles=3)
        filas = [
            {
                "pres": datos["presentacion_id"],
                "est": establecimiento_id,
                "prod": datos["producto_id"],
                "precio": precio,
                "precio_base": Decimal(precio) / Decimal(1000),
                "observado": ahora - timedelta(hours=2),
            }
            for establecimiento_id, precio in zip(
                datos["establecimiento_ids"], (1000, 1250, 1500, 2000), strict=True
            )
        ]
        await sesion.execute(
            text("""
                INSERT INTO public.precio_vigente (
                    presentacion_id, establecimiento_id, producto_id, precio_cop,
                    precio_por_base, cantidad_base, sello, motivo_sello,
                    n_reportes_validos, n_fuentes, ultimo_reporte_en
                ) VALUES (
                    :pres, :est, :prod, :precio, :precio_base, 1000, 'pocos_datos',
                    'Pocos reportes para la prueba EC-06', 1, 1, :observado
                );
            """),
            filas,
        )
    return datos


async def _insertar_promociones_ec06(sufijo: str, datos: dict[str, Any]) -> None:
    """Publica tres promociones vigentes de distinto tipo sobre el producto."""
    ahora = datetime.now(UTC)
    establecimientos = datos["establecimiento_ids"]
    filas = [
        {
            "est": establecimientos[0],
            "prod": datos["producto_id"],
            "pres": datos["presentacion_id"],
            "comercio": datos["perfiles_ids"][0],
            "titulo": f"Descuento T68 {sufijo}",
            "tipo": "porcentaje",
            "porcentaje": 10,
            "precio_especial": None,
            "pague_x": None,
            "lleve_y": None,
            "condiciones": "Valida hasta agotar existencias.",
            "desde": ahora - timedelta(hours=2),
            "hasta": ahora + timedelta(days=7),
        },
        {
            "est": establecimientos[1],
            "prod": datos["producto_id"],
            "pres": datos["presentacion_id"],
            "comercio": datos["perfiles_ids"][1],
            "titulo": f"Precio especial T68 {sufijo}",
            "tipo": "precio_especial",
            "porcentaje": None,
            "precio_especial": 900,
            "pague_x": None,
            "lleve_y": None,
            "condiciones": "Presenta esta promocion en caja.",
            "desde": ahora - timedelta(hours=1),
            "hasta": ahora + timedelta(days=7),
        },
        {
            "est": establecimientos[2],
            "prod": datos["producto_id"],
            "pres": datos["presentacion_id"],
            "comercio": datos["perfiles_ids"][2],
            "titulo": f"Lleva tres paga dos T68 {sufijo}",
            "tipo": "pague_x_lleve_y",
            "porcentaje": None,
            "precio_especial": None,
            "pague_x": 2,
            "lleve_y": 3,
            "condiciones": "Aplica solo en la tienda participante.",
            "desde": ahora,
            "hasta": ahora + timedelta(days=7),
        },
    ]
    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("""
                INSERT INTO public.promocion (
                    establecimiento_id, producto_id, presentacion_id, comercio_id,
                    titulo, tipo, porcentaje_descuento, precio_especial_cop,
                    pague_x, lleve_y, condiciones, vigente_desde, vigente_hasta,
                    hasta_revocar, activa
                ) VALUES (
                    :est, :prod, :pres, :comercio, :titulo,
                    CAST(:tipo AS tipo_promocion), :porcentaje, :precio_especial,
                    :pague_x, :lleve_y, :condiciones, :desde, :hasta, false, true
                );
            """),
            filas,
        )


@pytest.mark.asyncio
async def test_ec06_promociones_activas_no_cambian_orden_de_resultados() -> None:
    """EC-06: el orden de `resultados` es identico con y sin promociones."""
    await _exigir_base_aislada()
    sufijo = _sufijo()
    ahora = datetime.now(UTC)
    datos = await _sembrar_resultados_ec06(sufijo, ahora)
    prod_id = str(datos["producto_id"])
    pres_id = str(datos["presentacion_id"])
    params = {"orden": "precio_unitario", "presentacion_id": pres_id}
    cache = CacheMemoria()
    previo = app.dependency_overrides.get(obtener_puerto_cache)
    app.dependency_overrides[obtener_puerto_cache] = lambda: cache

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
            sin_promos = await cli.get(URL_COMPARACION.format(prod_id=prod_id), params=params)
            assert sin_promos.status_code == 200, sin_promos.text
            datos_sin = sin_promos.json()["datos"]
            assert datos_sin["promociones"] == []
            precios_sin = [item["precio_cop"] for item in datos_sin["resultados"]]
            assert precios_sin == [1000, 1250, 1500, 2000]

            await _insertar_promociones_ec06(sufijo, datos)
            await cache.invalidar_producto(prod_id)
            con_promos = await cli.get(URL_COMPARACION.format(prod_id=prod_id), params=params)
            assert con_promos.status_code == 200, con_promos.text
            datos_con = con_promos.json()["datos"]

            # EC-06: la misma lista, en el mismo orden, con los mismos precios.
            assert datos_con["resultados"] == datos_sin["resultados"]
            assert datos_con["promociones"] != []
            assert len(datos_con["promociones"]) == 3
            assert all(promo["es_promocion"] is True for promo in datos_con["promociones"])
            assert {promo["tipo"] for promo in datos_con["promociones"]} == {
                "porcentaje",
                "precio_especial",
                "pague_x_lleve_y",
            }
            assert datos_con["meta"]["criterio_orden"] == "precio_unitario"
            assert "promociones" in datos_con["meta"]["texto_neutralidad"].lower()
    finally:
        if previo is not None:
            app.dependency_overrides[obtener_puerto_cache] = previo
        else:
            app.dependency_overrides.pop(obtener_puerto_cache, None)
        await _limpiar_escenario(datos)
