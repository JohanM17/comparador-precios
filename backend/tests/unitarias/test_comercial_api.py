"""Pruebas de contrato y rol de la cola de reclamos de comercio (T-67).

No tocan PostgreSQL: la autenticacion y el servicio se reemplazan por dobles.
La consulta del repositorio se verifica con una sesion falsa que conserva el
SQL ejecutado para comprobar que solo trae pendientes y en orden FIFO.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.compartido.errores import registrar_manejadores_errores
from app.compartido.seguridad import UsuarioAutenticado, requiere_usuario_autenticado_base
from app.modulos.comercial import repositorio
from app.modulos.comercial.api import obtener_servicio_comercial
from app.modulos.comercial.api import router as comercial_router


def _usuario(rol: str) -> UsuarioAutenticado:
    return UsuarioAutenticado(
        id=uuid4(),
        email=f"{rol}@armenia.co",
        rol=rol,
        estado="activa",
    )


def _solicitud(indice: int) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "establecimiento_id": uuid4(),
        "establecimiento_nombre": f"Tienda {indice}",
        "establecimiento_barrio": "Centro",
        "establecimiento_direccion": "Cra 14 # 18-22",
        "solicitante_alias": f"tendero_{indice}",
        "telefono_contacto": "3001234567",
        "mensaje": "Soy el dueno, atiendo de 7 a 8.",
        "estado": "pendiente",
        "creado_en": datetime.now(UTC),
    }


class _ServicioFalso:
    """Doble del servicio comercial que registra las llamadas recibidas."""

    def __init__(self, solicitudes: list[dict[str, Any]]) -> None:
        self.solicitudes = solicitudes
        self.limites: list[int] = []
        self.roles: list[str] = []

    async def listar_solicitudes_pendientes(
        self, usuario: UsuarioAutenticado, limite: int
    ) -> list[dict[str, Any]]:
        self.roles.append(usuario.rol)
        self.limites.append(limite)
        return self.solicitudes


def _crear_app(servicio: _ServicioFalso, usuario: UsuarioAutenticado) -> FastAPI:
    app = FastAPI()
    registrar_manejadores_errores(app)
    app.include_router(comercial_router, prefix="/v1")
    app.dependency_overrides[obtener_servicio_comercial] = lambda: servicio
    app.dependency_overrides[requiere_usuario_autenticado_base] = lambda: usuario
    return app


async def _listar(app: FastAPI, ruta: str = "/v1/moderacion/comercios") -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        return await cliente.get(ruta)


@pytest.mark.asyncio
async def test_moderador_puede_ver_la_cola_de_reclamos() -> None:
    """Un moderador activo recibe 200 y el total de reclamos pendientes."""
    servicio = _ServicioFalso([_solicitud(1), _solicitud(2)])
    app = _crear_app(servicio, _usuario("moderador"))

    respuesta = await _listar(app)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 2
    assert [dato["solicitante_alias"] for dato in cuerpo["datos"]] == ["tendero_1", "tendero_2"]
    assert servicio.roles == ["moderador"]


@pytest.mark.asyncio
async def test_reportante_no_puede_ver_la_cola_de_reclamos() -> None:
    """Un reportante recibe 403 y el servicio ni siquiera se invoca."""
    servicio = _ServicioFalso([_solicitud(1)])
    app = _crear_app(servicio, _usuario("reportante"))

    respuesta = await _listar(app)

    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "PROHIBIDO"
    assert servicio.roles == []


@pytest.mark.asyncio
async def test_admin_puede_ver_la_cola_de_reclamos() -> None:
    """El rol admin conserva acceso a la revision de reclamos."""
    servicio = _ServicioFalso([_solicitud(1)])
    app = _crear_app(servicio, _usuario("admin"))

    respuesta = await _listar(app)

    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1
    assert servicio.roles == ["admin"]


@pytest.mark.asyncio
async def test_listar_reclamos_respeta_el_limite_de_la_consulta() -> None:
    """El parametro limite de la ruta llega al servicio sin alterarse."""
    servicio = _ServicioFalso([_solicitud(1)])
    app = _crear_app(servicio, _usuario("moderador"))

    respuesta = await _listar(app, "/v1/moderacion/comercios?limite=7")

    assert respuesta.status_code == 200
    assert servicio.limites == [7]


@pytest.mark.asyncio
async def test_listar_reclamos_rechaza_limite_invalido() -> None:
    """Un limite fuera de rango se rechaza antes de consultar la base."""
    servicio = _ServicioFalso([])
    app = _crear_app(servicio, _usuario("moderador"))

    respuesta = await _listar(app, "/v1/moderacion/comercios?limite=0")

    assert respuesta.status_code == 422
    assert servicio.limites == []


class _ResultadoFalso:
    """Resultado de SQLAlchemy con filas ya preparadas."""

    def __init__(self, filas: list[SimpleNamespace]) -> None:
        self._filas = filas

    def fetchall(self) -> list[SimpleNamespace]:
        return self._filas


class _SesionFalsa:
    """Sesion minima que conserva el SQL y los parametros ejecutados."""

    def __init__(self, filas: list[SimpleNamespace]) -> None:
        self.filas = filas
        self.sql = ""
        self.parametros: dict[str, Any] = {}

    async def execute(self, sql: Any, parametros: dict[str, Any]) -> _ResultadoFalso:
        self.sql = str(sql)
        self.parametros = parametros
        return _ResultadoFalso(self.filas)


@pytest.mark.asyncio
async def test_repositorio_solo_devuelve_pendientes_en_orden_fifo() -> None:
    """La consulta filtra por estado pendiente y ordena del mas antiguo al mas nuevo."""
    primera = _solicitud(1)
    segunda = _solicitud(2)
    sesion = _SesionFalsa(
        [
            SimpleNamespace(_mapping=primera),
            SimpleNamespace(_mapping=segunda),
        ]
    )

    filas = await repositorio.listar_solicitudes_pendientes(sesion, limite=50)  # type: ignore[arg-type]

    assert "WHERE s.estado = 'pendiente'" in sesion.sql
    assert "ORDER BY s.creado_en ASC" in sesion.sql
    assert sesion.parametros == {"limite": 50}
    assert [fila["solicitante_alias"] for fila in filas] == ["tendero_1", "tendero_2"]
    assert all(isinstance(fila["id"], UUID) for fila in filas)
