"""Pruebas de integracion de telemetria sin colector OTLP ni escritura en BD (T-120/T-124)."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from opentelemetry import trace as otel_trace
from opentelemetry._logs import _internal as otel_logs_internal
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import _internal as otel_metrics_internal
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from opentelemetry.util._once import Once

from app import main as modulo_main
from app.compartido import telemetria
from app.compartido.errores import ValidacionError
from app.compartido.logging_cfg import (
    FiltroCorrelacionTrazas,
    FiltroPrivacidadLey1581,
    LoggingAccesoMiddleware,
    RequestIdMiddleware,
    configurar_logging,
)
from app.compartido.seguridad import UsuarioAutenticado
from app.config import Configuracion
from app.dominio.parametros import ParametrosDominio
from app.dominio.riesgo import EvaluacionReporte
from app.modulos.precios import repositorio
from app.modulos.precios import servicio as modulo_servicio
from app.modulos.precios import servicio_comparacion as modulo_comparacion
from app.modulos.precios.esquemas import CrearReporteEntrada
from app.modulos.precios.servicio import ServicioPrecios
from app.modulos.precios.servicio_comparacion import ServicioComparacion

_CLAVES_PROHIBIDAS = frozenset(
    {
        "lat",
        "lng",
        "latitude",
        "longitude",
        "reportante_id",
        "alias",
        "email",
        "ip",
        "client_ip",
        "ip_address",
        "net.peer.ip",
        "client.address",
        "huella_red",
        "foto_ruta",
        "foto_prueba_path",
        "body",
        "request.body",
        "response.body",
        "http.request.body",
        "http.response.body",
        "authorization",
        "cookie",
        "set-cookie",
        "http.request.header.authorization",
        "http.request.header.cookie",
    }
)

_VALORES_PROHIBIDOS = (
    "persona@example.com",
    "persona%40example.com",
    "lat=4.53",
    "lng=-75.68",
    "lat%3D4.53",
    "lng%3D-75.68",
    "token-secreto",
    "sesion=abc",
)


@pytest.fixture(autouse=True)
def _habilitar_sdk_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aisla la suite de un OTEL_SDK_DISABLED=true del entorno del operador."""
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")


def _configuracion(**cambios: Any) -> Configuracion:
    """Construye una configuracion sin leer el archivo .env real."""
    return Configuracion(_env_file=None, **cambios)


def _proveedor_de_telemetria(exportador: SpanExporter) -> TracerProvider:
    """Crea un provider que aplica la sanitizacion real antes de exportar."""
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    proveedor.add_span_processor(
        telemetria.ProcesadorErroresPrimero(
            SimpleSpanProcessor(exportador),
            ratio_exitos=1.0,
        )
    )
    return proveedor


def _texto_de_span(span: ReadableSpan) -> str:
    """Serializa atributos, eventos y estado para buscar PII en un span."""
    partes = [str(dict(span.attributes or {}))]
    if span.status.description:
        partes.append(span.status.description)
    for evento in span.events:
        partes.append(f"{evento.name}:{dict(evento.attributes or {})}")
    return " ".join(partes)


def _assert_sin_pii_en_spans(spans: list[ReadableSpan]) -> None:
    """Falla si algun span expone valores o claves prohibidas."""
    for span in spans:
        texto = _texto_de_span(span)
        for valor in _VALORES_PROHIBIDOS:
            assert valor not in texto
        claves = {str(clave).lower() for clave in (span.attributes or {})}
        assert not claves.intersection(_CLAVES_PROHIBIDAS)
        for evento in span.events:
            claves_evento = {str(clave).lower() for clave in (evento.attributes or {})}
            assert not claves_evento.intersection(_CLAVES_PROHIBIDAS)


class _ExportadorQueFalla(SpanExporter):
    """Exportador que siempre lanza para simular un colector caido."""

    def __init__(self) -> None:
        self.lotes: list[int] = []

    def export(self, spans: Any) -> Any:
        """Registra el lote y falla como lo haria un colector inalcanzable."""
        self.lotes.append(len(spans))
        raise RuntimeError("colector de pruebas inalcanzable")

    def shutdown(self) -> None:
        """No hay recursos que liberar."""


