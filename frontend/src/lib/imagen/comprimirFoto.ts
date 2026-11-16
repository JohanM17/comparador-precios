export interface OpcionesCompresionFoto {
  readonly maxDimension?: number;
  readonly maxBytes?: number;
}

export interface ResultadoCompresionFoto {
  readonly blob: Blob;
  readonly ancho: number;
  readonly alto: number;
  readonly tamanoBytes: number;
}

const DIMENSION_MAXIMA_DEFECTO = 1280;
const PESO_MAXIMO_DEFECTO = 300 * 1024;
const CALIDADES_WEBP: readonly number[] = [0.84, 0.72, 0.6, 0.48, 0.36, 0.26];

interface ImagenDecodificada {
  readonly anchoOriginal: number;
  readonly altoOriginal: number;
  readonly dibujar: (ctx: CanvasRenderingContext2D, ancho: number, alto: number) => void;
  readonly liberar: () => void;
}

async function decodificarImagen(archivo: File): Promise<ImagenDecodificada> {
  if (typeof createImageBitmap === "function") {
    const bitmap = await createImageBitmap(archivo);
    return {
      anchoOriginal: bitmap.width,
      altoOriginal: bitmap.height,
      dibujar: (ctx, ancho, alto) => ctx.drawImage(bitmap, 0, 0, ancho, alto),
      liberar: () => bitmap.close(),
    };
  }

  const url = URL.createObjectURL(archivo);
  try {
    const img = await new Promise<HTMLImageElement>((resolver, rechazar) => {
      const el = new Image();
      el.onload = () => resolver(el);
      el.onerror = () => rechazar(new Error("No se pudo leer la imagen seleccionada."));
      el.src = url;
    });
    return {
      anchoOriginal: img.naturalWidth,
      altoOriginal: img.naturalHeight,
      dibujar: (ctx, ancho, alto) => ctx.drawImage(img, 0, 0, ancho, alto),
      liberar: () => URL.revokeObjectURL(url),
    };
  } catch (err) {
    URL.revokeObjectURL(url);
    throw err;
  }
}

function calcularDimensiones(
  anchoOriginal: number,
  altoOriginal: number,
  maxDimension: number
): { readonly ancho: number; readonly alto: number } {
  const mayor = Math.max(anchoOriginal, altoOriginal);
  if (mayor <= maxDimension) {
    return { ancho: Math.max(1, anchoOriginal), alto: Math.max(1, altoOriginal) };
  }
  const factor = maxDimension / mayor;
  return {
    ancho: Math.max(1, Math.round(anchoOriginal * factor)),
    alto: Math.max(1, Math.round(altoOriginal * factor)),
  };
}

function convertirCanvasAWebP(
  canvas: HTMLCanvasElement,
  calidad: number
): Promise<Blob> {
  return new Promise((resolver, rechazar) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          rechazar(new Error("El navegador no pudo exportar la fotografía en WebP."));
          return;
        }
        resolver(blob);
      },
      "image/webp",
      calidad
    );
  });
}

/**
 * Comprime una imagen en <canvas> del navegador a image/webp (<= 1280px y <= 300 KB).
 * Al redibujar los pixeles en canvas se eliminan de raiz todos los metadatos EXIF (GPS/camara).
 */
export async function comprimirFotoWebP(
  archivo: File,
  opciones: OpcionesCompresionFoto = {}
): Promise<ResultadoCompresionFoto> {
  if (!archivo.type.startsWith("image/")) {
    throw new Error("El archivo seleccionado debe ser una imagen válida.");
  }

  const maxDimension = opciones.maxDimension ?? DIMENSION_MAXIMA_DEFECTO;
  const maxBytes = opciones.maxBytes ?? PESO_MAXIMO_DEFECTO;

  const decodificada = await decodificarImagen(archivo);
  try {
    let { ancho, alto } = calcularDimensiones(
      decodificada.anchoOriginal,
      decodificada.altoOriginal,
      maxDimension
    );

    for (let intentoEscala = 0; intentoEscala < 3; intentoEscala += 1) {
      const canvas = document.createElement("canvas");
      canvas.width = ancho;
      canvas.height = alto;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        throw new Error("No se pudo inicializar el lienzo de compresión en el navegador.");
      }

      // El redibujo en canvas descarta EXIF/GPS y conserva solo la matriz de pixeles
      decodificada.dibujar(ctx, ancho, alto);

      for (const calidad of CALIDADES_WEBP) {
        const blob = await convertirCanvasAWebP(canvas, calidad);
        if (blob.type === "image/webp" && blob.size <= maxBytes) {
          return {
            blob,
            ancho,
            alto,
            tamanoBytes: blob.size,
          };
        }
      }

      ancho = Math.max(320, Math.round(ancho * 0.78));
      alto = Math.max(320, Math.round(alto * 0.78));
    }

    throw new Error("No fue posible comprimir la fotografía por debajo de 300 KB.");
  } finally {
    decodificada.liberar();
  }
}
