"""Aplicacion principal FastAPI y definicion de endpoints del nucleo."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

from app.adaptadores.open_food_facts import AdaptadorOpenFoodFacts
from app.adaptadores.storage_supabase import AdaptadorStorageSupabase
from app.bd import cerrar_conexiones, verificar_conexion_bd
from app.compartido.errores import (
    DetalleProblema,
    ServicioNoDisponibleError,
    registrar_manejadores_errores,
)
from app.compartido.logging_cfg import (
    LoggingAccesoMiddleware,
    RequestIdMiddleware,
    configurar_logging,
)
from app.compartido.seguridad import UsuarioAutenticado, requiere_rol, requiere_usuario
from app.config import obtener_configuracion
from app.modulos.catalogo.api import router as catalogo_router
from app.modulos.cuentas.api import (
    obtener_puerto_almacenamiento as obtener_almacenamiento_cuentas,
)
from app.modulos.cuentas.api import (
    router as cuentas_router,
)
from app.modulos.establecimientos.api import router as establecimientos_router
from app.modulos.fotos.api import (
    obtener_puerto_almacenamiento as obtener_almacenamiento_fotos,
)
from app.modulos.fotos.api import (
    router as fotos_router,
)
from app.modulos.moderacion.api import (
    obtener_puerto_catalogo,
)
from app.modulos.moderacion.api import (
    router as moderacion_router,
)


class RespuestaSalud(BaseModel):
    estado: str
    version: str
    entorno: str


class RespuestaListo(BaseModel):
    estado: str
    bd: str
    cache: str


class RespuestaUsuario(BaseModel):
    usuario_id: str
    email: str | None
    rol: str


async def _verificar_redis() -> str:
    """Verifica el comando PING en Redis sin interrumpir el servicio si falla."""
    cfg = obtener_configuracion()
    if not cfg.REDIS_URL:
        return "desactivado"

    import redis.asyncio as aioredis

    cliente = None
    try:
        cliente = aioredis.from_url(  # type: ignore[no-untyped-call]
            cfg.REDIS_URL,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
        await cliente.ping()
        return "conectado"
    except Exception:
        # ADR-015 y ADR-016: Redis fuera del camino critico, falla graciosamente
        return "degradado"
    finally:
        if cliente is not None:
            await cliente.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicacion: inicio y liberacion de recursos."""
    configurar_logging()
    yield
    await cerrar_conexiones()


def create_app() -> FastAPI:
    """Fabrica de la aplicacion FastAPI con configuracion integral."""
    cfg = obtener_configuracion()

    app = FastAPI(
        title="API Comparador de Precios Armenia",
        version="1.0.0",
        description="Backend API para la plataforma colaborativa de comparacion de precios",
        lifespan=lifespan,
    )

    # Middlewares en orden de ejecucion (el ultimo agregado es el primero en recibir)
    app.add_middleware(LoggingAccesoMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Manejo de errores estandar RFC 9457
    registrar_manejadores_errores(app)

    # Router principal /v1
    v1_router = APIRouter(prefix="/v1")

    @v1_router.get("/salud", response_model=RespuestaSalud, summary="Liveness probe")
    async def salud() -> dict[str, str]:
        return {"estado": "ok", "version": "1.0.0", "entorno": cfg.ENTORNO}

    @v1_router.get("/salud/listo", response_model=RespuestaListo, summary="Readiness probe")
    async def salud_listo() -> dict[str, str]:
        bd_ok = await verificar_conexion_bd()
        if not bd_ok:
            raise ServicioNoDisponibleError("La base de datos PostgreSQL no responde.")

        estado_cache = await _verificar_redis()
        return {"estado": "listo", "bd": "conectado", "cache": estado_cache}

    # Rutas protegidas para validacion de seguridad y roles en pruebas
    @v1_router.get("/auth/perfil-actual", response_model=RespuestaUsuario)
    async def perfil_actual(
        usuario: Annotated[UsuarioAutenticado, Depends(requiere_usuario)],
    ) -> dict[str, Any]:
        return {
            "usuario_id": str(usuario.id),
            "email": usuario.email,
            "rol": usuario.rol,
        }

    @v1_router.get("/auth/solo-moderador", response_model=RespuestaUsuario)
    async def solo_moderador(
        usuario: Annotated[UsuarioAutenticado, Depends(requiere_rol("moderador", "admin"))],
    ) -> dict[str, Any]:
        return {
            "usuario_id": str(usuario.id),
            "email": usuario.email,
            "rol": usuario.rol,
        }

    adaptador_off = AdaptadorOpenFoodFacts()
    adaptador_storage = AdaptadorStorageSupabase()
    app.dependency_overrides[obtener_puerto_catalogo] = lambda: adaptador_off
    app.dependency_overrides[obtener_almacenamiento_cuentas] = lambda: adaptador_storage
    app.dependency_overrides[obtener_almacenamiento_fotos] = lambda: adaptador_storage

    v1_router.include_router(catalogo_router)
    v1_router.include_router(establecimientos_router)
    v1_router.include_router(moderacion_router)
    v1_router.include_router(cuentas_router)
    v1_router.include_router(fotos_router)
    app.include_router(v1_router)

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        )
        schemas = schema.setdefault("components", {}).setdefault("schemas", {})
        schemas["DetalleProblema"] = DetalleProblema.model_json_schema()
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app


app = create_app()
