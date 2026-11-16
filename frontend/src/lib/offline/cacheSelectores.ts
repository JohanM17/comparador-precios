import type { EstablecimientoResumen } from "@/lib/api/clienteReportes";

const CLAVE_TIENDA_RECIENTE = "comparador_tienda_reciente_v1";
const CLAVE_CACHE_TIENDAS = "comparador_tiendas_cache_v1";
const CLAVE_PRES_RECIENTES = "comparador_presentaciones_recientes_v1";
const CLAVE_CACHE_PRES = "comparador_presentaciones_cache_v1";
const DOS_HORAS_MS = 2 * 60 * 60 * 1000;

export interface TiendaSeleccionada {
  readonly id: string;
  readonly nombre: string;
  readonly direccion?: string;
  readonly tipo?: string;
}

interface TiendaRecienteGuardada extends TiendaSeleccionada {
  readonly guardadoEn: number;
}

export interface PresentacionOpcion {
  readonly id: string;
  readonly etiqueta: string;
  readonly productoNombre: string;
  readonly marca?: string | null;
}

export function guardarTiendaReciente(tienda: TiendaSeleccionada): void {
  if (typeof window === "undefined") return;
  const registro: TiendaRecienteGuardada = { ...tienda, guardadoEn: Date.now() };
  try {
    window.sessionStorage.setItem(CLAVE_TIENDA_RECIENTE, JSON.stringify(registro));
  } catch {
    // Ignorar error de cuota
  }
}

export function leerTiendaReciente(): TiendaSeleccionada | null {
  if (typeof window === "undefined") return null;
  try {
    const bruto = window.sessionStorage.getItem(CLAVE_TIENDA_RECIENTE);
    if (!bruto) return null;
    const dato = JSON.parse(bruto) as TiendaRecienteGuardada;
    if (Date.now() - dato.guardadoEn > DOS_HORAS_MS) {
      window.sessionStorage.removeItem(CLAVE_TIENDA_RECIENTE);
      return null;
    }
    return { id: dato.id, nombre: dato.nombre, direccion: dato.direccion, tipo: dato.tipo };
  } catch {
    return null;
  }
}

export function guardarCacheTiendas(tiendas: readonly EstablecimientoResumen[]): void {
  if (typeof window === "undefined") return;
  try {
    const sinCoords = tiendas.map((t) => ({ ...t, distancia_m: null }));
    window.localStorage.setItem(CLAVE_CACHE_TIENDAS, JSON.stringify(sinCoords));
  } catch {
    // Ignorar cuota
  }
}

export function leerCacheTiendas(): EstablecimientoResumen[] {
  if (typeof window === "undefined") return [];
  try {
    const bruto = window.localStorage.getItem(CLAVE_CACHE_TIENDAS);
    return bruto ? (JSON.parse(bruto) as EstablecimientoResumen[]) : [];
  } catch {
    return [];
  }
}

export function guardarPresentacionReciente(opcion: PresentacionOpcion): void {
  if (typeof window === "undefined") return;
  try {
    const actuales = leerPresentacionesRecientes();
    const filtradas = actuales.filter((item) => item.id !== opcion.id);
    window.localStorage.setItem(CLAVE_PRES_RECIENTES, JSON.stringify([opcion, ...filtradas].slice(0, 5)));
  } catch {
    // Ignorar cuota
  }
}

export function leerPresentacionesRecientes(): PresentacionOpcion[] {
  if (typeof window === "undefined") return [];
  try {
    const bruto = window.localStorage.getItem(CLAVE_PRES_RECIENTES);
    return bruto ? (JSON.parse(bruto) as PresentacionOpcion[]) : [];
  } catch {
    return [];
  }
}

export function guardarCachePresentaciones(opciones: readonly PresentacionOpcion[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(CLAVE_CACHE_PRES, JSON.stringify(opciones));
  } catch {
    // Ignorar cuota
  }
}

export function leerCachePresentaciones(): PresentacionOpcion[] {
  if (typeof window === "undefined") return [];
  try {
    const bruto = window.localStorage.getItem(CLAVE_CACHE_PRES);
    return bruto ? (JSON.parse(bruto) as PresentacionOpcion[]) : [];
  } catch {
    return [];
  }
}

