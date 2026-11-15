"""Escenario de base de datos para la prueba de actualidad EC-02 (T-54)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from sqlalchemy import text

from app.bd import sesion_transaccional
from app.config import obtener_configuracion


def token_para_ec02(usuario_id: str) -> str:
    """Genera JWT HS256 de prueba para actores de EC-02."""
    cfg = obtener_configuracion()
    secreto = cfg.SUPABASE_JWT_SECRET or "secreto_jwt_prueba_local_32_bytes_min"
    cfg.SUPABASE_JWT_SECRET = secreto
    return jwt.encode({"sub": usuario_id, "email": f"{usuario_id[:8]}@ec02.co"}, secreto, "HS256")


def _fila_rep(
    rid: str,
    pid: str,
    eid: str,
    prod: str,
    precio: int,
    cant: int,
    uid: str,
    obs: datetime,
    est: str,
) -> dict[str, Any]:
    return {
        "id": rid,
        "pid": pid,
        "eid": eid,
        "prod": prod,
        "precio": precio,
        "cant": cant,
        "ppb": round(precio / cant, 6),
        "uid": uid,
        "obs": obs,
        "est": est,
        "ik": str(uuid4()),
    }


async def _insertar_entidades(
    sesion: Any,
    run_id: str,
    prod_id: str,
    pres_ids: list[tuple[str, int]],
    est_ids: list[str],
    actores: tuple[tuple[str, str, float, int], ...],
    hace_30d: datetime,
) -> None:
    for uid, rol, rep, corr in actores:
        await sesion.execute(
            text(
                "INSERT INTO public.perfil "
                "(id, alias, rol, estado, reputacion, reportes_corroborados, creado_en) "
                "VALUES (:id, :al, CAST(:rol AS rol_usuario), 'activa', :rep, :corr, :cr);"
            ),
            {
                "id": uid,
                "al": f"ec02_{uid[:8]}",
                "rol": rol,
                "rep": rep,
                "corr": corr,
                "cr": hace_30d,
            },
        )
        await sesion.execute(
            text(
                "INSERT INTO public.autorizacion_datos (usuario_id, version_politica, finalidad) "
                "VALUES (:id, '1.0', 'Prueba automatizada EC-02 actualidad <= 60s');"
            ),
            {"id": uid},
        )
    await sesion.execute(
        text(
            "INSERT INTO public.producto (id, nombre, nombre_norm, categoria_id, unidad_base) "
            "VALUES (:id, :nom, :norm, 1, 'g');"
        ),
        {"id": prod_id, "nom": f"EC02 Arroz {run_id}", "norm": f"ec02 arroz {run_id}"},
    )
    await sesion.execute(
        text(
            "INSERT INTO public.presentacion (id, producto_id, marca, valor_cantidad, unidad, "
            "multiplicador, cantidad_base, etiqueta, etiqueta_norm) "
            "VALUES (:id, :pid, :marca, :cant, 'g', 1, :cant, :etiq, :enorm);"
        ),
        [
            {
                "id": pid,
                "pid": prod_id,
                "marca": f"MEC02_{i}",
                "cant": cant,
                "etiq": f"Arroz EC02 {run_id} {cant}g",
                "enorm": f"arroz ec02 {run_id} {cant}g",
            }
            for i, (pid, cant) in enumerate(pres_ids)
        ],
    )
    await sesion.execute(
        text(
            "INSERT INTO public.establecimiento "
            "(id, nombre, tipo, direccion, municipio, departamento, ubicacion) "
            "VALUES (:id, :nom, 'tienda_barrio', :dir, 'Armenia', 'Quindio', "
            "ST_SetSRID(ST_MakePoint(-75.675, 4.535), 4326)::geography);"
        ),
        [
            {"id": eid, "nom": f"Tienda EC02 {run_id} {j}", "dir": f"Cra 14 # 2-{10 + j} {run_id}"}
            for j, eid in enumerate(est_ids)
        ],
    )


async def preparar_escenario_ec02() -> dict[str, Any]:
    """Crea producto, 10 presentaciones x 10 tiendas (100 pares) y casos base."""
    ahora = datetime.now(UTC)
    hace_30d = ahora - timedelta(days=30)
    hace_2h = ahora - timedelta(hours=2)
    hace_5m = ahora - timedelta(minutes=5)
    run_id = uuid4().hex[:8]
    u_bajo, u_alto, u_mod = str(uuid4()), str(uuid4()), str(uuid4())
    prod_id = str(uuid4())
    pres_ids = [(str(uuid4()), 500 + i) for i in range(10)]
    est_ids = [str(uuid4()) for _ in range(10)]
    pares: list[dict[str, Any]] = []
    actores = (
        (u_bajo, "reportante", 0.250, 1),
        (u_alto, "reportante", 0.950, 12),
        (u_mod, "moderador", 0.900, 5),
    )

    async with sesion_transaccional() as sesion:
        await _insertar_entidades(sesion, run_id, prod_id, pres_ids, est_ids, actores, hace_30d)
        reportes_sql, vigentes_sql, casos_sql = [], [], []
        for idx in range(100):
            pid, cant = pres_ids[idx // 10]
            eid = est_ids[idx % 10]
            r_base = str(uuid4())
            reportes_sql.append(
                _fila_rep(r_base, pid, eid, prod_id, 5000, cant, u_bajo, hace_2h, "aceptado")
            )
            vigentes_sql.append(
                {
                    "pid": pid,
                    "eid": eid,
                    "prod": prod_id,
                    "precio": 5000,
                    "ppb": round(5000 / cant, 6),
                    "cant": cant,
                    "obs": hace_2h,
                    "rorig": r_base,
                }
            )
            caso_id: str | None = None
            if idx >= 50:
                r_dud, caso_id = str(uuid4()), str(uuid4())
                reportes_sql.append(
                    _fila_rep(r_dud, pid, eid, prod_id, 4700, cant, u_alto, hace_5m, "dudoso")
                )
                casos_sql.append({"cid": caso_id, "rid": r_dud})
            pares.append({"pres_id": pid, "est_id": eid, "caso_id": caso_id})

        await sesion.execute(
            text(
                "INSERT INTO public.reporte_precio (id, presentacion_id, establecimiento_id, "
                "producto_id, precio_cop, cantidad_base_snapshot, precio_por_base, fuente, "
                "reportante_id, observado_en, estado, estado_original, conjunto_referencia, "
                "idempotency_key) VALUES (:id, :pid, :eid, :prod, :precio, :cant, :ppb, 'usuario', "
                ":uid, :obs, CAST(:est AS estado_confianza), CAST(:est AS estado_confianza), "
                "'sin_referencia', :ik);"
            ),
            reportes_sql,
        )
        await sesion.execute(
            text(
                "INSERT INTO public.precio_vigente (presentacion_id, establecimiento_id, "
                "producto_id, precio_cop, precio_por_base, cantidad_base, sello, "
                "n_reportes_validos, n_fuentes, ultimo_reporte_en, reporte_origen_id) "
                "VALUES (:pid, :eid, :prod, :precio, :ppb, :cant, "
                "'pocos_datos', 1, 1, :obs, :rorig);"
            ),
            vigentes_sql,
        )
        await sesion.execute(
            text(
                "INSERT INTO public.caso_moderacion "
                "(id, tipo, referencia_tabla, referencia_id, prioridad, estado) "
                "VALUES (:cid, 'reporte_dudoso', 'reporte_precio', :rid, 2, 'abierto');"
            ),
            casos_sql,
        )

    return {
        "prod_id": prod_id,
        "pres_ids": [p[0] for p in pres_ids],
        "est_ids": est_ids,
        "pares": pares,
        "tok_alto": token_para_ec02(u_alto),
        "tok_mod": token_para_ec02(u_mod),
    }


async def desactivar_escenario_ec02(datos: dict[str, Any]) -> None:
    """Oculta registros temporales del escenario EC-02 tras finalizar."""
    async with sesion_transaccional() as sesion:
        for tabla, clave in (
            ("public.presentacion SET activa = false", "pres_ids"),
            ("public.establecimiento SET activo = false", "est_ids"),
        ):
            await sesion.execute(
                text(f"UPDATE {tabla} WHERE id = ANY(CAST(:ids AS uuid[]));"),
                {"ids": datos[clave]},
            )
        await sesion.execute(
            text("UPDATE public.producto SET activo = false WHERE id = :pid;"),
            {"pid": datos["prod_id"]},
        )
