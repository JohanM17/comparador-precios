"""Script de carga idempotente de datos semilla para Armenia (Quindío).

Carga categorías, productos, presentaciones, alias, establecimientos y precios semilla
iniciales con precalculo de precio_vigente en dos bloques y sellos de confianza.
Garantiza 100 % de idempotencia mediante inserciones en lote (executemany) y ON CONFLICT.
"""

from __future__ import annotations

import asyncio
import csv
import unicodedata
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

import asyncpg

from app.config import obtener_configuracion
from app.dominio.parametros import ParametrosDominio
from app.dominio.sello import evaluar_sello_y_precio
from app.dominio.unidades import calcular_cantidad_base, calcular_precio_por_base
from app.dominio.vigencia import CandidatoReporte

DIRECTORIO_RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIO_SEMILLA = DIRECTORIO_RAIZ / "supabase" / "seed"


def normalizar_texto(texto: str) -> str:
    """Convierte texto a minúsculas y elimina diacríticos/tildes."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tildes.lower().strip()


async def limpiar_registros_prueba_residuales(conn: asyncpg.Connection) -> None:
    """Desactiva productos y tiendas temporales de pruebas y limpia su precio_vigente."""
    await conn.execute(
        """
        UPDATE public.producto
        SET activo = false
        WHERE nombre LIKE 'EC02 %'
           OR nombre LIKE 'Prod Test %'
           OR nombre LIKE 'Harina Prueba %'
           OR (nombre LIKE 'Lentejas %' AND nombre <> 'Lentejas seleccionadas');
        """
    )
    await conn.execute(
        """
        UPDATE public.presentacion
        SET activa = false
        WHERE producto_id IN (SELECT id FROM public.producto WHERE activo = false);
        """
    )
    await conn.execute(
        """
        UPDATE public.establecimiento
        SET activo = false
        WHERE nombre LIKE 'Tienda EC02 %' OR nombre LIKE 'Tienda user_%';
        """
    )
    await conn.execute(
        """
        DELETE FROM public.precio_vigente
        WHERE producto_id IN (SELECT id FROM public.producto WHERE activo = false)
           OR establecimiento_id IN (SELECT id FROM public.establecimiento WHERE activo = false);
        """
    )


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
        INSERT INTO producto (nombre, nombre_norm, categoria_id, unidad_base, activo)
        VALUES ($1, $2, $3, $4, true)
        ON CONFLICT (nombre) DO UPDATE SET
            categoria_id = EXCLUDED.categoria_id,
            unidad_base = EXCLUDED.unidad_base,
            activo = true;
        """,
        filas_datos,
    )

    filas_db = await conn.fetch(
        "SELECT id, nombre, unidad_base FROM producto WHERE activo = true;"
    )
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
            cantidad_base, etiqueta, etiqueta_norm, codigo_barras, fuente_catalogo, activa
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'semilla', true)
        ON CONFLICT (producto_id, marca, cantidad_base) DO UPDATE SET
            etiqueta = EXCLUDED.etiqueta,
            etiqueta_norm = EXCLUDED.etiqueta_norm,
            codigo_barras = EXCLUDED.codigo_barras,
            activa = true;
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
            departamento, ubicacion, osm_id, activo
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            ST_SetSRID(ST_MakePoint($8, $9), 4326),
            $10, true
        )
        ON CONFLICT (nombre, direccion) DO UPDATE SET
            tipo = EXCLUDED.tipo,
            barrio = EXCLUDED.barrio,
            ubicacion = EXCLUDED.ubicacion,
            osm_id = EXCLUDED.osm_id,
            activo = true;
        """,
        filas_datos,
    )
    return len(filas_datos)


def _estimar_precio_base_cop(
    categoria_id: int, unidad_base: str, cantidad_base: Decimal, indice: int
) -> int:
    """Calcula un precio realista en COP para la canasta familiar en Armenia."""
    cant = float(cantidad_base)
    variacion = 1.0 + ((indice % 5) - 2) * 0.03

    if unidad_base == "g":
        tarifas_por_gramo = {
            1: 4.8,   # Granos, arroz, pastas
            2: 19.5,  # Lacteos y quesos en gramos
            3: 5.2,   # Sal, azucar, panela
            4: 24.0,  # Cafe, chocolate, avena
            5: 9.5,   # Harinas y panaderia
            6: 16.0,  # Enlatados y salsas
            7: 22.0,  # Carnes, pollo y embutidos
            8: 3.8,   # Frutas, verduras y tuberculos
            9: 11.0,  # Aseo del hogar en gramos
            10: 21.0, # Cuidado personal en gramos
        }
        bruto = cant * tarifas_por_gramo.get(categoria_id, 8.0) * variacion
    elif unidad_base == "ml":
        tarifas_por_ml = {
            2: 4.3,   # Leche, yogur, kumis
            3: 11.5,  # Aceites de cocina
            4: 3.2,   # Agua embotellada
            9: 6.2,   # Detergentes liquidos, blanqueador
            10: 19.0, # Champu, acondicionador, crema, alcohol
        }
        bruto = cant * tarifas_por_ml.get(categoria_id, 6.0) * variacion
    else:
        # unidad
        if cant >= 50:
            bruto = cant * 110.0 * variacion
        elif cant >= 15:
            bruto = cant * 580.0 * variacion
        elif cant >= 6:
            bruto = cant * 1450.0 * variacion
        else:
            bruto = max(2200.0, cant * 2400.0 * variacion)

    redondeado = int(round(bruto / 100.0) * 100)
    return max(1500, min(85000, redondeado))


def _particionar_establecimientos(
    filas_est: list[Any],
) -> tuple[list[Any], list[Any]]:
    tiendas_barrio = [e for e in filas_est if e["tipo"] == "tienda_barrio"]
    supermercados = [e for e in filas_est if e["tipo"] != "tienda_barrio"]
    return (tiendas_barrio or list(filas_est), supermercados or list(filas_est))


def _definir_pares_presentacion(
    idx: int,
    precio_base: int,
    ahora: datetime,
    uid_1: UUID,
    uid_2: UUID,
    supermercados: list[Any],
    tiendas_barrio: list[Any],
) -> list[tuple[UUID, list[tuple[str, UUID | None, int, datetime, str]]]]:
    est_confiable_sup = supermercados[(idx * 2) % len(supermercados)]["id"]
    est_confiable_barrio = tiendas_barrio[(idx * 2) % len(tiendas_barrio)]["id"]
    est_pocos_datos = supermercados[(idx * 2 + 1) % len(supermercados)]["id"]
    est_bloque_2 = tiendas_barrio[(idx * 2 + 1) % len(tiendas_barrio)]["id"]
    es_par = idx % 2 == 0
    obs_b2 = ahora - timedelta(days=12) if es_par else ahora - timedelta(hours=8)
    est_b2 = "aceptado" if es_par else "dudoso"

    return [
        (
            est_confiable_sup,
            [
                ("semilla", None, precio_base, ahora - timedelta(hours=18), "aceptado"),
                ("usuario", uid_1, precio_base + 50, ahora - timedelta(hours=12), "aceptado"),
                ("usuario", uid_2, precio_base, ahora - timedelta(hours=4), "aceptado"),
            ],
        ),
        (
            est_confiable_barrio,
            [
                ("semilla", None, precio_base + 150, ahora - timedelta(hours=24), "aceptado"),
                ("usuario", uid_1, precio_base + 150, ahora - timedelta(hours=10), "aceptado"),
                ("usuario", uid_2, precio_base + 200, ahora - timedelta(hours=3), "aceptado"),
            ],
        ),
        (
            est_pocos_datos,
            [
                (
                    "semilla",
                    None,
                    max(1200, precio_base - 100),
                    ahora - timedelta(days=2),
                    "aceptado",
                ),
            ],
        ),
        (
            est_bloque_2,
            [("semilla", None, precio_base + 300, obs_b2, est_b2)],
        ),
    ]


def _construir_filas_par(
    pres_id: UUID,
    prod_id: UUID,
    est_id: UUID,
    cant_base: Decimal,
    definiciones: list[tuple[str, UUID | None, int, datetime, str]],
    ahora: datetime,
    params: ParametrosDominio,
) -> tuple[list[tuple[Any, ...]], tuple[Any, ...] | None]:
    reportes_par: list[tuple[Any, ...]] = []
    candidatos: list[CandidatoReporte] = []

    for r_idx, (fuente, autor_uuid, p_cop, obs_en, estado) in enumerate(definiciones):
        rep_id = uuid5(NAMESPACE_DNS, f"semilla:rep:{pres_id}:{est_id}:{r_idx}")
        ppb = calcular_precio_por_base(p_cop, cant_base)
        ref = "presentacion_tienda" if estado == "aceptado" else "sin_referencia"
        reportes_par.append(
            (
                rep_id,
                pres_id,
                est_id,
                prod_id,
                p_cop,
                cant_base,
                ppb,
                fuente,
                autor_uuid,
                obs_en,
                estado,
                estado,
                ref,
            )
        )
        candidatos.append(
            CandidatoReporte(
                id=rep_id,
                precio_cop=p_cop,
                cantidad_base=cant_base,
                observado_en=obs_en,
                autor_id=str(autor_uuid) if autor_uuid else None,
                reputacion_autor=0.85 if autor_uuid else 0.5,
                tiene_foto=False,
                estado=estado,
                fuente=fuente,
            )
        )

    res = evaluar_sello_y_precio(candidatos, ahora, params)
    if res is None:
        return reportes_par, None

    fila_vigente = (
        pres_id,
        est_id,
        prod_id,
        res.precio_cop,
        res.precio_por_base,
        res.cantidad_base,
        res.sello,
        res.motivo_sello,
        res.n_reportes_validos,
        res.n_fuentes,
        res.dispersion,
        res.ultimo_reporte_en,
        res.reporte_origen_id,
    )
    return reportes_par, fila_vigente


async def cargar_precios_semilla(conn: asyncpg.Connection) -> int:
    """Siembra reportes semilla idempotentes y precalcula precio_vigente para S1, S2 y S3."""
    ahora = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    params = ParametrosDominio()

    perfiles_semilla = [
        (uuid5(NAMESPACE_DNS, "semilla:perfil:vecino_centenario"), "vecino_centenario"),
        (uuid5(NAMESPACE_DNS, "semilla:perfil:vecina_laureles"), "vecina_laureles"),
        (uuid5(NAMESPACE_DNS, "semilla:perfil:comprador_calima"), "comprador_calima"),
    ]
    await conn.executemany(
        """
        INSERT INTO public.perfil (id, alias, rol, estado, reputacion, reportes_corroborados)
        VALUES ($1, $2, 'reportante', 'activa', 0.850, 12)
        ON CONFLICT (id) DO NOTHING;
        """,
        perfiles_semilla,
    )
    uid_1, uid_2 = perfiles_semilla[0][0], perfiles_semilla[1][0]

    filas_pres = await conn.fetch(
        """
        SELECT pr.id as presentacion_id, pr.producto_id, pr.cantidad_base,
               p.categoria_id, p.unidad_base, p.nombre as producto_nombre
        FROM public.presentacion pr
        JOIN public.producto p ON pr.producto_id = p.id
        WHERE pr.activa = true AND p.activo = true
        ORDER BY p.nombre ASC, pr.cantidad_base ASC;
        """
    )
    filas_est = await conn.fetch(
        """
        SELECT id, nombre, tipo::text as tipo
        FROM public.establecimiento
        WHERE activo = true
        ORDER BY nombre ASC;
        """
    )
    if not filas_pres or not filas_est:
        return 0

    tiendas_barrio, supermercados = _particionar_establecimientos(filas_est)
    lote_reportes: list[tuple[Any, ...]] = []
    lote_vigentes: list[tuple[Any, ...]] = []

    for idx, pr in enumerate(filas_pres):
        pres_id: UUID = pr["presentacion_id"]
        prod_id: UUID = pr["producto_id"]
        cant_base = Decimal(str(pr["cantidad_base"]))
        precio_base = _estimar_precio_base_cop(
            int(pr["categoria_id"]), str(pr["unidad_base"]), cant_base, idx
        )
        config_pares = _definir_pares_presentacion(
            idx, precio_base, ahora, uid_1, uid_2, supermercados, tiendas_barrio
        )
        vistos_est: set[UUID] = set()
        for est_id, definiciones in config_pares:
            if est_id in vistos_est:
                continue
            vistos_est.add(est_id)
            reps, vig = _construir_filas_par(
                pres_id, prod_id, est_id, cant_base, definiciones, ahora, params
            )
            lote_reportes.extend(reps)
            if vig is not None:
                lote_vigentes.append(vig)

    await conn.executemany(
        """
        INSERT INTO public.reporte_precio (
            id, presentacion_id, establecimiento_id, producto_id,
            precio_cop, cantidad_base_snapshot, precio_por_base,
            fuente, reportante_id, observado_en,
            estado, estado_original, conjunto_referencia, es_demo
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7,
            CAST($8 AS fuente_precio), $9, $10,
            CAST($11 AS estado_confianza), CAST($12 AS estado_confianza), $13, false
        )
        ON CONFLICT (id) DO NOTHING;
        """,
        lote_reportes,
    )

    await conn.execute("DELETE FROM public.precio_vigente;")
    await conn.executemany(
        """
        INSERT INTO public.precio_vigente (
            presentacion_id, establecimiento_id, producto_id,
            precio_cop, precio_por_base, cantidad_base,
            sello, motivo_sello, n_reportes_validos, n_fuentes,
            dispersion, ultimo_reporte_en, reporte_origen_id, recalculado_en
        ) VALUES (
            $1, $2, $3,
            $4, $5, $6,
            CAST($7 AS sello_precio), $8, $9, $10,
            $11, $12, $13, now()
        )
        ON CONFLICT (presentacion_id, establecimiento_id) DO UPDATE SET
            producto_id = EXCLUDED.producto_id,
            precio_cop = EXCLUDED.precio_cop,
            precio_por_base = EXCLUDED.precio_por_base,
            cantidad_base = EXCLUDED.cantidad_base,
            sello = EXCLUDED.sello,
            motivo_sello = EXCLUDED.motivo_sello,
            n_reportes_validos = EXCLUDED.n_reportes_validos,
            n_fuentes = EXCLUDED.n_fuentes,
            dispersion = EXCLUDED.dispersion,
            ultimo_reporte_en = EXCLUDED.ultimo_reporte_en,
            reporte_origen_id = EXCLUDED.reporte_origen_id,
            recalculado_en = now();
        """,
        lote_vigentes,
    )

    return len(lote_vigentes)


async def ejecutar_semilla() -> dict[str, int]:
    """Orquesta la carga de todas las fuentes de datos semilla."""
    cfg = obtener_configuracion()
    url = cfg.MIGRATIONS_DATABASE_URL or cfg.DATABASE_URL
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        await limpiar_registros_prueba_residuales(conn)
        n_cat = await cargar_categorias(conn)
        mapa_prod = await cargar_productos(conn)
        n_pres = await cargar_presentaciones(conn, mapa_prod)
        n_ali = await cargar_alias(conn, mapa_prod)
        n_est = await cargar_establecimientos(conn)
        n_pv = await cargar_precios_semilla(conn)
        return {
            "categorias": n_cat,
            "productos": len(mapa_prod),
            "presentaciones": n_pres,
            "alias": n_ali,
            "establecimientos": n_est,
            "precios_vigentes": n_pv,
        }
    finally:
        await conn.close()


if __name__ == "__main__":
    resultado = asyncio.run(ejecutar_semilla())
    print("\n[OK] Semilla aplicada con exito:")
    for k, v in resultado.items():
        print(f"  -> {k}: {v}")
