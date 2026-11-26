#!/usr/bin/env python3
"""Benchmark reproducible de la serie de historial (A2 / EC-08).

Inserta 100 reportes sinteticos dentro de una transaccion que siempre se
revierte, ejecuta la consulta del servicio de historial y reporta p50/p95/p99.
No deja datos persistidos ni imprime credenciales.

Uso:
    cd backend
    .venv/bin/python ../scripts/benchmark_historial.py --iteraciones 50
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text

from app.bd import obtener_creador_sesiones
from app.modulos.precios.servicio_historial import ServicioHistorial


def cargar_env(ruta: Path) -> None:
    """Carga .env sin imprimir valores sensibles."""
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        clave, valor = s.split("=", 1)
        valor = valor.strip().strip('"').strip("'")
        if clave.strip() and clave.strip() not in os.environ:
            os.environ[clave.strip()] = valor


def percentil(valores: list[float], proporcion: float) -> float:
    """Percentil nearest-rank sobre una lista no vacia."""
    ordenados = sorted(valores)
    indice = max(0, math.ceil(proporcion * len(ordenados)) - 1)
    return ordenados[indice]


async def elegir_par(sesion: object) -> dict[str, UUID]:
    """Elige un par demo activo con presentacion activa."""
    fila = (
        await sesion.execute(  # type: ignore[attr-defined]
            text("""
                SELECT r.producto_id, r.establecimiento_id, r.presentacion_id
                FROM public.reporte_precio r
                JOIN public.producto p ON p.id = r.producto_id AND p.activo = true
                JOIN public.establecimiento e ON e.id = r.establecimiento_id AND e.activo = true
                JOIN public.presentacion pr ON pr.id = r.presentacion_id AND pr.activa = true
                WHERE r.es_demo = true
                ORDER BY r.observado_en DESC
                LIMIT 1;
            """)
        )
    ).first()
    if fila is None:
        raise SystemExit("No hay un par demo activo con presentacion activa.")
    return {
        "producto_id": fila[0],
        "establecimiento_id": fila[1],
        "presentacion_id": fila[2],
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iteraciones", type=int, default=50)
    parser.add_argument("--calentamiento", type=int, default=5)
    parser.add_argument("--puntos", type=int, default=100)
    parser.add_argument("--limite", type=int, default=100)
    args = parser.parse_args()

    cargar_env(Path(__file__).resolve().parent.parent / ".env")
    creador = obtener_creador_sesiones()
    ahora = datetime.now(UTC)
    desde = ahora - timedelta(days=90)

    async with creador() as sesion:
        transaccion = await sesion.begin()
        try:
            await sesion.execute(text("SET LOCAL ROLE app_backend;"))
            par = await elegir_par(sesion)
            producto_id = par["producto_id"]
            establecimiento_id = par["establecimiento_id"]
            presentacion_id = par["presentacion_id"]

            insertar = text("""
                INSERT INTO public.reporte_precio (
                    id, presentacion_id, establecimiento_id, producto_id,
                    precio_cop, cantidad_base_snapshot, precio_por_base,
                    fuente, reportante_id, observado_en,
                    estado, estado_original, conjunto_referencia, es_demo
                ) VALUES (
                    :id, :presentacion_id, :establecimiento_id, :producto_id,
                    :precio_cop, :cantidad_base, :precio_por_base,
                    CAST('usuario' AS fuente_precio), NULL, :observado_en,
                    CAST('aceptado' AS estado_confianza),
                    CAST('aceptado' AS estado_confianza),
                    'presentacion_tienda', true
                );
            """)
            cantidad_base = Decimal("1000")
            for i in range(args.puntos):
                precio = 4000 + (i * 7) % 1500
                await sesion.execute(
                    insertar,
                    {
                        "id": uuid4(),
                        "presentacion_id": presentacion_id,
                        "establecimiento_id": establecimiento_id,
                        "producto_id": producto_id,
                        "precio_cop": precio,
                        "cantidad_base": cantidad_base,
                        "precio_por_base": Decimal(precio) / cantidad_base,
                        "observado_en": ahora - timedelta(days=i % 90, minutes=i % 60),
                    },
                )

            servicio = ServicioHistorial(sesion, ahora=ahora)
            for _ in range(args.calentamiento):
                await servicio.obtener_historial(
                    producto_id=producto_id,
                    establecimiento_id=establecimiento_id,
                    presentacion_id=presentacion_id,
                    desde=desde,
                    hasta=ahora,
                    limite=args.limite,
                )

            duraciones: list[float] = []
            puntos_devueltos = 0
            for _ in range(args.iteraciones):
                inicio = time.perf_counter()
                respuesta = await servicio.obtener_historial(
                    producto_id=producto_id,
                    establecimiento_id=establecimiento_id,
                    presentacion_id=presentacion_id,
                    desde=desde,
                    hasta=ahora,
                    limite=args.limite,
                )
                duraciones.append((time.perf_counter() - inicio) * 1000)
                puntos_devueltos = len(respuesta.datos.puntos)

            p50 = percentil(duraciones, 0.50)
            p95 = percentil(duraciones, 0.95)
            p99 = percentil(duraciones, 0.99)
            print("Benchmark historial A2 / EC-08")
            print(f"  producto_id: {producto_id}")
            print(f"  establecimiento_id: {establecimiento_id}")
            print(f"  presentacion_id: {presentacion_id}")
            print(f"  puntos_insertados: {args.puntos}")
            print(f"  puntos_devueltos: {puntos_devueltos}")
            print(f"  iteraciones_medidas: {args.iteraciones}")
            print(f"  calentamiento: {args.calentamiento}")
            print(f"  p50_ms: {p50:.2f}")
            print(f"  p95_ms: {p95:.2f}")
            print(f"  p99_ms: {p99:.2f}")
            print(f"  max_ms: {max(duraciones):.2f}")
            print(f"  criterio_p95_500ms: {'CUMPLE' if p95 <= 500 else 'INCUMPLE'}")
            return 0 if p95 <= 500 and puntos_devueltos == args.limite else 1
        finally:
            await transaccion.rollback()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
