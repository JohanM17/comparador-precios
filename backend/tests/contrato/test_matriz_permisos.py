"""Prueba parametrizada de la Matriz de Permisos RBAC (Seccion 6.5 - T-51)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.adaptadores.cache_dos_niveles import CacheDosNiveles
from app.bd import sesion_transaccional
from app.compartido.dependencias import obtener_puerto_cache
from app.config import obtener_configuracion
from app.main import app
from app.modulos.fotos.api import limitador_fotos
from app.modulos.precios.servicio import limitador_escritura
from tests.contrato.ayudantes_rbac import (
    ROLES_RBAC,
    headers_para_rol,
    obtener_ids_semilla,
)


@pytest.fixture(autouse=True)
def _aislar_cache_y_limites() -> Any:
    limitador_escritura.limpiar()
    limitador_fotos.limpiar()
    cache_mem = CacheDosNiveles(ttl_l1_segundos=5.0)
    prev = app.dependency_overrides.get(obtener_puerto_cache)
    app.dependency_overrides[obtener_puerto_cache] = lambda: cache_mem
    yield
    if prev is not None:
        app.dependency_overrides[obtener_puerto_cache] = prev
    else:
        app.dependency_overrides.pop(obtener_puerto_cache, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("clave_rol", "estado_get_pub", "estado_post_corr"),
    [(r, 200, 201) for r in ROLES_RBAC],
)
async def test_matriz_endpoints_publicos(
    clave_rol: str, estado_get_pub: int, estado_post_corr: int
) -> None:
    """Celda 1 (6.5): GET publicos y solicitudes-correccion permiten todos los roles."""
    prod_id, _, est_id = await obtener_ids_semilla()
    headers = await headers_para_rol(clave_rol)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
        for ruta in (
            "/v1/categorias",
            "/v1/productos",
            f"/v1/productos/{prod_id}/comparacion",
            "/v1/establecimientos",
            "/v1/legal/politica-tratamiento",
        ):
            r = await cli.get(ruta, headers=headers)
            assert r.status_code == estado_get_pub, f"{clave_rol} en {ruta} -> {r.text}"

        r_corr = await cli.post(
            f"/v1/establecimientos/{est_id}/solicitudes-correccion",
            headers=headers,
            json={"correo": "vecino@armenia.co", "mensaje": "Horario actualizado sabados"},
        )
        assert r_corr.status_code == estado_post_corr


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("clave_rol", "estado_esp", "codigo_esp"),
    [
        ("anonimo", 401, "NO_AUTENTICADO"),
        ("sin_autorizar", 201, None),
        ("reportante_activa", 200, None),
        ("moderador_activa", 200, None),
        ("suspendida", 403, "CUENTA_SUSPENDIDA"),
        ("bloqueada", 403, "CUENTA_SUSPENDIDA"),
    ],
)
async def test_matriz_autorizacion_datos(
    clave_rol: str, estado_esp: int, codigo_esp: str | None
) -> None:
    """Celda 2 (6.5): POST /v1/mi-cuenta/autorizacion."""
    headers = await headers_para_rol(clave_rol)
    alias = f"aut_{uuid4().hex[:8]}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
        r = await cli.post(
            "/v1/mi-cuenta/autorizacion",
            headers=headers,
            json={"alias": alias, "version_politica": "1.0", "acepta": True},
        )
        assert r.status_code == estado_esp, r.text
        if codigo_esp:
            assert r.json()["codigo"] == codigo_esp


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("clave_rol", "estado_esp", "codigo_esp"),
    [
        ("anonimo", 401, "NO_AUTENTICADO"),
        ("sin_autorizar", 403, "AUTORIZACION_REQUERIDA"),
        ("reportante_activa", 200, None),
        ("moderador_activa", 200, None),
        ("suspendida", 200, None),
        ("bloqueada", 200, None),
    ],
)
async def test_matriz_mi_cuenta_derecho_ley(
    clave_rol: str, estado_esp: int, codigo_esp: str | None
) -> None:
    """Celda 3 (6.5): GET y DELETE /v1/mi-cuenta garantizan derecho ARCO a suspendidas."""
    headers = await headers_para_rol(clave_rol)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
        r_get = await cli.get("/v1/mi-cuenta", headers=headers)
        assert r_get.status_code == estado_esp, r_get.text
        if codigo_esp:
            assert r_get.json()["codigo"] == codigo_esp

        r_del = await cli.delete("/v1/mi-cuenta", headers=headers)
        assert r_del.status_code == estado_esp, r_del.text
        if codigo_esp:
            assert r_del.json()["codigo"] == codigo_esp


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("clave_rol", "estado_esp", "codigo_esp"),
    [
        ("anonimo", 401, "NO_AUTENTICADO"),
        ("sin_autorizar", 403, "AUTORIZACION_REQUERIDA"),
        ("reportante_activa", 201, None),
        ("moderador_activa", 201, None),
        ("suspendida", 403, "CUENTA_SUSPENDIDA"),
        ("bloqueada", 403, "CUENTA_SUSPENDIDA"),
    ],
)
async def test_matriz_reportes_fotos_sugerencias(
    clave_rol: str, estado_esp: int, codigo_esp: str | None
) -> None:
    """Celda 4 (6.5): POST /v1/reportes, /fotos/url-subida y /sugerencias-presentacion."""
    prod_id, pres_id, est_id = await obtener_ids_semilla()
    headers = await headers_para_rol(clave_rol)
    ahora = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
        r_rep = await cli.post(
            "/v1/reportes",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={
                "presentacion_id": pres_id,
                "establecimiento_id": est_id,
                "precio_cop": 3200,
                "observado_en": ahora,
                "foto_ruta": None,
            },
        )
        assert r_rep.status_code == estado_esp, r_rep.text
        if codigo_esp:
            assert r_rep.json()["codigo"] == codigo_esp

        r_foto = await cli.post(
            "/v1/fotos/url-subida",
            headers=headers,
            json={"nombre_archivo": "p.webp", "tipo_mime": "image/webp", "tamano_bytes": 12000},
        )
        assert r_foto.status_code == estado_esp, r_foto.text
        if codigo_esp:
            assert r_foto.json()["codigo"] == codigo_esp

        r_sug = await cli.post(
            "/v1/sugerencias-presentacion",
            headers=headers,
            json={"producto_id": prod_id, "texto_libre": "Presentacion prueba RBAC 750 g"},
        )
        assert r_sug.status_code == estado_esp, r_sug.text
        if codigo_esp:
            assert r_sug.json()["codigo"] == codigo_esp


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("clave_rol", "estado_esp", "codigo_esp"),
    [
        ("anonimo", 401, "NO_AUTENTICADO"),
        ("sin_autorizar", 403, "PROHIBIDO"),
        ("reportante_activa", 403, "PROHIBIDO"),
        ("moderador_activa", 200, None),
        ("suspendida", 403, "CUENTA_SUSPENDIDA"),
        ("bloqueada", 403, "CUENTA_SUSPENDIDA"),
    ],
)
async def test_matriz_moderacion(clave_rol: str, estado_esp: int, codigo_esp: str | None) -> None:
    """Celda 7 (6.5): Endpoints /v1/moderacion/* exclusivos de moderador activo."""
    headers = await headers_para_rol(clave_rol)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
        rutas_mod = (
            "/v1/moderacion/casos",
            "/v1/moderacion/parametros",
            "/v1/moderacion/auditoria",
        )
        for ruta in rutas_mod:
            r = await cli.get(ruta, headers=headers)
            assert r.status_code == estado_esp, f"{clave_rol} en {ruta} -> {r.text}"
            if codigo_esp:
                assert r.json()["codigo"] == codigo_esp


async def _crear_establecimiento_reclamable() -> str:
    """Crea un establecimiento sin dueno para probar el reclamo de forma aislada."""
    sufijo = uuid4().hex[:8]
    async with sesion_transaccional() as sesion:
        return str(
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
                        "nombre": f"Reclamo RBAC {sufijo}",
                        "direccion": f"Calle RBAC {sufijo}",
                    },
                )
            ).scalar_one()
        )


async def _borrar_establecimiento_reclamable(establecimiento_id: str) -> None:
    async with sesion_transaccional() as sesion:
        await sesion.execute(
            text("""
                DELETE FROM public.solicitud_verificacion_comercio
                WHERE establecimiento_id = :id;
            """),
            {"id": establecimiento_id},
        )
        await sesion.execute(
            text("DELETE FROM public.establecimiento WHERE id = :id;"),
            {"id": establecimiento_id},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("clave_rol", "estado_esp", "codigo_esp"),
    [
        ("anonimo", 401, "NO_AUTENTICADO"),
        ("sin_autorizar", 403, "AUTORIZACION_REQUERIDA"),
        ("reportante_activa", 201, None),
        ("moderador_activa", 201, None),
        ("suspendida", 403, "CUENTA_SUSPENDIDA"),
        ("bloqueada", 403, "CUENTA_SUSPENDIDA"),
    ],
)
async def test_matriz_reclamo_comercio(
    clave_rol: str, estado_esp: int, codigo_esp: str | None
) -> None:
    """Celda 9: reclamar titularidad exige autorizacion de datos (Ley 1581)."""
    est_id = await _crear_establecimiento_reclamable()
    try:
        headers = await headers_para_rol(clave_rol)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
            r = await cli.post(
                "/v1/comercio/reclamos",
                headers=headers,
                json={
                    "establecimiento_id": est_id,
                    "telefono_contacto": "3001234567",
                    "mensaje": "Soy el dueno y quiero publicar precios oficiales",
                },
            )
        assert r.status_code == estado_esp, r.text
        if codigo_esp:
            assert r.json()["codigo"] == codigo_esp
    finally:
        await _borrar_establecimiento_reclamable(est_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cabecera_job", "con_jwt_mod", "estado_esp"),
    [
        (None, False, 401),
        (None, True, 401),
        ("invalido", False, 401),
        ("valido", False, 200),
    ],
)
async def test_matriz_jobs_internos(
    cabecera_job: str | None, con_jwt_mod: bool, estado_esp: int
) -> None:
    """Celda 8 (6.5): POST /internal/jobs/{nombre} exige X-Job-Token valido."""
    cfg = obtener_configuracion()
    headers: dict[str, str] = {}
    if cabecera_job == "valido":
        headers["X-Job-Token"] = cfg.JOB_TOKEN
    elif cabecera_job is not None:
        headers["X-Job-Token"] = "cabecera-erronea-123"
    if con_jwt_mod:
        headers.update(await headers_para_rol("moderador_activa"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
        r = await cli.post("/internal/jobs/ping_bd", headers=headers)
        assert r.status_code == estado_esp, r.text
