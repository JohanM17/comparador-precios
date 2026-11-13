"""Script de carga idempotente de datos semilla para Armenia (Quindío).

Carga categorías, productos, presentaciones, alias y establecimientos desde CSV.
Garantiza 100 % de idempotencia mediante inserciones en lote (executemany) y ON CONFLICT.
"""

from __future__ import annotations

import asyncio
import csv
import unicodedata
from decimal import Decimal
from pathlib import Path

import asyncpg
from app.config import obtener_configuracion
from app.dominio.unidades import calcular_cantidad_base

DIRECTORIO_RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIO_SEMILLA = DIRECTORIO_RAIZ / "supabase" / "seed"


def normalizar_texto(texto: str) -> str:
    """Convierte texto a minúsculas y elimina diacríticos/tildes."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tildes.lower().strip()


async def cargar_categorias(conn: asyncpg.Connection) -> int:
    """Carga las categorías base en lote de forma idempotente."""
    ruta = DIRECTORIO_SEMILLA / "categorias.csv"
    if not ruta.exists():
        return 0

    filas_datos: list[tuple[int, str, int | None, int]] = []
    with ruta.open(mode="r", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            cat_id = int(fila["id"])
            nombre = fila["nombre"].strip()
            padre_id = int(fila["padre_id"]) if fila.get("padre_id") else None
            orden = int(fila["orden"]) if fila.get("orden") else 0
            filas_datos.append((cat_id, nombre, padre_id, orden))

    await conn.executemany(
        """
        INSERT INTO categoria (id, nombre, padre_id, orden)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (id) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            orden = EXCLUDED.orden;
        """,
        filas_datos,
    )
    return len(filas_datos)


async def cargar_productos(conn: asyncpg.Connection) -> dict[str, tuple[str, str]]:
    """Carga los productos en lote y retorna un mapa {nombre: (uuid, unidad_base)}."""
    ruta = DIRECTORIO_SEMILLA / "productos.csv"
    if not ruta.exists():
        return {}

    filas_datos: list[tuple[str, str, int, str]] = []
    with ruta.open(mode="r", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            nombre = fila["nombre"].strip()
            nombre_norm = normalizar_texto(nombre)
            cat_id = int(fila["categoria_id"])
            u_base = fila["unidad_base"].strip()
            filas_datos.append((nombre, nombre_norm, cat_id, u_base))

    await conn.executemany(
        """
        INSERT INTO producto (nombre, nombre_norm, categoria_id, unidad_base)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (nombre) DO UPDATE SET
            categoria_id = EXCLUDED.categoria_id,
            unidad_base = EXCLUDED.unidad_base;
        """,
        filas_datos,
    )

    filas_db = await conn.fetch("SELECT id, nombre, unidad_base FROM producto;")
    return {f["nombre"]: (str(f["id"]), f["unidad_base"]) for f in filas_db}


async def cargar_presentaciones(
    conn: asyncpg.Connection, mapa_productos: dict[str, tuple[str, str]]
) -> int:
    """Carga las presentaciones en lote calculando cantidad_base en memoria."""
    ruta = DIRECTORIO_SEMILLA / "presentaciones.csv"
    if not ruta.exists():
        return 0

    filas_datos: list[
        tuple[str, str | None, Decimal, str, int, Decimal, str, str, str | None]
    ] = []
    with ruta.open(mode="r", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            prod_nombre = fila["producto_nombre"].strip()
            if prod_nombre not in mapa_productos:
                continue

            prod_id, u_base = mapa_productos[prod_nombre]
            marca = fila["marca"].strip() if fila.get("marca") else None
            val_cant = Decimal(fila["valor_cantidad"].strip())
            unidad = fila["unidad"].strip()
            mult = (
                int(fila["multiplicador"].strip()) if fila.get("multiplicador") else 1
            )
            etiqueta = fila["etiqueta"].strip()
            etiqueta_norm = normalizar_texto(etiqueta)
            codigo = (
                fila["codigo_barras"].strip() if fila.get("codigo_barras") else None
            )

            cant_base = calcular_cantidad_base(val_cant, unidad, u_base, mult)
            filas_datos.append(
                (
                    prod_id,
                    marca,
                    val_cant,
                    unidad,
                    mult,
                    cant_base,
                    etiqueta,
                    etiqueta_norm,
                    codigo,
                )
            )

    await conn.executemany(
        """
        INSERT INTO presentacion (
            producto_id, marca, valor_cantidad, unidad, multiplicador,
            cantidad_base, etiqueta, etiqueta_norm, codigo_barras, fuente_catalogo
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'semilla')
        ON CONFLICT (producto_id, marca, cantidad_base) DO UPDATE SET
            etiqueta = EXCLUDED.etiqueta,
            etiqueta_norm = EXCLUDED.etiqueta_norm,
            codigo_barras = EXCLUDED.codigo_barras;
        """,
        filas_datos,
    )
    return len(filas_datos)


async def cargar_alias(
    conn: asyncpg.Connection, mapa_productos: dict[str, tuple[str, str]]
) -> int:
    """Carga alias alternativos de búsqueda en lote."""
    ruta = DIRECTORIO_SEMILLA / "alias.csv"
    if not ruta.exists():
        return 0

    filas_datos: list[tuple[str, str, str]] = []
    with ruta.open(mode="r", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            prod_nombre = fila["producto_nombre"].strip()
            if prod_nombre not in mapa_productos:
                continue

            prod_id, _ = mapa_productos[prod_nombre]
            alias = fila["alias"].strip()
            alias_norm = normalizar_texto(alias)
            filas_datos.append((prod_id, alias, alias_norm))

    await conn.executemany(
        """
        INSERT INTO alias_producto (producto_id, alias, alias_norm)
        VALUES ($1, $2, $3)
        ON CONFLICT (producto_id, alias_norm) DO NOTHING;
        """,
        filas_datos,
    )
    return len(filas_datos)


async def cargar_establecimientos(conn: asyncpg.Connection) -> int:
    """Carga los establecimientos reales georreferenciados de Armenia en lote."""
    ruta = DIRECTORIO_SEMILLA / "establecimientos.csv"
    if not ruta.exists():
        return 0

    filas_datos: list[
        tuple[str, str, str | None, str, str | None, str, str, float, float, int | None]
    ] = []
    with ruta.open(mode="r", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            nombre = fila["nombre"].strip()
            tipo = fila["tipo"].strip()
            cadena = fila["cadena"].strip() if fila.get("cadena") else None
            direccion = fila["direccion"].strip()
            barrio = fila["barrio"].strip() if fila.get("barrio") else None
            municipio = fila.get("municipio", "Armenia").strip()
            departamento = fila.get("departamento", "Quindío").strip()
            lat = float(fila["lat"].strip())
            lng = float(fila["lng"].strip())
            osm_id = int(fila["osm_id"].strip()) if fila.get("osm_id") else None

            filas_datos.append(
                (
                    nombre,
                    tipo,
                    cadena,
                    direccion,
                    barrio,
                    municipio,
                    departamento,
                    lng,
                    lat,
                    osm_id,
                )
            )

    await conn.executemany(
        """
        INSERT INTO establecimiento (
            nombre, tipo, cadena, direccion, barrio, municipio,
            departamento, ubicacion, osm_id
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            ST_SetSRID(ST_MakePoint($8, $9), 4326),
            $10
        )
        ON CONFLICT (nombre, direccion) DO UPDATE SET
            tipo = EXCLUDED.tipo,
            barrio = EXCLUDED.barrio,
            ubicacion = EXCLUDED.ubicacion,
            osm_id = EXCLUDED.osm_id;
        """,
        filas_datos,
    )
    return len(filas_datos)


async def ejecutar_semilla() -> dict[str, int]:
    """Orquesta la carga de todas las fuentes de datos semilla."""
    cfg = obtener_configuracion()
    url = cfg.MIGRATIONS_DATABASE_URL or cfg.DATABASE_URL
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        n_cat = await cargar_categorias(conn)
        mapa_prod = await cargar_productos(conn)
        n_pres = await cargar_presentaciones(conn, mapa_prod)
        n_ali = await cargar_alias(conn, mapa_prod)
        n_est = await cargar_establecimientos(conn)
        return {
            "categorias": n_cat,
            "productos": len(mapa_prod),
            "presentaciones": n_pres,
            "alias": n_ali,
            "establecimientos": n_est,
        }
    finally:
        await conn.close()


if __name__ == "__main__":
    resultado = asyncio.run(ejecutar_semilla())
    print("\n[OK] Semilla aplicada con exito:")
    for k, v in resultado.items():
        print(f"  -> {k}: {v}")
