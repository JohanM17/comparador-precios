"""Pruebas unitarias para la validacion y limpieza de metadatos EXIF con Pillow (Tarea T-27)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.adaptadores.storage_supabase import limpiar_metadatos_exif
from app.compartido.errores import ArchivoInvalidoError


def _generar_jpeg_con_exif_gps() -> bytes:
    """Genera en memoria un archivo JPEG con coordenadas GPS incrustadas en EXIF."""
    imagen = Image.new("RGB", (50, 50), color="red")
    exif = imagen.getexif()
    # GPS IFD (0x8825 = 34853)
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (4.0, 32.0, 0.0)
    gps[3] = "W"
    gps[4] = (75.0, 41.0, 0.0)
    # Etiqueta EXIF 305 = Software
    exif[305] = "Camara Smartphone Armenia"

    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_limpieza_exif_elimina_gps_y_metadatos() -> None:
    """Verifica que una imagen con EXIF/GPS quede con 0 metadatos tras el procesado."""
    jpeg_con_gps = _generar_jpeg_con_exif_gps()

    # Comprobar que la imagen original si tiene metadatos EXIF
    img_original = Image.open(io.BytesIO(jpeg_con_gps))
    exif_original = img_original.getexif()
    assert len(exif_original) > 0

    # Procesar con la funcion de limpieza
    jpeg_limpio = limpiar_metadatos_exif(jpeg_con_gps, tipo_mime="image/jpeg", max_kb=300)

    # Comprobar que la imagen resultante no contiene ninguna etiqueta EXIF
    img_procesada = Image.open(io.BytesIO(jpeg_limpio))
    exif_procesado = img_procesada.getexif()
    assert len(exif_procesado) == 0


def test_limpieza_exif_soporta_webp() -> None:
    """Verifica que las imagenes WebP sean procesadas y re-codificadas sin metadatos."""
    imagen = Image.new("RGB", (60, 60), color="green")
    buffer = io.BytesIO()
    imagen.save(buffer, format="WEBP")
    webp_bytes = buffer.getvalue()

    webp_limpio = limpiar_metadatos_exif(webp_bytes, tipo_mime="image/webp", max_kb=300)
    assert len(webp_limpio) > 0
    img_limpia = Image.open(io.BytesIO(webp_limpio))
    assert img_limpia.format == "WEBP"


def test_rechazo_archivo_supera_tamano_maximo() -> None:
    """Verifica que un archivo superior a 300 KB lance ArchivoInvalidoError (422)."""
    archivo_pesado = b"X" * (301 * 1024)  # 301 KB
    with pytest.raises(ArchivoInvalidoError, match="supera el tamaño máximo"):
        limpiar_metadatos_exif(archivo_pesado, tipo_mime="image/jpeg", max_kb=300)


def test_rechazo_tipo_mime_no_permitido() -> None:
    """Verifica que tipos MIME distintos a JPEG y WebP sean rechazados con 422."""
    contenido = b"%PDF-1.4 simulado..."
    with pytest.raises(ArchivoInvalidoError, match="Tipo de archivo no permitido"):
        limpiar_metadatos_exif(contenido, tipo_mime="application/pdf", max_kb=300)
