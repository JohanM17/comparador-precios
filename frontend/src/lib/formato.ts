import { ApiError } from "@/lib/api/clienteApi";

const FORMATEADOR_PESOS = new Intl.NumberFormat("es-CO", {
  maximumFractionDigits: 0,
});

const FORMATEADOR_BOGOTA = new Intl.DateTimeFormat("es-CO", {
  timeZone: "America/Bogota",
  dateStyle: "medium",
  timeStyle: "short",
});

const ETIQUETAS_TIPO_ESTABLECIMIENTO: Readonly<Record<string, string>> = {
  tienda_barrio: "Tienda de barrio",
  supermercado: "Supermercado",
  minimercado: "Minimercado",
  plaza_mercado: "Plaza de mercado",
  fruver: "Fruver",
  drogueria: "Droguería",
  panaderia: "Panadería",
};

/** Formatea un monto entero en pesos colombianos ($X.XXX). */
export function formatearPesos(valorCop: number): string {
  return `$${FORMATEADOR_PESOS.format(Math.round(valorCop))}`;
}

/** Formatea una distancia en metros para lectura ciudadana. */
export function formatearDistancia(distanciaM: number): string {
  if (distanciaM < 1000) {
    return `${Math.round(distanciaM)} m`;
  }
  const km = (distanciaM / 1000).toFixed(1).replace(".", ",");
  return `${km} km`;
}

/** Convierte una fecha ISO UTC a hora oficial de Colombia (America/Bogota). */
export function formatearFechaBogota(isoUtc: string): string {
  const fecha = new Date(isoUtc);
  if (Number.isNaN(fecha.getTime())) {
    return isoUtc;
  }
  return `${FORMATEADOR_BOGOTA.format(fecha)} (Colombia)`;
}

/** Calcula una etiqueta relativa legible de antiguedad sin alterar datos. */
export function formatearAntiguedadRelativa(isoUtc: string): string {
  const marca = new Date(isoUtc).getTime();
  if (Number.isNaN(marca)) {
    return "Fecha desconocida";
  }
  const segundos = Math.max(0, Math.floor((Date.now() - marca) / 1000));
  if (segundos < 60) {
    return "Hace menos de 1 min";
  }
  const minutos = Math.floor(segundos / 60);
  if (minutos < 60) {
    return `Hace ${minutos} min`;
  }
  const horas = Math.floor(minutos / 60);
  if (horas < 24) {
    return `Hace ${horas} h`;
  }
  const dias = Math.floor(horas / 24);
  return dias === 1 ? "Hace 1 día" : `Hace ${dias} días`;
}

/** Devuelve una etiqueta legible para el tipo de establecimiento. */
export function formatearTipoEstablecimiento(tipo: string): string {
  return ETIQUETAS_TIPO_ESTABLECIMIENTO[tipo] ?? tipo.replace(/_/g, " ");
}

export interface InfoErrorVisible {
  readonly detalle: string;
  readonly codigo?: string;
  readonly requestId?: string;
}

/** Extrae detalle, codigo y request_id desde un error desconocido. */
export function extraerInfoError(error: unknown, respaldo: string): InfoErrorVisible {
  if (error instanceof ApiError) {
    return {
      detalle: error.problem.detail || error.message,
      codigo: error.problem.codigo,
      requestId: error.problem.request_id ?? undefined,
    };
  }
  if (error instanceof Error) {
    return { detalle: error.message };
  }
  return { detalle: respaldo };
}

