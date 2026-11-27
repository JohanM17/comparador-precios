"""Pruebas de la baja de cuenta: autenticacion, Auth externo y orden de commit."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from app.adaptadores.auth_supabase import AdaptadorAuthSupabase
from app.compartido import seguridad
from app.compartido.errores import NoAutenticadoError
from app.compartido.seguridad import (
    UsuarioAutenticado,
    requiere_usuario,
    requiere_usuario_autenticado_base,
)
from app.config import Configuracion
from app.modulos.cuentas import api as cuentas_api
from app.modulos.cuentas.esquemas import EliminarCuentaRespuesta
from app.modulos.cuentas.servicio import ServicioCuentas

USUARIO_ID = UUID(int=40)


def _usuario(estado: str = "activa") -> UsuarioAutenticado:
    return UsuarioAutenticado(
        id=USUARIO_ID,
        email="titular@armenia.co",
        rol="moderador",
        estado=estado,
    )


def test_requiere_usuario_rechaza_cuenta_eliminada() -> None:
    """Una cuenta suprimida no puede volver a operar: recibe 401, no 403."""
    with pytest.raises(NoAutenticadoError) as exc:
        requiere_usuario(_usuario("eliminada"))

    assert exc.value.status == 401
    assert exc.value.codigo == "NO_AUTENTICADO"


def test_requiere_usuario_permite_cuenta_activa() -> None:
    """La misma dependencia sigue permitiendo una cuenta activa."""
    assert requiere_usuario(_usuario("activa")).estado == "activa"


@pytest.mark.asyncio
async def test_la_dependencia_base_rechaza_cuenta_eliminada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Toda ruta con la dependencia base cierra el paso a una cuenta eliminada."""

    async def consultar_perfil(*args: Any, **kwargs: Any) -> tuple[str, str]:
        return "reportante", "eliminada"

    monkeypatch.setattr(seguridad, "decodificar_token", lambda token: {"sub": str(USUARIO_ID)})
    monkeypatch.setattr(seguridad, "_consultar_perfil_bd", consultar_perfil)

    with pytest.raises(NoAutenticadoError) as exc:
        await requiere_usuario_autenticado_base(
            f"Bearer token-{USUARIO_ID}",
            object(),  # type: ignore[arg-type]
        )

    assert exc.value.status == 401


class _AuthFalso:
    """Puerto de Auth que registra la llamada y puede fallar."""

    def __init__(self, resultado: bool = True, falla: bool = False) -> None:
        self.resultado = resultado
        self.falla = falla
        self.llamadas: list[UUID] = []

    async def eliminar_usuario(self, usuario_id: UUID) -> bool:
        self.llamadas.append(usuario_id)
        if self.falla:
            raise RuntimeError("fallo de red simulado")
        return self.resultado


@pytest.mark.asyncio
async def test_eliminar_credencial_auth_llama_al_puerto() -> None:
    """La credencial se elimina con el identificador del titular."""
    auth = _AuthFalso()
    servicio = ServicioCuentas(sesion=object(), puerto_auth_admin=auth)  # type: ignore[arg-type]

    assert await servicio.eliminar_credencial_auth(USUARIO_ID) is True
    assert auth.llamadas == [USUARIO_ID]


@pytest.mark.asyncio
async def test_eliminar_credencial_auth_es_best_effort() -> None:
    """Un fallo del Auth externo no propaga excepcion ni rompe la baja local."""
    auth = _AuthFalso(falla=True)
    servicio = ServicioCuentas(sesion=object(), puerto_auth_admin=auth)  # type: ignore[arg-type]

    assert await servicio.eliminar_credencial_auth(USUARIO_ID) is False


@pytest.mark.asyncio
async def test_la_api_elimina_la_credencial_despues_del_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El orden es: abrir sesion -> baja en BD -> commit -> borrar credencial."""
    eventos: list[str] = []

    @asynccontextmanager
    async def sesion_falsa() -> AsyncGenerator[Any, None]:
        eventos.append("begin")
        yield object()
        eventos.append("commit")

    class _ServicioFalso:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        async def eliminar_mi_cuenta(self, usuario: UsuarioAutenticado) -> EliminarCuentaRespuesta:
            eventos.append("bd")
            return EliminarCuentaRespuesta(
                mensaje="Cuenta eliminada",
                usuario_id=usuario.id,
                estado="eliminada",
            )

        async def invalidar_cache_baja(self) -> None:
            eventos.append("cache")

        async def eliminar_credencial_auth(self, usuario_id: UUID) -> bool:
            eventos.append("auth")
            return True

    monkeypatch.setattr(cuentas_api, "sesion_transaccional", sesion_falsa)
    monkeypatch.setattr(cuentas_api, "ServicioCuentas", _ServicioFalso)

    respuesta = await cuentas_api.eliminar_cuenta_usuario(
        _usuario(),
        object(),
        object(),
        object(),  # type: ignore[arg-type]
    )

    assert respuesta.estado == "eliminada"
    assert eventos == ["begin", "bd", "commit", "cache", "auth"]


def _config_auth() -> Configuracion:
    return Configuracion(
        SUPABASE_URL="https://proyecto.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-de-prueba",
    )


@pytest.mark.asyncio
async def test_adaptador_auth_llama_al_endpoint_admin_con_service_role() -> None:
    """El adaptador usa DELETE /auth/v1/admin/users/{id} con la service role key."""
    capturado: dict[str, Any] = {}

    def manejador(request: httpx.Request) -> httpx.Response:
        capturado["metodo"] = request.method
        capturado["url"] = str(request.url)
        capturado["authorization"] = request.headers.get("authorization")
        capturado["apikey"] = request.headers.get("apikey")
        return httpx.Response(200)

    cliente = httpx.AsyncClient(transport=httpx.MockTransport(manejador))
    adaptador = AdaptadorAuthSupabase(cfg=_config_auth(), cliente_http=cliente)
    try:
        assert await adaptador.eliminar_usuario(USUARIO_ID) is True
    finally:
        await cliente.aclose()

    assert capturado["metodo"] == "DELETE"
    assert capturado["url"] == (f"https://proyecto.supabase.co/auth/v1/admin/users/{USUARIO_ID}")
    assert capturado["authorization"] == "Bearer service-role-de-prueba"
    assert capturado["apikey"] == "service-role-de-prueba"


@pytest.mark.asyncio
async def test_adaptador_auth_retorna_false_sin_pii_en_el_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Un 500 se reporta como warning generico, sin el identificador del titular."""
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    adaptador = AdaptadorAuthSupabase(cfg=_config_auth(), cliente_http=cliente)
    with caplog.at_level(logging.WARNING, logger="app"):
        try:
            assert await adaptador.eliminar_usuario(USUARIO_ID) is False
        finally:
            await cliente.aclose()

    assert "credencial de autenticacion" in caplog.text
    assert str(USUARIO_ID) not in caplog.text


@pytest.mark.asyncio
async def test_adaptador_auth_sin_configuracion_no_llama_http(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sin URL o service role se omite la llamada y se deja un warning generico."""
    cfg = Configuracion(SUPABASE_URL="", SUPABASE_SERVICE_ROLE_KEY="")
    adaptador = AdaptadorAuthSupabase(cfg=cfg)
    with caplog.at_level(logging.WARNING, logger="app"):
        assert await adaptador.eliminar_usuario(uuid4()) is False

    assert "configuracion incompleta" in caplog.text
