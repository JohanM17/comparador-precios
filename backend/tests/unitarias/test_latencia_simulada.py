"""Pruebas unitarias del middleware de latencia simulada (Tarea T-123)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.compartido import latencia_simulada
from app.compartido.latencia_simulada import LatenciaSimuladaMiddleware
from app.compartido.logging_cfg import LoggingAccesoMiddleware, RequestIdMiddleware
from app.config import Configuracion


@pytest.fixture
def esperas(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Reemplaza asyncio.sleep por un espia para no esperar durante las pruebas."""
    llamadas: list[float] = []

    async def dormir(segundos: float) -> None:
        llamadas.append(segundos)

    monkeypatch.setattr(latencia_simulada, "asyncio", SimpleNamespace(sleep=dormir))
    return llamadas


def _crear_app(
    *,
    milisegundos: int,
    entorno: str,
    rutas: tuple[str, ...] = ("/v1/",),
) -> FastAPI:
    """Construye una app minima con el middleware bajo prueba."""
    aplicacion = FastAPI()
    aplicacion.add_middleware(
        LatenciaSimuladaMiddleware,
        milisegundos=milisegundos,
        entorno=entorno,
        rutas=rutas,
    )

    @aplicacion.get("/v1/productos/{producto_id}/comparacion")
    async def comparacion(producto_id: str) -> dict[str, str]:
        return {"producto_id": producto_id, "estado": "ok"}

    @aplicacion.get("/v1/salud")
    async def salud() -> dict[str, str]:
        return {"estado": "ok"}

    @aplicacion.get("/v1/productos-destacados")
    async def productos_destacados() -> dict[str, str]:
        return {"estado": "ok"}

    @aplicacion.get("/otra")
    async def otra() -> dict[str, str]:
        return {"estado": "ok"}

    return aplicacion


@pytest.mark.parametrize("entorno", ["production", "PRODUCTION", " production "])
def test_produccion_no_duerme(
    esperas: list[float],
    entorno: str,
) -> None:
    """En produccion la variable se ignora aunque tenga un valor positivo."""
    aplicacion = _crear_app(milisegundos=3000, entorno=entorno)

    with TestClient(aplicacion) as cliente:
        respuesta = cliente.get("/v1/productos/abc/comparacion")

    assert respuesta.status_code == 200
    assert esperas == []


@pytest.mark.parametrize("milisegundos", [0, -1, -3000])
def test_valor_no_positivo_no_duerme(
    esperas: list[float],
    milisegundos: int,
) -> None:
    """Cero y los valores negativos se tratan como latencia desactivada."""
    aplicacion = _crear_app(milisegundos=milisegundos, entorno="pruebas")

    with TestClient(aplicacion) as cliente:
        respuesta = cliente.get("/v1/productos/abc/comparacion")

    assert respuesta.status_code == 200
    assert esperas == []


@pytest.mark.parametrize(("milisegundos", "segundos"), [(3000, 3.0), (250, 0.25)])
def test_pruebas_duerme_lo_configurado(
    esperas: list[float],
    milisegundos: int,
    segundos: float,
) -> None:
    """En pruebas convierte milisegundos a segundos antes de esperar."""
    aplicacion = _crear_app(milisegundos=milisegundos, entorno="pruebas")

    with TestClient(aplicacion) as cliente:
        respuesta = cliente.get("/v1/productos/abc/comparacion")

    assert respuesta.status_code == 200
    assert esperas == pytest.approx([segundos])


def test_ruta_fuera_del_filtro_no_duerme(esperas: list[float]) -> None:
    """Solo las rutas configuradas reciben la latencia artificial."""
    aplicacion = _crear_app(
        milisegundos=3000,
        entorno="pruebas",
        rutas=("/v1/productos",),
    )

    with TestClient(aplicacion) as cliente:
        assert cliente.get("/v1/salud").status_code == 200
        assert cliente.get("/otra").status_code == 200
        assert cliente.get("/v1/productos/abc/comparacion").status_code == 200

    assert esperas == pytest.approx([3.0])


def test_prefijo_no_coincide_con_rutas_parecidas(esperas: list[float]) -> None:
    """La comparacion es por segmentos, no por texto parcial."""
    aplicacion = _crear_app(
        milisegundos=3000,
        entorno="pruebas",
        rutas=("/v1/productos",),
    )

    with TestClient(aplicacion) as cliente:
        assert cliente.get("/v1/productos-destacados").status_code == 200

    assert esperas == []


def test_respuesta_pasa_intacta(esperas: list[float]) -> None:
    """La espera no altera el estado ni el cuerpo de la respuesta."""
    aplicacion = _crear_app(milisegundos=3000, entorno="pruebas")

    with TestClient(aplicacion) as cliente:
        respuesta = cliente.get("/v1/productos/abc/comparacion")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"producto_id": "abc", "estado": "ok"}
    assert esperas == pytest.approx([3.0])


def test_no_registra_datos_sensibles(
    esperas: list[float],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El middleware no escribe trazas con la URL, coordenadas ni correos."""
    monkeypatch.setattr(logging.getLogger("httpx"), "disabled", True)
    aplicacion = _crear_app(milisegundos=3000, entorno="pruebas")

    with caplog.at_level(logging.DEBUG):
        with TestClient(aplicacion) as cliente:
            respuesta = cliente.get(
                "/v1/productos/abc/comparacion?lat=4.53&lng=-75.68&email=persona%40example.com"
            )

    assert respuesta.status_code == 200
    registros_propios = [
        registro
        for registro in caplog.records
        if registro.name == "app"
        or registro.name.startswith("app.")
        or registro.name == latencia_simulada.__name__
    ]
    assert registros_propios == []
    texto = "\n".join(registro.getMessage() for registro in caplog.records)
    assert "4.53" not in texto
    assert "-75.68" not in texto
    assert "persona%40example.com" not in texto
    assert esperas == pytest.approx([3.0])


def test_create_app_registra_la_latencia_con_la_configuracion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La fabrica de la app conecta la variable de entorno y las rutas de negocio."""
    from app import main as modulo_main

    configuracion = Configuracion(
        _env_file=None,
        ENTORNO="pruebas",
        SIMULAR_LATENCIA_MS=3000,
    )
    monkeypatch.setattr(modulo_main, "obtener_configuracion", lambda: configuracion)

    aplicacion = modulo_main.create_app()

    registro = next(
        middleware
        for middleware in aplicacion.user_middleware
        if middleware.cls is LatenciaSimuladaMiddleware
    )
    assert registro.kwargs["milisegundos"] == 3000
    assert registro.kwargs["entorno"] == "pruebas"
    assert registro.kwargs["rutas"] == modulo_main.RUTAS_LATENCIA_SIMULADA
    assert "/v1/productos" in modulo_main.RUTAS_LATENCIA_SIMULADA
    assert "/v1/salud" not in modulo_main.RUTAS_LATENCIA_SIMULADA

    tipos = [middleware.cls for middleware in aplicacion.user_middleware]
    assert tipos.index(RequestIdMiddleware) < tipos.index(LoggingAccesoMiddleware)
    assert tipos.index(LoggingAccesoMiddleware) < tipos.index(LatenciaSimuladaMiddleware)
