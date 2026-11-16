"""Endpoints de la API REST para la obtencion de URLs firmadas de fotos."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.compartido.limites import LimitadorVentanaDeslizante
from app.compartido.seguridad import UsuarioAutenticado, requiere_autorizacion_datos
from app.modulos.fotos.esquemas import RespuestaUrlSubida, SolicitudUrlSubida
from app.puertos.almacenamiento import PuertoAlmacenamientoFotos

router = APIRouter(tags=["Fotos y Evidencias"])

# Limitador de tasa: maximo 30 solicitudes de subida por hora por usuario
limitador_fotos = LimitadorVentanaDeslizante()


def obtener_puerto_almacenamiento() -> PuertoAlmacenamientoFotos:
    """Proveedor inyectable del puerto de almacenamiento (inyectado en main.py)."""
    raise NotImplementedError("El puerto de almacenamiento debe ser inyectado por FastAPI.")


@router.post(
    "/fotos/url-subida",
    status_code=201,
    response_model=RespuestaUrlSubida,
    summary="Generar URL firmada para subir fotografia de prueba",
)
async def generar_url_subida_foto(
    entrada: SolicitudUrlSubida,
    usuario: Annotated[UsuarioAutenticado, Depends(requiere_autorizacion_datos)],
    almacenamiento: Annotated[PuertoAlmacenamientoFotos, Depends(obtener_puerto_almacenamiento)],
) -> RespuestaUrlSubida:
    """Genera una URL firmada de subida temporal a Storage Supabase bucket pruebas (T-27)."""
    limitador_fotos.exigir_limite(
        clave=str(usuario.id),
        max_solicitudes=30,
        ventana_segundos=3600,
        detalle="Ha superado el limite de 30 fotografias por hora.",
    )

    resultado = await almacenamiento.generar_url_subida(
        usuario_id=usuario.id,
        nombre_archivo=entrada.nombre_archivo,
        tipo_mime=entrada.tipo_mime,
        tamano_bytes=entrada.tamano_bytes,
    )

    return RespuestaUrlSubida(
        ruta=resultado.ruta,
        url_firmada=resultado.url_firmada,
        expira_en=resultado.expira_en_segundos,
    )
