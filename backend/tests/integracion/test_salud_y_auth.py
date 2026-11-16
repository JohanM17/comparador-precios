"""Pruebas de integracion para endpoints de salud, RFC 9457 y seguridad JWT."""

from __future__ import annotations

import io
import logging
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.compartido.logging_cfg import FiltroPrivacidadLey1581
from app.config import obtener_configuracion
from app.main import app

RUTA_PERFIL = "/v1/auth/perfil-actual"
RUTA_MODERADOR = "/v1/auth/solo-moderador"
TIPO_PROBLEM_JSON = "application/problem+json"


@pytest.mark.asyncio
async def test_salud_liveness() -> None:
    """Verifica que /v1/salud responde 200 OK con la version y cabecera X-Request-ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as cliente:
        res = await cliente.get("/v1/salud")
        assert res.status_code == 200
        assert "X-Request-ID" in res.headers
        cuerpo = res.json()
        assert cuerpo["estado"] == "ok"
        assert cuerpo["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_salud_readiness() -> None:
    """Verifica conectividad en vivo con PostgreSQL y Redis a traves de /v1/salud/listo."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as cliente:
        res = await cliente.get("/v1/salud/listo")
        assert res.status_code == 200
        cuerpo = res.json()
        assert cuerpo["estado"] == "listo"
        assert cuerpo["bd"] == "conectado"
        assert cuerpo["cache"] in ("conectado", "degradado", "desactivado")


@pytest.mark.asyncio
async def test_error_recurso_inexistente_rfc9457() -> None:
    """Verifica que un recurso 404 devuelva estructura RFC 9457 con request_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as cliente:
        res = await cliente.get("/v1/ruta-que-no-existe-para-prueba")
        assert res.status_code == 404
        assert res.headers["content-type"] == TIPO_PROBLEM_JSON
        assert "X-Request-ID" in res.headers
        cuerpo = res.json()
        assert cuerpo["status"] == 404
        assert cuerpo["codigo"] == "NO_ENCONTRADO"
        assert cuerpo["request_id"] == res.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_logs_redactan_coordenadas_y_datos_sensibles() -> None:
    """Verifica que el logger de acceso jamas registre coordenadas ni correos (Ley 1581)."""
    stream = io.StringIO()
    manejador = logging.StreamHandler(stream)
    manejador.addFilter(FiltroPrivacidadLey1581())
    logger_acceso = logging.getLogger("app.acceso")
    logger_acceso.setLevel(logging.INFO)
    logger_acceso.addHandler(manejador)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as cliente:
            res = await cliente.get("/v1/salud?lat=4.5339&lng=-75.6811&email=test@ejemplo.com")
            assert res.status_code == 200

        manejador.flush()
        salida_logs = stream.getvalue()

        # Comprobacion estricta: ninguna coordenada o email debe existir en los logs
        assert "4.5339" not in salida_logs
        assert "-75.6811" not in salida_logs
        assert "test@ejemplo.com" not in salida_logs
        assert "[REDACTADO_COORD]" in salida_logs
    finally:
        logger_acceso.removeHandler(manejador)


@pytest.mark.asyncio
async def test_rutas_protegidas_rechazan_sin_token() -> None:
    """Verifica que peticiones sin cabecera Authorization sean rechazadas con 401 RFC 9457."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as cliente:
        res = await cliente.get(RUTA_PERFIL)
        assert res.status_code == 401
        assert res.headers["content-type"] == TIPO_PROBLEM_JSON
        cuerpo = res.json()
        assert cuerpo["codigo"] == "NO_AUTENTICADO"
        assert cuerpo["status"] == 401


@pytest.mark.asyncio
async def test_rutas_protegidas_rechazan_token_invalido() -> None:
    """Verifica que peticiones con token malformado o falso sean rechazadas con 401 RFC 9457."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as cliente:
        res = await cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": "Bearer token.falso.invalido"},
        )
        assert res.status_code == 401
        assert res.headers["content-type"] == TIPO_PROBLEM_JSON
        cuerpo = res.json()
        assert cuerpo["codigo"] == "NO_AUTENTICADO"


@pytest.mark.asyncio
async def test_autenticacion_jwt_y_rechazo_rol_prohibido() -> None:
    """Verifica validacion de firma JWT HS256 local y rechazo 403 por rol insuficiente."""
    cfg = obtener_configuracion()
    secreto = cfg.SUPABASE_JWT_SECRET or "secreto_jwt_prueba_local_32_bytes_min"
    cfg.SUPABASE_JWT_SECRET = secreto

    usuario_id = str(uuid4())
    token_consumidor = jwt.encode(
        {"sub": usuario_id, "email": "consumidor@ejemplo.com"},
        secreto,
        algorithm="HS256",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as cliente:
        # 1. El usuario autenticado accede a su perfil
        res_perfil = await cliente.get(
            RUTA_PERFIL,
            headers={"Authorization": f"Bearer {token_consumidor}"},
        )
        assert res_perfil.status_code == 200
        datos_perfil = res_perfil.json()
        assert datos_perfil["usuario_id"] == usuario_id

        # 2. El usuario con rol 'consumidor' intenta acceder a endpoint de moderador -> 403
        res_mod = await cliente.get(
            RUTA_MODERADOR,
            headers={"Authorization": f"Bearer {token_consumidor}"},
        )
        assert res_mod.status_code == 403
        assert res_mod.headers["content-type"] == TIPO_PROBLEM_JSON
        cuerpo_mod = res_mod.json()
        assert cuerpo_mod["codigo"] == "PROHIBIDO"
