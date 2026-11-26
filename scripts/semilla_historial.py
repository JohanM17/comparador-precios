"""Semilla reproducible del historial de precios de demostracion (A2 / EC-08).

Genera una serie de puntos historicos de 90 dias marcados con ``es_demo = true``
para que la grafica de historial tenga datos visibles en la demo.

El generador es puro y determinista: los IDs se derivan con ``uuid5`` y los
precios se calculan a partir de un precio base conocido. El escritor es
idempotente (``ON CONFLICT (id) DO NOTHING``) y NUNCA modifica ``precio_vigente``:
los puntos demo no alteran la comparacion vigente.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TypedDict
from uuid import NAMESPACE_DNS, UUID, uuid5

import asyncpg

from app.config import obtener_configuracion
from app.dominio.unidades import calcular_precio_por_base

DIAS_HISTORIAL: tuple[int, ...] = (85, 70, 55, 40, 25, 10)
FUENTES: tuple[str, ...] = ("usuario", "comercio", "semilla")

# Perfil existente creado por scripts/semilla.py para los reportes de usuario.
PERFIL_VECINO_CENTENARIO: UUID = uuid5(NAMESPACE_DNS, "semilla:perfil:vecino_centenario")


class PuntoDemo(TypedDict):
    """Fila de ``public.reporte_precio`` generada para la demostracion."""

    id: UUID
    presentacion_id: UUID
    establecimiento_id: UUID
    producto_id: UUID
    precio_cop: int
    cantidad_base_snapshot: Decimal
    precio_por_base: Decimal
    fuente: str
    reportante_id: UUID | None
    observado_en: datetime
    estado: str
    estado_original: str
    conjunto_referencia: str
    es_demo: bool


SQL_SELECCIONAR_PRESENTACIONES = """
    SELECT pr.id AS presentacion_id, pr.producto_id, pr.cantidad_base
    FROM public.presentacion pr
    JOIN public.producto p ON p.id = pr.producto_id
    LEFT JOIN public.reporte_precio rp
      ON rp.presentacion_id = pr.id
     AND rp.estado::text IN ('aceptado', 'dudoso')
    WHERE pr.activa = true AND p.activo = true
    GROUP BY pr.id, pr.producto_id, pr.cantidad_base, p.nombre
    ORDER BY count(rp.id) DESC, p.nombre ASC, pr.cantidad_base ASC, pr.id ASC
    LIMIT 3;
"""

SQL_SELECCIONAR_ESTABLECIMIENTOS = """
    SELECT e.id
    FROM public.establecimiento e
    LEFT JOIN public.reporte_precio rp
      ON rp.establecimiento_id = e.id
     AND rp.estado::text IN ('aceptado', 'dudoso')
    WHERE e.activo = true
    GROUP BY e.id, e.nombre
    ORDER BY count(rp.id) DESC, e.nombre ASC, e.id ASC
    LIMIT 3;
"""

SQL_PRECIO_VIGENTE = """
    SELECT precio_cop
    FROM public.precio_vigente
    WHERE presentacion_id = $1 AND establecimiento_id = $2;
"""

SQL_ULTIMO_REPORTE = """
    SELECT precio_cop
    FROM public.reporte_precio
    WHERE presentacion_id = $1
      AND establecimiento_id = $2
      AND estado::text = 'aceptado'
    ORDER BY observado_en DESC, id DESC
    LIMIT 1;
"""

SQL_ULTIMO_REPORTE_PRESENTACION = """
    SELECT precio_cop
    FROM public.reporte_precio
    WHERE presentacion_id = $1
      AND estado::text = 'aceptado'
    ORDER BY observado_en DESC, id DESC
    LIMIT 1;
