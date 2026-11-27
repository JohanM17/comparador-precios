/** Etiquetas legibles de los tipos de caso que expone el backend. */
export const TIPOS_CASO_MODERACION: readonly {
  readonly valor: string;
  readonly etiqueta: string;
}[] = [
  { valor: "reporte_dudoso", etiqueta: "Reporte dudoso" },
  { valor: "rafaga", etiqueta: "Ráfaga" },
  { valor: "solicitud_correccion", etiqueta: "Solicitud de corrección" },
  { valor: "sugerencia_presentacion", etiqueta: "Sugerencia de presentación" },
  { valor: "verificacion_comercio", etiqueta: "Verificación de comercio" },
  { valor: "disputa_precio", etiqueta: "Disputa de precio" },
];

const ETIQUETAS_POR_TIPO: Readonly<Record<string, string>> = Object.fromEntries(
  TIPOS_CASO_MODERACION.map((tipo) => [tipo.valor, tipo.etiqueta])
);

/** Devuelve una etiqueta legible; si el backend agrega un tipo nuevo, lo humaniza. */
export function etiquetaTipoCaso(tipo: string): string {
  return ETIQUETAS_POR_TIPO[tipo] ?? tipo.replaceAll("_", " ");
}
