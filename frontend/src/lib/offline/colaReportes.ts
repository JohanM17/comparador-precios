import { ApiError } from "@/lib/api/clienteApi";
import { clienteReportes } from "@/lib/api/clienteReportes";
import {
  actualizarEnCola,
  contarColaReportes,
  eliminarDeCola,
  listarColaReportes,
  type ReporteEnCola,
  type ResumenSincronizacion,
} from "@/lib/offline/almacenColaReportes";

export {
  ALMACEN_COLA_REPORTES,
  NOMBRE_BD_OFFLINE,
  VERSION_BD_OFFLINE,
  contarColaReportes,
  eliminarDeCola,
  encolarReporteOffline,
  listarColaReportes,
  type EntradaNuevaCola,
  type ReporteEnCola,
  type ResumenSincronizacion,
} from "@/lib/offline/almacenColaReportes";

let sincronizacionEnCurso = false;

async function subirFotoSubpasoA(
  item: ReporteEnCola,
  token: string
): Promise<string> {
  if (!item.foto_blob) {
    throw new Error("No existe blob de fotografía para subir.");
  }
  const tipoMime = item.foto_blob.type || "image/webp";
  const nombreArchivo = `evidencia_${item.idempotency_key.slice(0, 8)}.webp`;

  const urlResp = await clienteReportes.solicitarUrlSubidaFoto(token, {
    nombre_archivo: nombreArchivo,
    tipo_mime: tipoMime,
    tamano_bytes: item.foto_blob.size,
  });

  const subida = await fetch(urlResp.url_firmada, {
    method: "PUT",
    headers: { "Content-Type": tipoMime },
    body: item.foto_blob,
  });

  if (!subida.ok) {
    throw new Error(`Error al subir fotografía a URL firmada (${subida.status}).`);
  }

  return urlResp.ruta;
}

function calcularBackoffMs(intentos: number): number {
  return Math.min(300_000, 2_000 * 2 ** Math.max(0, intentos - 1));
}

function esElegibleReintento(item: ReporteEnCola, ahora: number, forzar: boolean): boolean {
  return forzar || !item.proximo_intento_en || item.proximo_intento_en <= ahora;
}

function extraerMensajeErrorSync(err: unknown): string {
  return err instanceof Error ? err.message : "Error temporal al sincronizar reporte.";
}

interface ResultadoElementoSync {
  readonly tipo: "ok" | "descartado422" | "error";
  readonly error?: string;
}

interface AcumuladorSync {
  readonly sincronizados: number;
  readonly descartados422: number;
  readonly errores: readonly string[];
}

async function procesarElementoCola(
  item: ReporteEnCola,
  token: string
): Promise<ResultadoElementoSync> {
  try {
    // Subpaso A: subir fotografia si existe foto_blob y aun no hay foto_ruta_remota
    if (item.foto_blob !== null && item.foto_ruta_remota === null) {
      item.foto_ruta_remota = await subirFotoSubpasoA(item, token);
      await actualizarEnCola(item);
    }

    // Subpaso B: enviar reporte con la misma Idempotency-Key UUIDv4
    await clienteReportes.crearReporte(token, item.idempotency_key, {
      presentacion_id: item.presentacion_id,
      establecimiento_id: item.establecimiento_id,
      precio_cop: item.precio_cop,
      observado_en: item.observado_en,
      foto_ruta: item.foto_ruta_remota,
    });

    // Subpaso C (exito 201 o 200 idempotente): eliminar de IndexedDB
    await eliminarDeCola(item.idempotency_key);
    return { tipo: "ok" };
  } catch (err) {
    if (err instanceof ApiError && err.problem.status === 422) {
      // Subpaso C (422 no recuperable): eliminar de cola y notificar
      await eliminarDeCola(item.idempotency_key);
      return {
        tipo: "descartado422",
        error: err.problem.detail || "Reporte descartado por validación (422).",
      };
    }

    const mensaje = extraerMensajeErrorSync(err);
    item.intentos += 1;
    item.ultimo_error = mensaje;
    item.proximo_intento_en = Date.now() + calcularBackoffMs(item.intentos);
    await actualizarEnCola(item);
    return { tipo: "error", error: mensaje };
  }
}

async function sincronizarEnSerie(
  items: readonly ReporteEnCola[],
  indice: number,
  token: string,
  acum: AcumuladorSync
): Promise<AcumuladorSync> {
  if (indice >= items.length) {
    return acum;
  }
  const res = await procesarElementoCola(items[indice], token);
  const errores = res.error ? [...acum.errores, res.error] : acum.errores;
  const siguiente: AcumuladorSync = {
    sincronizados: acum.sincronizados + (res.tipo === "ok" ? 1 : 0),
    descartados422: acum.descartados422 + (res.tipo === "descartado422" ? 1 : 0),
    errores,
  };
  return sincronizarEnSerie(items, indice + 1, token, siguiente);
}

/**
 * Sincroniza los reportes almacenados en IndexedDB siguiendo estrictamente el Flujo F4:
 * Subpaso A (foto primero y persistir foto_ruta_remota), Subpaso B (POST /v1/reportes con Idempotency-Key),
 * Subpaso C (eliminar en 201/200/422; backoff en red/429/5xx).
 */
export async function sincronizarColaReportes(
  obtenerToken: () => Promise<string | null>,
  opciones: { readonly forzar?: boolean } = {}
): Promise<ResumenSincronizacion> {
  if (typeof window === "undefined" || !navigator.onLine || sincronizacionEnCurso) {
    const pendientes = await contarColaReportes();
    return { sincronizados: 0, descartados422: 0, pendientes, errores: [] };
  }

  sincronizacionEnCurso = true;
  try {
    const items = await listarColaReportes();
    if (items.length === 0) {
      return { sincronizados: 0, descartados422: 0, pendientes: 0, errores: [] };
    }

    const token = await obtenerToken();
    if (!token) {
      return {
        sincronizados: 0,
        descartados422: 0,
        pendientes: items.length,
        errores: ["Inicia sesión para sincronizar los reportes pendientes."],
      };
    }

    const ahora = Date.now();
    const elegibles = items.filter((item) =>
      esElegibleReintento(item, ahora, Boolean(opciones.forzar))
    );
    const acum = await sincronizarEnSerie(elegibles, 0, token, {
      sincronizados: 0,
      descartados422: 0,
      errores: [],
    });
    const pendientes = await contarColaReportes();
    return { ...acum, pendientes };
  } finally {
    sincronizacionEnCurso = false;
  }
}

export function registrarSincronizacionAutomatica(
  obtenerToken: () => Promise<string | null>,
  onSincronizado?: (resumen: ResumenSincronizacion) => void
): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const ejecutar = (): void => {
    void sincronizarColaReportes(obtenerToken, { forzar: true }).then((resumen) => {
      onSincronizado?.(resumen);
    });
  };

  window.addEventListener("online", ejecutar);
  if (navigator.onLine) {
    ejecutar();
  }

  return () => {
    window.removeEventListener("online", ejecutar);
  };
}
