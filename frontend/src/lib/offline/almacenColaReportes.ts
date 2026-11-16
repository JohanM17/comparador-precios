import { openDB, type DBSchema, type IDBPDatabase } from "idb";

export const NOMBRE_BD_OFFLINE = "comparador_precios_offline";
export const VERSION_BD_OFFLINE = 1;
export const ALMACEN_COLA_REPORTES = "cola_reportes";

export interface ReporteEnCola {
  readonly idempotency_key: string;
  readonly presentacion_id: string;
  readonly presentacion_etiqueta?: string;
  readonly establecimiento_id: string;
  readonly establecimiento_nombre?: string;
  readonly precio_cop: number;
  readonly observado_en: string;
  readonly foto_blob: Blob | null;
  foto_ruta_remota: string | null;
  intentos: number;
  ultimo_error?: string | null;
  proximo_intento_en?: number | null;
  readonly creado_localmente_en: string;
}

export type EntradaNuevaCola = Omit<
  ReporteEnCola,
  "foto_ruta_remota" | "intentos" | "ultimo_error" | "proximo_intento_en" | "creado_localmente_en"
>;

export interface ResumenSincronizacion {
  readonly sincronizados: number;
  readonly descartados422: number;
  readonly pendientes: number;
  readonly errores: readonly string[];
}

interface EsquemaBdOffline extends DBSchema {
  cola_reportes: { key: string; value: ReporteEnCola };
}

async function abrirBdOffline(): Promise<IDBPDatabase<EsquemaBdOffline>> {
  return openDB<EsquemaBdOffline>(NOMBRE_BD_OFFLINE, VERSION_BD_OFFLINE, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(ALMACEN_COLA_REPORTES)) {
        db.createObjectStore(ALMACEN_COLA_REPORTES, { keyPath: "idempotency_key" });
      }
    },
  });
}

export async function encolarReporteOffline(entrada: EntradaNuevaCola): Promise<ReporteEnCola> {
  const db = await abrirBdOffline();
  const registro: ReporteEnCola = {
    ...entrada,
    foto_ruta_remota: null,
    intentos: 0,
    ultimo_error: null,
    proximo_intento_en: null,
    creado_localmente_en: new Date().toISOString(),
  };
  await db.put(ALMACEN_COLA_REPORTES, registro);
  db.close();
  return registro;
}

export async function listarColaReportes(): Promise<ReporteEnCola[]> {
  if (typeof window === "undefined" || !("indexedDB" in window)) return [];
  const db = await abrirBdOffline();
  const items = await db.getAll(ALMACEN_COLA_REPORTES);
  db.close();
  return items.sort((a, b) => a.creado_localmente_en.localeCompare(b.creado_localmente_en));
}

export async function contarColaReportes(): Promise<number> {
  if (typeof window === "undefined" || !("indexedDB" in window)) return 0;
  const db = await abrirBdOffline();
  const total = await db.count(ALMACEN_COLA_REPORTES);
  db.close();
  return total;
}

export async function actualizarEnCola(registro: ReporteEnCola): Promise<void> {
  const db = await abrirBdOffline();
  await db.put(ALMACEN_COLA_REPORTES, registro);
  db.close();
}

export async function eliminarDeCola(idempotencyKey: string): Promise<void> {
  const db = await abrirBdOffline();
  await db.delete(ALMACEN_COLA_REPORTES, idempotencyKey);
  db.close();
}
