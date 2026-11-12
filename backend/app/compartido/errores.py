"""Jerarquia de excepciones y manejadores de error bajo RFC 9457."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

TITULO_VALIDACION_FALLIDA = "Validacion Fallida"


class DetalleProblema(BaseModel):
    """Estructura de error estandar segun RFC 9457 (application/problem+json)."""

    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    instance: str
    codigo: str
    request_id: str | None = None


class AppError(Exception):
    """Excepcion base de la aplicacion con metadatos RFC 9457."""

    def __init__(
        self,
        codigo: str,
        status: int,
        titulo: str,
        detalle: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detalle)
        self.codigo = codigo
        self.status = status
        self.titulo = titulo
        self.detalle = detalle
        self.headers = headers or {}


class ValidacionError(AppError):
    def __init__(self, detalle: str) -> None:
        super().__init__("VALIDACION", 422, TITULO_VALIDACION_FALLIDA, detalle)


class PrecioFueraDeRangoError(AppError):
    def __init__(self, detalle: str) -> None:
        super().__init__("PRECIO_FUERA_DE_RANGO", 422, "Precio Fuera De Rango", detalle)


class FechaInvalidaError(AppError):
    def __init__(self, detalle: str) -> None:
        super().__init__("FECHA_INVALIDA", 422, "Fecha Invalida", detalle)


class UnidadesIncompatiblesError(AppError):
    def __init__(self, detalle: str) -> None:
        super().__init__("UNIDADES_INCOMPATIBLES", 422, "Unidades Incompatibles", detalle)


class ArchivoInvalidoError(AppError):
    def __init__(self, detalle: str) -> None:
        super().__init__("ARCHIVO_INVALIDO", 422, "Archivo Invalido", detalle)


class NoAutenticadoError(AppError):
    def __init__(
        self, detalle: str = "Credenciales de autenticacion ausentes o invalidas."
    ) -> None:
        super().__init__(
            "NO_AUTENTICADO", 401, "No Autenticado", detalle, {"WWW-Authenticate": "Bearer"}
        )


class ProhibidoError(AppError):
    def __init__(self, detalle: str = "No posee permisos suficientes para esta operacion.") -> None:
        super().__init__("PROHIBIDO", 403, "Acceso Prohibido", detalle)


class AutorizacionRequeridaError(AppError):
    def __init__(
        self, detalle: str = "Se requiere autorizacion previa de tratamiento de datos (Ley 1581)."
    ) -> None:
        super().__init__("AUTORIZACION_REQUERIDA", 403, "Autorizacion Requerida", detalle)


class CuentaSuspendidaError(AppError):
    def __init__(self, detalle: str = "La cuenta se encuentra suspendida o bloqueada.") -> None:
        super().__init__("CUENTA_SUSPENDIDA", 403, "Cuenta Suspendida", detalle)


class NoEncontradoError(AppError):
    def __init__(self, detalle: str = "El recurso solicitado no fue encontrado.") -> None:
        super().__init__("NO_ENCONTRADO", 404, "Recurso No Encontrado", detalle)


class ConflictoError(AppError):
    def __init__(self, detalle: str) -> None:
        super().__init__("CONFLICTO", 409, "Conflicto De Recursos", detalle)


class LimiteExcedidoError(AppError):
    def __init__(self, detalle: str, retry_after: int = 60) -> None:
        headers = {"Retry-After": str(retry_after)}
        super().__init__(
            "LIMITE_EXCEDIDO", 429, "Limite De Peticiones Excedido", detalle, headers=headers
        )


class ServicioNoDisponibleError(AppError):
    def __init__(self, detalle: str = "Servicio temporalmente no disponible.") -> None:
        super().__init__("SERVICIO_NO_DISPONIBLE", 503, "Servicio No Disponible", detalle)


def _crear_respuesta_problema(
    request: Request,
    codigo: str,
    status: int,
    titulo: str,
    detalle: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id: str | None = getattr(request.state, "request_id", None)
    slug = codigo.lower().replace("_", "-")
    tipo_url = f"https://comparador.armenia.gov.co/errores/{slug}"

    problema = DetalleProblema(
        type=tipo_url,
        title=titulo,
        status=status,
        detail=detalle,
        instance=request.url.path,
        codigo=codigo,
        request_id=request_id,
    )
    todas_cabeceras = {"Content-Type": "application/problem+json"}
    if headers:
        todas_cabeceras.update(headers)
    if request_id:
        todas_cabeceras["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status,
        content=problema.model_dump(),
        headers=todas_cabeceras,
    )


def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _crear_respuesta_problema(
        request, exc.codigo, exc.status, exc.titulo, exc.detalle, exc.headers
    )


def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = exc.errors()
    detalle = "; ".join(f"{' -> '.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errores)
    return _crear_respuesta_problema(request, "VALIDACION", 422, TITULO_VALIDACION_FALLIDA, detalle)


def http_exception_handler(
    request: Request, exc: HTTPException | StarletteHTTPException
) -> JSONResponse:
    mapa_codigos: dict[int, tuple[str, str]] = {
        401: ("NO_AUTENTICADO", "No Autenticado"),
        403: ("PROHIBIDO", "Acceso Prohibido"),
        404: ("NO_ENCONTRADO", "Recurso No Encontrado"),
        409: ("CONFLICTO", "Conflicto De Recursos"),
        422: ("VALIDACION", TITULO_VALIDACION_FALLIDA),
        429: ("LIMITE_EXCEDIDO", "Limite De Peticiones Excedido"),
        503: ("SERVICIO_NO_DISPONIBLE", "Servicio No Disponible"),
    }
    codigo, titulo = mapa_codigos.get(exc.status_code, ("ERROR_HTTP", "Error HTTP"))
    return _crear_respuesta_problema(
        request, codigo, exc.status_code, titulo, str(exc.detail), exc.headers
    )


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _crear_respuesta_problema(
        request,
        "SERVICIO_NO_DISPONIBLE",
        503,
        "Error Interno Del Servidor",
        "Ocurrio un error inesperado al procesar la solicitud.",
    )


def registrar_manejadores_errores(app: FastAPI) -> None:
    """Registra todos los manejadores RFC 9457 en la aplicacion FastAPI."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
