/**
 * Utilidades de presentacion del historial de precios.
 *
 * Solo traducen y formatean datos entregados por la API: no calculan precios,
 * no reordenan puntos ni aplican reglas de negocio.
 */

export type FormaMarcadorHistorial = "circulo" | "cuadrado" | "triangulo";

export interface EstiloOrigenHistorial {
  readonly origen: string;
  readonly etiqueta: string;
  readonly color: string;
  readonly forma: FormaMarcadorHistorial;
}

/** Origenes publicos del historial, en el orden de la leyenda. */
export const ORIGENES_HISTORIAL: readonly EstiloOrigenHistorial[] = [
  { origen: "usuario", etiqueta: "Reportado", color: "#047857", forma: "circulo" },
  { origen: "comercio", etiqueta: "Oficial", color: "#1d4ed8", forma: "cuadrado" },
  {
    origen: "semilla",
    etiqueta: "Semilla/demostración",
    color: "#b45309",
    forma: "triangulo",
  },
];

const ESTILOS_POR_ORIGEN: ReadonlyMap<string, EstiloOrigenHistorial> = new Map(
  ORIGENES_HISTORIAL.map((estilo) => [estilo.origen, estilo]),
);

const ESTILO_ORIGEN_DESCONOCIDO: EstiloOrigenHistorial = {
  origen: "desconocido",
  etiqueta: "Origen no identificado",
  color: "#475569",
  forma: "circulo",
};

const ETIQUETAS_ESTADO: Readonly<Record<string, string>> = {
  aceptado: "Aceptado",
  dudoso: "En revisión",
  rechazado: "Rechazado",
};

const ETIQUETAS_UNIDAD: Readonly<Record<string, string>> = {
  kg: "kg",
  l: "l",
  unidad: "unidad",
};

const FORMATO_FECHA = new Intl.DateTimeFormat("es-CO", {
  timeZone: "America/Bogota",
  dateStyle: "medium",
});

const FORMATO_EJE = new Intl.DateTimeFormat("es-CO", {
  timeZone: "America/Bogota",
  day: "2-digit",
  month: "short",
});

/** Devuelve etiqueta, color y forma del marcador para un origen del historial. */
export function estiloOrigen(origen: string): EstiloOrigenHistorial {
  const estilo = ESTILOS_POR_ORIGEN.get(origen);
  if (estilo) {
    return estilo;
  }
  return {
    ...ESTILO_ORIGEN_DESCONOCIDO,
    origen,
    etiqueta: origen.length > 0 ? origen.replaceAll("_", " ") : ESTILO_ORIGEN_DESCONOCIDO.etiqueta,
  };
}

/** Devuelve la etiqueta ciudadana del estado de un punto. */
export function etiquetaEstado(estado: string): string {
  return ETIQUETAS_ESTADO[estado] ?? estado.replaceAll("_", " ");
}

/** Indica si el estado corresponde a un punto en revision. */
export function esEstadoDudoso(estado: string): boolean {
  return estado === "dudoso";
}

/** Devuelve la unidad de visualizacion tal como se muestra al ciudadano. */
export function etiquetaUnidad(unidad: string): string {
  return ETIQUETAS_UNIDAD[unidad] ?? unidad;
}

/** Devuelve el titulo del eje de precios con su unidad de visualizacion. */
export function etiquetaEjePrecio(unidad: string): string {
  return `Precio por ${etiquetaUnidad(unidad)}`;
}

/** Formatea una fecha ISO como dia, mes y ano en la zona oficial de Colombia. */
export function formatearFechaHistorial(isoUtc: string): string {
  const fecha = new Date(isoUtc);
  if (Number.isNaN(fecha.getTime())) {
    return isoUtc;
  }
  return FORMATO_FECHA.format(fecha);
}

/** Formatea la marca de tiempo del eje X como dia y mes en Colombia. */
export function formatearMarcaEje(marcaMs: number): string {
  if (!Number.isFinite(marcaMs)) {
    return "";
  }
  return FORMATO_EJE.format(new Date(marcaMs));
}