def _crear_app_de_prueba(proveedor: TracerProvider) -> FastAPI:
    """Crea una app ASGI instrumentada con rutas que no tocan la base de datos."""
    app = FastAPI(title="Pruebas de privacidad de telemetria")
    app.add_middleware(LoggingAccesoMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/v1/prueba")
    async def prueba(request: Request) -> dict[str, str]:
        if request.query_params.get("registrar") != "0":
            logging.getLogger("app").info(
                "evento correo=persona@example.com codificado=persona%%40example.com "
                "lat=4.53 lng=-75.68 token=Bearer abc.def ip=190.1.2.3 huella_red=%s",
                "a" * 64,
            )
        return {"estado": "ok"}

    @app.get("/v1/prueba/error")
    async def error() -> None:
        raise ValueError("orden=persona@example.com&lat=4.53&lng=-75.68")

    @app.get("/v1/prueba/estado")
    async def estado() -> dict[str, str]:
        span = otel_trace.get_current_span()
        span.set_status(StatusCode.ERROR, "fallo con persona@example.com lat=4.53")
        return {"estado": "ok"}

    @app.post("/v1/prueba/cuerpo")
    async def cuerpo(request: Request) -> dict[str, str]:
        contenido = await request.body()
        if b"persona@example.com" not in contenido:
            raise ValueError("El cuerpo esperado no llego completo.")
        return {"estado": "recibido"}

    FastAPIInstrumentor.instrument_app(app, tracer_provider=proveedor)
    return app


@pytest.fixture
def proveedores_globales_aislados() -> Iterator[None]:
    """Restaura los providers globales de OpenTelemetry despues de la prueba.

    `set_tracer_provider`, `set_meter_provider` y `set_logger_provider` solo
    aceptan una asignacion por proceso; la fixture reinicia el estado privado
    del SDK para que las pruebas puedan configurar su propio provider sin
    contaminar a las demas.
    """
    estado = {
        "trazas": (otel_trace._TRACER_PROVIDER, otel_trace._TRACER_PROVIDER_SET_ONCE._done),
        "metricas": (
            otel_metrics_internal._METER_PROVIDER,
            otel_metrics_internal._METER_PROVIDER_SET_ONCE._done,
        ),
        "logs": (
            otel_logs_internal._LOGGER_PROVIDER,
            otel_logs_internal._LOGGER_PROVIDER_SET_ONCE._done,
        ),
        "modulo": (
            telemetria._telemetria_activa,
            telemetria._tracer_provider,
            telemetria._meter_provider,
            telemetria._logger_provider,
        ),
    }
    otel_trace._TRACER_PROVIDER = None
    otel_trace._TRACER_PROVIDER_SET_ONCE = Once()
    otel_metrics_internal._METER_PROVIDER = None
    otel_metrics_internal._METER_PROVIDER_SET_ONCE = Once()
    otel_logs_internal._LOGGER_PROVIDER = None
    otel_logs_internal._LOGGER_PROVIDER_SET_ONCE = Once()
    telemetria._telemetria_activa = False
    telemetria._tracer_provider = None
    telemetria._meter_provider = None
    telemetria._logger_provider = None

    try:
        yield
    finally:
        telemetria.apagar_telemetria()
        otel_trace._TRACER_PROVIDER = estado["trazas"][0]
        otel_trace._TRACER_PROVIDER_SET_ONCE = Once()
        otel_trace._TRACER_PROVIDER_SET_ONCE._done = estado["trazas"][1]
        otel_metrics_internal._METER_PROVIDER = estado["metricas"][0]
        otel_metrics_internal._METER_PROVIDER_SET_ONCE = Once()
        otel_metrics_internal._METER_PROVIDER_SET_ONCE._done = estado["metricas"][1]
        otel_logs_internal._LOGGER_PROVIDER = estado["logs"][0]
        otel_logs_internal._LOGGER_PROVIDER_SET_ONCE = Once()
        otel_logs_internal._LOGGER_PROVIDER_SET_ONCE._done = estado["logs"][1]
        (
            telemetria._telemetria_activa,
            telemetria._tracer_provider,
            telemetria._meter_provider,
            telemetria._logger_provider,
        ) = estado["modulo"]


@pytest.fixture
def logging_cableado(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    """Aplica `configurar_logging` y restaura handlers, filtros y niveles."""
    logger_raiz = logging.getLogger()
    logger_app = logging.getLogger("app")
    logger_acceso = logging.getLogger("app.acceso")
    logger_uvicorn = logging.getLogger("uvicorn.access")
    loggers = (logger_raiz, logger_app, logger_acceso, logger_uvicorn)
    handlers = list(logger_raiz.handlers)
    estado_loggers = [
        (logger, logger.level, logger.disabled, list(logger.filters)) for logger in loggers
    ]
    estado_handlers = [
        (handler, handler.level, handler.formatter, list(handler.filters)) for handler in handlers
    ]
    tipos = (FiltroPrivacidadLey1581, FiltroCorrelacionTrazas)

    for logger in loggers:
        logger.filters[:] = [filtro for filtro in logger.filters if not isinstance(filtro, tipos)]
    for handler in handlers:
        handler.filters[:] = [filtro for filtro in handler.filters if not isinstance(filtro, tipos)]

    configurar_logging()
    handlers_nuevos = [handler for handler in logger_raiz.handlers if handler not in handlers]
    caplog.set_level(logging.INFO)
    try:
        yield
    finally:
        for handler in handlers_nuevos:
            logger_raiz.removeHandler(handler)
            handler.close()
        for logger, nivel, deshabilitado, filtros in estado_loggers:
            logger.setLevel(nivel)
            logger.disabled = deshabilitado
            logger.filters[:] = filtros
        for handler, nivel, formatter, filtros in estado_handlers:
            handler.setLevel(nivel)
            handler.setFormatter(formatter)
            handler.filters[:] = filtros


@pytest.fixture
def logging_limpio() -> Iterator[None]:
    """Deja la raiz sin handlers y restaura niveles, filtros y `disabled`.

    Los capturadores de pytest se retiran y la propia herramienta los descarta
    al cerrar la fase. A diferencia de `logging_cableado`, no configura nada:
    permite que el lifespan real instale el handler raiz y que `capsys` capture
    su salida.
    """
    logger_raiz = logging.getLogger()
    loggers = (
        logger_raiz,
        logging.getLogger("app"),
        logging.getLogger("app.acceso"),
        logging.getLogger("uvicorn.access"),
    )
    estado_loggers = [
        (logger, logger.level, logger.disabled, list(logger.filters)) for logger in loggers
    ]
    handlers_previos = list(logger_raiz.handlers)
    for handler in handlers_previos:
        logger_raiz.removeHandler(handler)

    try:
        yield
    finally:
        for handler in list(logger_raiz.handlers):
            logger_raiz.removeHandler(handler)
            if handler not in handlers_previos:
                handler.close()
        for logger, nivel, deshabilitado, filtros in estado_loggers:
            logger.setLevel(nivel)
            logger.disabled = deshabilitado
            logger.filters[:] = filtros


@pytest.fixture
def exportador_spans(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[InMemorySpanExporter]:
    """Sustituye los tracers de los servicios por uno con exportador en memoria."""
    exportador = InMemorySpanExporter()
    proveedor = _proveedor_de_telemetria(exportador)
    tracer = proveedor.get_tracer("pruebas.integracion.telemetria")
    monkeypatch.setattr(modulo_servicio, "tracer", tracer)
    monkeypatch.setattr(modulo_comparacion, "tracer", tracer)
    try:
        yield exportador
    finally:
        proveedor.shutdown()


class _CacheVacia:
    """Puerto de cache en memoria que nunca acierta."""

    async def obtener(self, producto_id: UUID | str, subllave: str) -> None:
        """Siempre falla el acierto de cache."""
        return None

    async def guardar(
        self,
        producto_id: UUID | str,
        subllave: str,
        datos: dict[str, Any],
        ttl_segundos: int = 60,
    ) -> None:
        """No persiste nada."""
        return None

    async def invalidar_producto(self, producto_id: UUID | str) -> None:
        """No invalida nada."""
        return None

    async def limpiar(self) -> None:
        """No limpia nada."""
        return None


class _InstrumentoFalso:
    """Contador o histograma que conserva los registros recibidos."""

    def __init__(self) -> None:
        self.registros: list[tuple[Any, dict[str, Any]]] = []

    def add(self, cantidad: int, atributos: dict[str, Any] | None = None) -> None:
        """Registra una suma con sus atributos."""
        self.registros.append((cantidad, dict(atributos or {})))

    def record(self, valor: float, atributos: dict[str, Any] | None = None) -> None:
        """Registra una medicion con sus atributos."""
        self.registros.append((valor, dict(atributos or {})))


def _fila_comparacion(presentacion_id: UUID, establecimiento_id: UUID) -> SimpleNamespace:
    """Construye una fila de precio vigente equivalente a la consulta SQL real."""
    return SimpleNamespace(
        presentacion_id=presentacion_id,
        establecimiento_id=establecimiento_id,
        precio_cop=3200,
        precio_por_base=Decimal("6.4"),
        sello="vigente",
        ultimo_reporte_en=datetime.now(UTC),
        est_nombre="Tienda de prueba",
        est_tipo="tienda",
        est_barrio="Centro",
        est_direccion="Calle 1 # 2-3",
        est_lat=4.5340,
        est_lng=-75.6811,
        pres_etiqueta="500 g",
        pres_marca="Marca",
        pres_cantidad_base=500.0,
        motivo_sello=None,
        n_reportes_validos=3,
        n_fuentes=3,
        con_foto=True,
    )


@pytest.mark.asyncio
async def test_comparacion_crea_span_sin_coordenadas_ni_pii(
    exportador_spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El servicio compara y expone solo atributos permitidos, sin lat/lng."""
    producto_id = uuid4()
    presentacion_id = uuid4()
    establecimiento_id = uuid4()
    fila = _fila_comparacion(presentacion_id, establecimiento_id)
    producto = SimpleNamespace(id=producto_id, nombre="Arroz", categoria_id=1, unidad_base="g")

    async def consultar_falsa(
        self: ServicioComparacion,
        sesion: Any,
        producto_consultado: UUID,
        presentacion: UUID | None,
    ) -> tuple[Any, list[Any], list[Any]]:
        return producto, [], [fila]

    monkeypatch.setattr(ServicioComparacion, "_consultar_bd", consultar_falsa)

    servicio = ServicioComparacion(puerto_cache=_CacheVacia(), sesion=object())  # type: ignore[arg-type]
    respuesta = await servicio.obtener_comparacion(
        producto_id=producto_id,
        orden="distancia",
        lat=4.5339,
        lng=-75.6811,
        radio_km=10.0,
    )

    assert len(respuesta.datos.resultados) == 1
    spans = exportador_spans.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "precios.obtener_comparacion"
    assert span.status.status_code == StatusCode.OK

    atributos = dict(span.attributes or {})
    assert atributos["precios.orden"] == "distancia"
    assert atributos["precios.presentacion"] is False
    assert atributos["precios.cache_hit"] is False
    assert atributos["precios.resultados_count"] == 1
    assert atributos["precios.radio_km"] == pytest.approx(10.0)
    assert float(atributos["precios.db_ms"]) >= 0.0

    claves_prohibidas = {
        "lat",
        "lng",
        "reportante_id",
        "huella_red",
        "alias",
        "foto_ruta",
        "foto_prueba_path",
        "client.address",
        "net.peer.ip",
        "http.request.header.authorization",
        "request.body",
        "response.body",
    }
    assert not claves_prohibidas.intersection(atributos)
    texto_atributos = str(atributos)
    assert "4.5339" not in texto_atributos
    assert "-75.6811" not in texto_atributos


@pytest.mark.asyncio
async def test_comparacion_cache_hit_marca_db_ms_cero(
    exportador_spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un acierto de cache no consulta la BD y lo refleja en los atributos."""
    contador = _InstrumentoFalso()
    histograma = _InstrumentoFalso()
    monkeypatch.setattr(modulo_comparacion, "_contador_comparaciones", contador)
    monkeypatch.setattr(modulo_comparacion, "_histograma_db_ms", histograma)
    producto_id = uuid4()
    respuesta_cache = {
        "datos": {
            "producto": {
                "id": str(producto_id),
                "nombre": "Arroz",
                "categoria_id": 1,
                "unidad_base": "g",
                "unidad_visualizacion": "kg",
                "presentaciones": [],
            },
            "resultados": [],
            "promociones": [],
            "meta": {
                "criterio_orden": "precio_unitario",
                "texto_neutralidad": "Ordenado por precio por kg.",
                "bloques": ["vigentes"],
                "generado_en": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "datos_de_demostracion": False,
            },
        }
    }

    class _CacheConAcierto(_CacheVacia):
        async def obtener(self, producto_id: UUID | str, subllave: str) -> dict[str, Any]:
            return respuesta_cache

    servicio = ServicioComparacion(puerto_cache=_CacheConAcierto(), sesion=object())  # type: ignore[arg-type]
    respuesta = await servicio.obtener_comparacion(producto_id=producto_id)

    assert respuesta.datos.resultados == []
    spans = exportador_spans.get_finished_spans()
    assert len(spans) == 1
    atributos = dict(spans[0].attributes or {})
    assert atributos["precios.cache_hit"] is True
    assert atributos["precios.db_ms"] == pytest.approx(0.0)
    assert atributos["precios.resultados_count"] == 0
    assert contador.registros == [(1, {"cache_hit": True})]
    assert histograma.registros == [(0.0, {"cache_hit": True})]


class _ConfianzaFalsa:
    """Evaluador de confianza que acepta siempre sin tocar la BD."""

    async def evaluar_reporte_entrante(self, **kwargs: Any) -> tuple[EvaluacionReporte, str]:
        return EvaluacionReporte(estado="aceptado"), "huella_interna"


def _instalar_dobles_registro(
    monkeypatch: pytest.MonkeyPatch,
    producto_id: UUID,
    establecimiento_id: UUID,
) -> None:
    """Reemplaza los colaboradores de BD del registro por dobles deterministas."""

    async def parametros(sesion: Any) -> ParametrosDominio:
        return ParametrosDominio()

    async def sin_limites(*args: Any, **kwargs: Any) -> None:
        return None

    def validar_sin_reglas(
        entrada: CrearReporteEntrada,
        params: ParametrosDominio,
        instante: datetime,
        idempotency_key: str | None,
    ) -> UUID:
        return uuid4()

    async def presentacion(sesion: Any, presentacion_id: UUID) -> dict[str, Any]:
        return {"producto_id": producto_id, "cantidad_base": Decimal("500")}

    async def establecimiento_activo(sesion: Any, establecimiento_id: UUID) -> bool:
        return True

    async def sin_reporte_previo(sesion: Any, usuario_id: UUID, key: UUID) -> None:
        return None

    async def insertar(sesion: Any, datos: dict[str, Any]) -> None:
        return None

    async def sin_efectos(self: ServicioPrecios, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(modulo_servicio, "obtener_parametros_dominio", parametros)
    monkeypatch.setattr(modulo_servicio, "validar_limites_usuario", sin_limites)
    monkeypatch.setattr(modulo_servicio, "validar_entrada_reporte", validar_sin_reglas)
    monkeypatch.setattr(repositorio, "obtener_presentacion_con_producto", presentacion)
    monkeypatch.setattr(repositorio, "verificar_establecimiento_activo", establecimiento_activo)
    monkeypatch.setattr(repositorio, "buscar_reporte_idempotente", sin_reporte_previo)
    monkeypatch.setattr(repositorio, "insertar_reporte_precio", insertar)
    monkeypatch.setattr(ServicioPrecios, "_aplicar_efectos_post_insercion", sin_efectos)


@pytest.mark.asyncio
async def test_registro_crea_span_con_atributos_permitidos_sin_pii(
    exportador_spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El registro instrumentado no filtra correo, IP, huella ni ruta de foto."""
    producto_id = uuid4()
    presentacion_id = uuid4()
    establecimiento_id = uuid4()
    usuario = UsuarioAutenticado(
        id=uuid4(),
        email="persona@example.com",
        rol="usuario",
        estado="activo",
    )
    entrada = CrearReporteEntrada(
        presentacion_id=presentacion_id,
        establecimiento_id=establecimiento_id,
        precio_cop=3200,
        observado_en=datetime.now(UTC),
        foto_ruta="fotos/prueba-privada.jpg",
    )
    _instalar_dobles_registro(monkeypatch, producto_id, establecimiento_id)
    contador = _InstrumentoFalso()
    monkeypatch.setattr(modulo_servicio, "_contador_reportes", contador)

    servicio = ServicioPrecios(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=_CacheVacia(),
        servicio_confianza=_ConfianzaFalsa(),  # type: ignore[arg-type]
    )
    respuesta, creado = await servicio.registrar_reporte(
        usuario=usuario,
        idempotency_key=str(uuid4()),
        entrada=entrada,
        ip_cliente="190.1.2.3",
    )

    assert creado is True
    assert respuesta.datos.estado_visible == "recibido"

    spans = exportador_spans.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "precios.registrar_reporte"
    assert span.status.status_code == StatusCode.OK

    atributos = dict(span.attributes or {})
    assert atributos["precios.presentacion_id"] == str(presentacion_id)
    assert atributos["precios.establecimiento_id"] == str(establecimiento_id)
    assert atributos["precios.estado"] == "aceptado"
    assert atributos["precios.idempotente"] is False
    assert atributos["precios.tiene_foto"] is True

    claves_prohibidas = {
        "lat",
        "lng",
        "reportante_id",
        "huella_red",
        "alias",
        "email",
        "ip",
        "foto_ruta",
        "foto_prueba_path",
        "client.address",
        "net.peer.ip",
        "http.request.header.authorization",
        "request.body",
        "response.body",
    }
    assert not claves_prohibidas.intersection(atributos)
    texto_atributos = str(atributos)
    assert "persona@example.com" not in texto_atributos
    assert "190.1.2.3" not in texto_atributos
    assert "huella_interna" not in texto_atributos
    assert "prueba-privada.jpg" not in texto_atributos
    assert contador.registros == [(1, {"estado": "aceptado", "idempotente": False})]


@pytest.mark.asyncio
async def test_registro_con_error_marca_span_error_y_relanza(
    exportador_spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una validacion fallida deja el span en ERROR y conserva la excepcion."""
    producto_id = uuid4()
    establecimiento_id = uuid4()
    _instalar_dobles_registro(monkeypatch, producto_id, establecimiento_id)

    def validar_con_error(
        entrada: CrearReporteEntrada,
        params: ParametrosDominio,
        instante: datetime,
        idempotency_key: str | None,
    ) -> UUID:
        raise ValidacionError("Regla de negocio incumplida para persona@example.com lat=4.53.")

    monkeypatch.setattr(modulo_servicio, "validar_entrada_reporte", validar_con_error)

    entrada = CrearReporteEntrada(
        presentacion_id=uuid4(),
        establecimiento_id=establecimiento_id,
        precio_cop=3200,
        observado_en=datetime.now(UTC),
    )
    servicio = ServicioPrecios(
        sesion=object(),  # type: ignore[arg-type]
        puerto_cache=_CacheVacia(),
        servicio_confianza=_ConfianzaFalsa(),  # type: ignore[arg-type]
    )

    with pytest.raises(ValidacionError):
        await servicio.registrar_reporte(
            usuario=UsuarioAutenticado(id=uuid4(), email=None, rol="usuario", estado="activo"),
            idempotency_key=str(uuid4()),
            entrada=entrada,
            ip_cliente="190.1.2.3",
        )

    spans = exportador_spans.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == StatusCode.ERROR
    evento = next(evento for evento in span.events if evento.name == "exception")
    atributos_evento = dict(evento.attributes or {})
    assert "persona@example.com" not in str(atributos_evento)
    assert "4.53" not in str(atributos_evento)
    assert "[REDACTADO_EMAIL]" in str(atributos_evento["exception.message"])
    assert "[REDACTADO_COORD]" in str(atributos_evento["exception.message"])
    assert "huella_red" not in str(span.attributes or {})
    _assert_sin_pii_en_spans([span])


class _InstrumentadorFalso:
    """Instrumentador de FastAPI que registra sus llamadas."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[FastAPI, str | None]] = []

    def instrument_app(self, app: FastAPI, excluded_urls: str | None = None) -> None:
        """Conserva la aplicacion y las URLs excluidas."""
        self.llamadas.append((app, excluded_urls))


def _preparar_lifespan(
    monkeypatch: pytest.MonkeyPatch,
    eventos: list[str],
) -> _InstrumentadorFalso:
    """Aisla el ciclo de vida de las dependencias externas."""

    async def cerrar_conexiones() -> None:
        eventos.append("cerrar")

    instrumentador = _InstrumentadorFalso()
    monkeypatch.setattr(modulo_main, "FastAPIInstrumentor", instrumentador)
    monkeypatch.setattr(modulo_main, "configurar_logging", lambda: eventos.append("logging"))
    monkeypatch.setattr(
        modulo_main, "configurar_telemetria", lambda configuracion: eventos.append("telemetria")
    )
    monkeypatch.setattr(modulo_main, "obtener_configuracion", lambda: object())
    monkeypatch.setattr(modulo_main, "apagar_telemetria", lambda: eventos.append("apagar"))
    monkeypatch.setattr(modulo_main, "cerrar_conexiones", cerrar_conexiones)
    return instrumentador


@pytest.mark.asyncio
async def test_lifespan_configura_y_apaga_sin_instrumentar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El lifespan configura telemetria y apaga, pero ya no instrumenta FastAPI."""
    eventos: list[str] = []
    instrumentador = _preparar_lifespan(monkeypatch, eventos)
    aplicacion = FastAPI()

    async with modulo_main.lifespan(aplicacion):
        eventos.append("dentro")

    assert eventos == ["logging", "telemetria", "dentro", "apagar", "cerrar"]
    assert instrumentador.llamadas == []


def test_create_app_instrumenta_antes_de_construir_la_pila(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La instrumentacion se registra en create_app, antes del primer request."""
    instrumentador = _InstrumentadorFalso()
    monkeypatch.setattr(modulo_main, "FastAPIInstrumentor", instrumentador)

    aplicacion = modulo_main.create_app()

    assert aplicacion.middleware_stack is None
    assert instrumentador.llamadas == [(aplicacion, "/v1/salud,/v1/salud/listo")]


def test_http_real_genera_span_y_excluye_salud(
    monkeypatch: pytest.MonkeyPatch,
    proveedores_globales_aislados: None,
) -> None:
    """Con un provider real, una ruta normal se traza y la salud no genera spans."""
    exportador = InMemorySpanExporter()
    proveedor = _proveedor_de_telemetria(exportador)
    otel_trace.set_tracer_provider(proveedor)

    configuracion = _configuracion(
        ENTORNO="pruebas",
        OTEL_SDK_DISABLED=False,
        OTEL_EXPORTER_OTLP_ENDPOINT="",
        DATABASE_URL="",
        REDIS_URL="",
    )
    monkeypatch.setattr(modulo_main, "obtener_configuracion", lambda: configuracion)
    monkeypatch.setattr(modulo_main, "configurar_logging", lambda: None)

    async def cerrar_sin_bd() -> None:
        return None

    async def bd_conectada() -> bool:
        return True

    async def redis_desactivado() -> str:
        return "desactivado"

    monkeypatch.setattr(modulo_main, "cerrar_conexiones", cerrar_sin_bd)
    monkeypatch.setattr(modulo_main, "verificar_conexion_bd", bd_conectada)
    monkeypatch.setattr(modulo_main, "_verificar_redis", redis_desactivado)
    aplicacion = modulo_main.create_app()

    try:
        with TestClient(aplicacion) as cliente:
            respuesta = cliente.get(
                "/openapi.json?correo=persona@example.com"
                "&correo_cod=persona%40example.com"
                "&lat=4.53&lng=-75.68&coord_cod=lat%3D4.53",
                headers={
                    "authorization": "Bearer token-secreto",
                    "cookie": "sesion=abc; huella_red=" + "b" * 64,
                },
            )
            assert respuesta.status_code == 200
            respuesta_cuerpo = cliente.post(
                "/openapi.json",
                content=('{"correo":"persona@example.com","lat":4.53,"lng":-75.68}'),
                headers={
                    "authorization": "Bearer token-secreto",
                    "cookie": "sesion=abc",
                },
            )
            assert respuesta_cuerpo.status_code == 405
            assert cliente.get("/v1/salud").status_code == 200
            assert cliente.get("/v1/salud/listo").status_code == 200

        spans = list(exportador.get_finished_spans())
    finally:
        proveedor.shutdown()

    assert any("openapi" in span.name.lower() for span in spans)
    span_openapi = next(
        span
        for span in spans
        if span.kind == SpanKind.SERVER
        and span.attributes is not None
        and span.attributes.get("http.method") == "GET"
        and "openapi" in span.name.lower()
    )
    assert span_openapi.kind == SpanKind.SERVER
    assert not any(span.name.startswith("fastapi.") for span in spans)
    assert not any("/v1/salud" in span.name for span in spans)
    atributos_openapi = dict(span_openapi.attributes or {})
    texto_openapi = str(atributos_openapi)
    assert "[REDACTADO_EMAIL]" in str(atributos_openapi.get("http.url", ""))
    assert "[REDACTADO_COORD]" in str(atributos_openapi.get("http.url", ""))
    assert "persona%40example.com" not in texto_openapi
    assert "net.peer.ip" not in atributos_openapi
    for valor in ("lat=4.53", "lng=-75.68", "lat%3D4.53", "lng%3D-75.68"):
        assert valor not in texto_openapi
    _assert_sin_pii_en_spans(spans)
    for span in spans:
        atributos = dict(span.attributes or {})
        assert atributos.get("http.route") not in ("/v1/salud", "/v1/salud/listo")
        assert "/v1/salud" not in str(atributos.get("http.target", ""))
        assert "/v1/salud" not in str(atributos.get("url.path", ""))
        claves = {str(clave).lower() for clave in atributos}
        assert "request.body" not in claves
        assert "response.body" not in claves


def test_http_redacta_excepcion_y_estado_con_pii() -> None:
    """Los eventos de excepcion y la descripcion del estado no exponen PII."""
    exportador = InMemorySpanExporter()
    proveedor = _proveedor_de_telemetria(exportador)
    app = _crear_app_de_prueba(proveedor)

    try:
        with TestClient(app, raise_server_exceptions=False) as cliente:
            respuesta = cliente.get(
                "/v1/prueba/error?correo=persona@example.com&lat=4.53&lng=-75.68"
            )
            assert respuesta.status_code == 500
            assert cliente.get("/v1/prueba/estado").status_code == 200

        spans = list(exportador.get_finished_spans())
    finally:
        proveedor.shutdown()

    span_error = next(
        span for span in spans if span.kind == SpanKind.SERVER and "error" in span.name
    )
    assert span_error.status.status_code == StatusCode.ERROR
    descripcion_error = span_error.status.description or ""
    assert "persona@example.com" not in descripcion_error
    assert "4.53" not in descripcion_error
    eventos_error = [evento for evento in span_error.events if evento.name == "exception"]
    assert eventos_error
    for evento in eventos_error:
        atributos_evento = dict(evento.attributes or {})
        assert "persona@example.com" not in str(atributos_evento.get("exception.message", ""))
        assert "4.53" not in str(atributos_evento.get("exception.message", ""))
        assert "persona@example.com" not in str(atributos_evento.get("exception.stacktrace", ""))
        assert "4.53" not in str(atributos_evento.get("exception.stacktrace", ""))

    span_estado = next(
        span for span in spans if span.kind == SpanKind.SERVER and "estado" in span.name
    )
    assert span_estado.status.status_code == StatusCode.ERROR
    assert span_estado.status.description == ("fallo con [REDACTADO_EMAIL] lat=[REDACTADO_COORD]")
    _assert_sin_pii_en_spans(spans)


def test_http_no_exporta_cuerpos_cabeceras_ni_alias_de_ip() -> None:
    """El cuerpo, las cabeceras y los alias de IP nunca llegan a los spans."""
    exportador = InMemorySpanExporter()
    proveedor = _proveedor_de_telemetria(exportador)
    app = _crear_app_de_prueba(proveedor)
    cuerpo = '{"correo":"persona@example.com","lat":4.53,"lng":-75.68}'

    try:
        with TestClient(app) as cliente:
            respuesta = cliente.post(
                "/v1/prueba/cuerpo?correo=persona@example.com&lat=4.53&lng=-75.68",
                content=cuerpo,
                headers={
                    "authorization": "Bearer token-secreto",
                    "cookie": "sesion=abc; huella_red=" + "b" * 64,
                    "x-forwarded-for": "190.1.2.3",
                    "x-real-ip": "190.1.2.3",
                },
            )
        assert respuesta.status_code == 200
        spans = list(exportador.get_finished_spans())
    finally:
        proveedor.shutdown()

    _assert_sin_pii_en_spans(spans)
    for span in spans:
        texto = _texto_de_span(span)
        assert cuerpo not in texto
        assert "190.1.2.3" not in texto
        assert "b" * 64 not in texto
        claves = {str(clave).lower() for clave in (span.attributes or {})}
        assert not claves.intersection(_CLAVES_PROHIBIDAS)


def test_logs_cableados_por_configurar_logging_no_filtran_pii(
    logging_cableado: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """El logging configurado por la app redacta, correlaciona y respeta PII."""
    logger_raiz = logging.getLogger()
    for logger in (logger_raiz, logging.getLogger("app"), logging.getLogger("app.acceso")):
        tipos = {type(filtro) for filtro in logger.filters}
        assert FiltroPrivacidadLey1581 in tipos
        assert FiltroCorrelacionTrazas in tipos
    for handler in logger_raiz.handlers:
        tipos = {type(filtro) for filtro in handler.filters}
        assert FiltroPrivacidadLey1581 in tipos
        assert FiltroCorrelacionTrazas in tipos

    exportador = InMemorySpanExporter()
    proveedor = _proveedor_de_telemetria(exportador)
    app = _crear_app_de_prueba(proveedor)
    cabeceras = {
        "authorization": "Bearer token-secreto",
        "cookie": "sesion=abc; huella_red=" + "b" * 64,
    }
    cuerpo = '{"correo":"persona@example.com","lat":4.53,"lng":-75.68}'

    try:
        with TestClient(app) as cliente:
            respuesta = cliente.get(
                "/v1/prueba?correo=persona@example.com"
                "&correo_cod=persona%40example.com"
                "&lat=4.53&lng=-75.68",
                headers=cabeceras,
            )
            respuesta_cuerpo = cliente.post(
                "/v1/prueba/cuerpo?correo=persona@example.com&lat=4.53",
                content=cuerpo,
                headers=cabeceras,
            )
        assert respuesta.status_code == 200
        assert respuesta_cuerpo.status_code == 200
    finally:
        proveedor.shutdown()

    registros = [registro for registro in caplog.records if registro.name in ("app", "app.acceso")]
    assert any(registro.name == "app" for registro in registros)
    assert any(registro.name == "app.acceso" for registro in registros)
    texto = "\n".join(registro.getMessage() for registro in registros)
    for valor in _VALORES_PROHIBIDOS:
        assert valor not in texto
    assert cuerpo not in texto
    assert "abc.def" not in texto
    assert "190.1.2.3" not in texto
    assert "a" * 64 not in texto
    assert "b" * 64 not in texto
    assert "huella_red" not in texto
    assert "[REDACTADO_EMAIL]" in texto
    assert "[REDACTADO_COORD]" in texto
    assert "[REDACTADO_TOKEN]" in texto
    assert "[REDACTADO_IP]" in texto
    assert "[REDACTADO_HUELLA]" in texto
    for registro in registros:
        assert re.fullmatch(r"[0-9a-f]{32}", registro.__dict__["trace_id"])
        assert re.fullmatch(r"[0-9a-f]{16}", registro.__dict__["span_id"])


def test_lifespan_emite_logs_de_acceso_saneados_a_la_salida_estandar(
    monkeypatch: pytest.MonkeyPatch,
    proveedores_globales_aislados: None,
    logging_limpio: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """El handler raiz del lifespan emite `app.acceso` con traza y sin PII."""
    exportador = InMemorySpanExporter()
    proveedor = _proveedor_de_telemetria(exportador)
    otel_trace.set_tracer_provider(proveedor)
    configuracion = _configuracion(
        OTEL_SDK_DISABLED=False,
        OTEL_EXPORTER_OTLP_ENDPOINT="",
        DATABASE_URL="",
        REDIS_URL="",
    )
    monkeypatch.setattr(modulo_main, "obtener_configuracion", lambda: configuracion)
    # pytest instala sus capturadores despues de las fixtures; se retiran para
    # que el lifespan encuentre la raiz vacia e instale su propio handler.
    logger_raiz = logging.getLogger()
    for handler in list(logger_raiz.handlers):
        logger_raiz.removeHandler(handler)
    aplicacion = modulo_main.create_app()

    try:
        with TestClient(aplicacion) as cliente:
            respuesta = cliente.get("/openapi.json?lat=4.53&lng=-75.68&correo=persona@example.com")
            assert respuesta.status_code == 200
        salida = capsys.readouterr()
    finally:
        proveedor.shutdown()

    texto = salida.err + salida.out
    assert re.search(
        r"INFO app\.acceso \[trace_id=[0-9a-f]{32} span_id=[0-9a-f]{16}\] "
        r"GET http://testserver/openapi\.json\?lat=\[REDACTADO_COORD\]"
        r"&lng=\[REDACTADO_COORD\]&correo=\[REDACTADO_EMAIL\]",
        texto,
    )
    assert "uvicorn.access" not in texto
    for valor in ("lat=4.53", "lng=-75.68", "persona@example.com"):
        assert valor not in texto


def test_exportador_que_falla_no_afecta_la_respuesta(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Un exportador que lanza solo deja un registro; la API responde 200."""
    exportador = _ExportadorQueFalla()
    proveedor = _proveedor_de_telemetria(exportador)
    app = _crear_app_de_prueba(proveedor)

    try:
        with caplog.at_level(logging.WARNING):
            with TestClient(app) as cliente:
                respuesta = cliente.get("/v1/prueba?registrar=0")
        assert respuesta.status_code == 200
    finally:
        proveedor.shutdown()

    assert exportador.lotes
    assert "Exception while exporting Span" in caplog.text
    assert "persona@example.com" not in caplog.text


def test_colector_inalcanzable_no_afecta_la_api(
    monkeypatch: pytest.MonkeyPatch,
    proveedores_globales_aislados: None,
) -> None:
    """Un OTLP cerrado no impide responder ni hace fallar el apagado."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "1")
    configuracion = _configuracion(
        OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:9",
        OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic super-secreto",
        OTEL_METRICS_EXPORTER="none",
        OTEL_LOGS_EXPORTER="none",
        OTEL_TRACES_SAMPLER_ARG=1.0,
    )
    telemetria.configurar_telemetria(configuracion)
    proveedor = telemetria._tracer_provider
    assert telemetria.telemetria_activa() is True
    assert proveedor is not None

    app = FastAPI(title="Pruebas de colector inalcanzable")

    @app.get("/v1/salud")
    async def salud() -> dict[str, str]:
        return {"estado": "ok"}

    FastAPIInstrumentor.instrument_app(app, tracer_provider=proveedor)

    with TestClient(app) as cliente:
        assert cliente.get("/v1/salud").status_code == 200
        assert cliente.get("/openapi.json").status_code == 200
    telemetria.apagar_telemetria()
    telemetria.apagar_telemetria()

    assert telemetria.telemetria_activa() is False
    assert telemetria._tracer_provider is None


def test_otel_sdk_disabled_responde_sin_crear_exportadores(
    monkeypatch: pytest.MonkeyPatch,
    proveedores_globales_aislados: None,
) -> None:
    """Con OTEL_SDK_DISABLED=true la API responde y no se crean exportadores."""
    creados: list[str] = []

    def exportador_prohibido(*args: Any, **kwargs: Any) -> None:
        creados.append("exportador")
        raise RuntimeError("no deberia construirse con OTEL_SDK_DISABLED")

    monkeypatch.setattr(telemetria, "OTLPSpanExporter", exportador_prohibido)
    monkeypatch.setattr(telemetria, "OTLPMetricExporter", exportador_prohibido)
    monkeypatch.setattr(telemetria, "OTLPLogExporter", exportador_prohibido)
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    configuracion = _configuracion(
        OTEL_SDK_DISABLED=True,
        OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:9",
        OTEL_METRICS_EXPORTER="otlp",
        OTEL_LOGS_EXPORTER="otlp",
    )
    monkeypatch.setattr(modulo_main, "obtener_configuracion", lambda: configuracion)
    monkeypatch.setattr(modulo_main, "configurar_logging", lambda: None)

    async def cerrar_sin_bd() -> None:
        return None

    monkeypatch.setattr(modulo_main, "cerrar_conexiones", cerrar_sin_bd)
    aplicacion = modulo_main.create_app()

    with TestClient(aplicacion) as cliente:
        assert cliente.get("/v1/salud").status_code == 200
        assert cliente.get("/openapi.json").status_code == 200
        assert telemetria.telemetria_activa() is False

    assert creados == []
    assert telemetria.telemetria_activa() is False


def test_sanitizacion_fallida_descarta_span_y_api_responde(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Si la sanitizacion lanza, el span se descarta y la peticion continua."""

    def sanitizar_con_error(span: ReadableSpan) -> None:
        raise RuntimeError("fallo de sanitizacion")

    exportador = InMemorySpanExporter()
    proveedor = _proveedor_de_telemetria(exportador)
    app = _crear_app_de_prueba(proveedor)
    monkeypatch.setattr(telemetria, "_sanitizar_span", sanitizar_con_error)

    try:
        with caplog.at_level(logging.WARNING, logger="app.telemetria"):
            with TestClient(app) as cliente:
                respuesta = cliente.get(
                    "/v1/prueba?registrar=0&correo=persona@example.com&lat=4.53"
                )
            assert respuesta.status_code == 200
        assert exportador.get_finished_spans() == ()
    finally:
        proveedor.shutdown()

    assert "Se descarta un span por fallo en la sanitizacion" in caplog.text
    assert "persona@example.com" not in caplog.text
