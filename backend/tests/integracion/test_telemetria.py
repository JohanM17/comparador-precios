"""Pruebas de integracion de telemetria sin colector OTLP ni escritura en BD (T-120)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from app import main as modulo_main
from app.compartido import telemetria
from app.compartido.errores import ValidacionError
from app.compartido.seguridad import UsuarioAutenticado
from app.dominio.parametros import ParametrosDominio
from app.dominio.riesgo import EvaluacionReporte
from app.modulos.precios import repositorio
from app.modulos.precios import servicio as modulo_servicio
from app.modulos.precios import servicio_comparacion as modulo_comparacion
from app.modulos.precios.esquemas import CrearReporteEntrada
from app.modulos.precios.servicio import ServicioPrecios
from app.modulos.precios.servicio_comparacion import ServicioComparacion


@pytest.fixture
def exportador_spans(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[InMemorySpanExporter]:
    """Sustituye los tracers de los servicios por uno con exportador en memoria."""
    exportador = InMemorySpanExporter()
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    proveedor.add_span_processor(SimpleSpanProcessor(exportador))
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

    assert "lat" not in atributos
    assert "lng" not in atributos
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
        raise ValidacionError("Regla de negocio incumplida.")

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
    assert any(evento.name == "exception" for evento in span.events)


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


def test_http_real_genera_span_y_excluye_salud() -> None:
    """Con un provider real, una ruta normal se traza y la salud no genera spans."""
    exportador = InMemorySpanExporter()
    proveedor = TracerProvider(sampler=telemetria.ALWAYS_ON)
    proveedor.add_span_processor(
        telemetria.ProcesadorErroresPrimero(
            SimpleSpanProcessor(exportador),
            ratio_exitos=1.0,
        )
    )
    otel_trace.set_tracer_provider(proveedor)

    try:
        with TestClient(modulo_main.app) as cliente:
            respuesta = cliente.get("/openapi.json?orden=persona%40example.com&lat%3D4.53")
            assert respuesta.status_code == 200
            assert cliente.get("/v1/salud").status_code == 200
            assert cliente.get("/v1/salud/listo").status_code in (200, 503)

        spans = list(exportador.get_finished_spans())
    finally:
        proveedor.shutdown()

    assert any("openapi" in span.name.lower() for span in spans)
    span_openapi = next(
        span for span in spans if span.kind == SpanKind.SERVER and "openapi" in span.name.lower()
    )
    assert span_openapi.kind == SpanKind.SERVER
    assert not any(span.name.startswith("fastapi.") for span in spans)
    assert not any("/v1/salud" in span.name for span in spans)
    atributos_openapi = dict(span_openapi.attributes or {})
    assert "[REDACTADO_EMAIL]" in str(atributos_openapi.get("http.url", ""))
    assert "[REDACTADO_COORD]" in str(atributos_openapi.get("http.url", ""))
    assert "persona%40example.com" not in str(atributos_openapi)
    assert "net.peer.ip" not in atributos_openapi
    assert "4.53" not in str(atributos_openapi)
    for span in spans:
        atributos = dict(span.attributes or {})
        assert atributos.get("http.route") not in ("/v1/salud", "/v1/salud/listo")
        assert "/v1/salud" not in str(atributos.get("http.target", ""))
        assert "/v1/salud" not in str(atributos.get("url.path", ""))