"""

SQL_INSERTAR_REPORTE = """
    INSERT INTO public.reporte_precio (
        id, presentacion_id, establecimiento_id, producto_id,
        precio_cop, cantidad_base_snapshot, precio_por_base,
        fuente, reportante_id, observado_en,
        estado, estado_original, conjunto_referencia, es_demo
    ) VALUES (
        $1, $2, $3, $4,
        $5, $6, $7,
        CAST($8 AS fuente_precio), $9, $10,
        CAST($11 AS estado_confianza), CAST($12 AS estado_confianza), $13, $14
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id;
"""


def _normalizar_utc(momento: datetime) -> datetime:
    """Convierte un instante a UTC sin mutar el valor original."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=UTC)
    return momento.astimezone(UTC)


def generar_puntos_demo(
    *,
    producto_id: UUID,
    presentacion_id: UUID,
    establecimiento_id: UUID,
    cantidad_base: Decimal,
    precio_base_cop: int,
    ahora: datetime,
) -> list[PuntoDemo]:
    """Genera puntos historicos deterministas para una combinacion producto-tienda.

    No muta la entrada y devuelve una lista nueva. Los precios suben 100 COP por
    indice para dibujar una tendencia simple y creible en la grafica.
    """
    if cantidad_base <= 0:
        raise ValueError("La cantidad base debe ser estrictamente mayor a 0.")
    if precio_base_cop <= 0:
        raise ValueError("El precio base en COP debe ser estrictamente mayor a 0.")

    momento_utc = _normalizar_utc(ahora)
    puntos: list[PuntoDemo] = []

    for indice, dias_atras in enumerate(DIAS_HISTORIAL):
        precio_cop = precio_base_cop + indice * 100
        fuente = FUENTES[indice % len(FUENTES)]
        estado = "aceptado" if indice % 2 == 0 else "dudoso"
        puntos.append(
            PuntoDemo(
                id=uuid5(
                    NAMESPACE_DNS,
                    f"demo-historial:{producto_id}:{presentacion_id}:{establecimiento_id}:{indice}",
                ),
                presentacion_id=presentacion_id,
                establecimiento_id=establecimiento_id,
                producto_id=producto_id,
                precio_cop=precio_cop,
                cantidad_base_snapshot=cantidad_base,
                precio_por_base=calcular_precio_por_base(precio_cop, cantidad_base),
                fuente=fuente,
                reportante_id=PERFIL_VECINO_CENTENARIO if fuente == "usuario" else None,
                observado_en=momento_utc - timedelta(days=dias_atras),
                estado=estado,
                estado_original=estado,
                conjunto_referencia=(
                    "presentacion_tienda" if estado == "aceptado" else "sin_referencia"
                ),
                es_demo=True,
            )
        )

    return puntos


async def _precio_base_para(
    conn: asyncpg.Connection,
    presentacion_id: UUID,
    establecimiento_id: UUID,
) -> int | None:
    """Obtiene un precio base real para la combinacion, sin inventar valores.

    Prioriza el precio vigente del par y, si no existe, el ultimo reporte aceptado
    del par o de la misma presentacion en cualquier establecimiento.
    """
    vigente = await conn.fetchval(
        SQL_PRECIO_VIGENTE,
        presentacion_id,
        establecimiento_id,
    )
    if vigente is not None:
        return int(vigente)

    ultimo = await conn.fetchval(
        SQL_ULTIMO_REPORTE,
        presentacion_id,
        establecimiento_id,
    )
    if ultimo is not None:
        return int(ultimo)

    ultimo_presentacion = await conn.fetchval(
        SQL_ULTIMO_REPORTE_PRESENTACION,
        presentacion_id,
    )
    if ultimo_presentacion is not None:
        return int(ultimo_presentacion)
    return None


async def sembrar_historial(
    conn: asyncpg.Connection,
    ahora: datetime,
) -> dict[str, int]:
    """Inserta los puntos demo para hasta 3 presentaciones por 3 establecimientos."""
    perfil_existe = await conn.fetchval(
        "SELECT 1 FROM public.perfil WHERE id = $1;",
        PERFIL_VECINO_CENTENARIO,
    )
    if perfil_existe is None:
        raise RuntimeError(
            "No existe el perfil semilla 'vecino_centenario'. "
            "Ejecuta scripts/semilla.py antes de sembrar el historial demo."
        )

    presentaciones = await conn.fetch(SQL_SELECCIONAR_PRESENTACIONES)
    establecimientos = await conn.fetch(SQL_SELECCIONAR_ESTABLECIMIENTOS)
    if not presentaciones or not establecimientos:
        return {
            "combinaciones": 0,
            "combinaciones_omitidas": 0,
            "puntos_generados": 0,
            "puntos_insertados": 0,
        }

    combinaciones = 0
    combinaciones_omitidas = 0
    puntos_generados = 0
    puntos_insertados = 0

    for presentacion in presentaciones:
        presentacion_id: UUID = presentacion["presentacion_id"]
        producto_id: UUID = presentacion["producto_id"]
        cantidad_base = Decimal(str(presentacion["cantidad_base"]))

        for establecimiento in establecimientos:
            establecimiento_id: UUID = establecimiento["id"]
            precio_base = await _precio_base_para(conn, presentacion_id, establecimiento_id)
            if precio_base is None:
                combinaciones_omitidas += 1
                continue

            combinaciones += 1
            puntos = generar_puntos_demo(
                producto_id=producto_id,
                presentacion_id=presentacion_id,
                establecimiento_id=establecimiento_id,
                cantidad_base=cantidad_base,
                precio_base_cop=precio_base,
                ahora=ahora,
            )
            puntos_generados += len(puntos)

            for punto in puntos:
                insertado = await conn.fetchval(
                    SQL_INSERTAR_REPORTE,
                    punto["id"],
                    punto["presentacion_id"],
                    punto["establecimiento_id"],
                    punto["producto_id"],
                    punto["precio_cop"],
                    punto["cantidad_base_snapshot"],
                    punto["precio_por_base"],
                    punto["fuente"],
                    punto["reportante_id"],
                    punto["observado_en"],
                    punto["estado"],
                    punto["estado_original"],
                    punto["conjunto_referencia"],
                    punto["es_demo"],
                )
                if insertado is not None:
                    puntos_insertados += 1

    return {
        "combinaciones": combinaciones,
        "combinaciones_omitidas": combinaciones_omitidas,
        "puntos_generados": puntos_generados,
        "puntos_insertados": puntos_insertados,
    }


async def ejecutar_semilla_historial(ahora: datetime | None = None) -> dict[str, int]:
    """Conecta a PostgreSQL y siembra el historial demo de forma idempotente."""
    configuracion = obtener_configuracion()
    url = configuracion.MIGRATIONS_DATABASE_URL or configuracion.DATABASE_URL
    if not url:
        raise RuntimeError(
            "Sin base de datos: configura MIGRATIONS_DATABASE_URL o DATABASE_URL "
            "en el archivo .env antes de ejecutar scripts/semilla_historial.py."
        )

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    momento = ahora if ahora is not None else datetime.now(UTC)
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        return await sembrar_historial(conn, momento)
    finally:
        await conn.close()


def main() -> int:
    """Punto de entrada del script; devuelve 0 si la semilla se aplico."""
    try:
        resultado = asyncio.run(ejecutar_semilla_historial())
    except RuntimeError as error:
        print(f"[ERROR] {error}")
        return 1

    print("\n[OK] Historial demo aplicado con exito:")
    print(f"  -> combinaciones: {resultado['combinaciones']}")
    print(f"  -> combinaciones_omitidas: {resultado['combinaciones_omitidas']}")
    print(f"  -> puntos_generados: {resultado['puntos_generados']}")
    print(f"  -> puntos_insertados: {resultado['puntos_insertados']}")
    print("  -> precio_vigente: sin cambios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
