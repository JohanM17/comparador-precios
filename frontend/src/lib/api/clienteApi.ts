import type { components } from "./esquema";

export type ProblemDetails = components["schemas"]["DetalleProblema"];
export type RespuestaSalud = components["schemas"]["RespuestaSalud"];
export type RespuestaListo = components["schemas"]["RespuestaListo"];
export type RespuestaUsuario = components["schemas"]["RespuestaUsuario"];
export type Categoria = components["schemas"]["CategoriaRespuesta"];
export type ProductoResumen = components["schemas"]["ProductoResumen"];
export type ListaProductosRespuesta = components["schemas"]["ListaProductosRespuesta"];
export type ProductoDetalle = components["schemas"]["ProductoDetalleRespuesta"];
export type DatosComparacion = components["schemas"]["DatosComparacion"];
export type RespuestaComparacion = components["schemas"]["RespuestaComparacion"];
export type ItemComparacion = components["schemas"]["ItemResultadoComparacion"];
export type MetaComparacion = components["schemas"]["MetaComparacion"];
export type EstablecimientoDetalle = components["schemas"]["EstablecimientoDetalleRespuesta"];
export type PrecioVigenteResumen = components["schemas"]["PrecioVigenteResumen"];
export type SolicitudCorreccionEntrada = components["schemas"]["SolicitudCorreccionEntrada"];
export type SolicitudCorreccionRespuesta = components["schemas"]["SolicitudCorreccionRespuesta"];
export type PoliticaTratamiento = components["schemas"]["PoliticaTratamientoRespuesta"];
export type AutorizacionEntrada = components["schemas"]["AutorizacionEntrada"];
export type AutorizacionRespuesta = components["schemas"]["AutorizacionRespuesta"];
export type PerfilUsuario = components["schemas"]["PerfilUsuarioRespuesta"];

export type SelloPrecio =
  | "confiable"
  | "oficial"
  | "pocos_datos"
  | "en_disputa"
  | "desactualizado"
  | "dudoso";

export interface ItemPromocion {
  readonly id?: string;
  readonly titulo?: string;
  readonly tipo?: string;
  readonly descripcion?: string;
  readonly condiciones?: string;
  readonly porcentaje_descuento?: number | null;
  readonly precio_especial_cop?: number | null;
  readonly pague_x?: number | null;
  readonly lleve_y?: number | null;
  readonly vigente_desde?: string | null;
  readonly vigente_hasta?: string | null;
  readonly hasta_revocar?: boolean;
  readonly establecimiento_nombre?: string | null;
  readonly presentacion_etiqueta?: string | null;
  readonly [key: string]: unknown;
}

export class ApiError extends Error {
  constructor(public readonly problem: ProblemDetails) {
    super(problem.detail || problem.title || "Error en la solicitud a la API");
    this.name = "ApiError";
  }
}

export interface OpcionesPeticion extends RequestInit {
  readonly token?: string | null;
  readonly idempotencyKey?: string | null;
}

export interface FiltrosProductos {
  readonly q?: string | null;
  readonly categoria_id?: number | null;
  readonly limite?: number;
  readonly cursor?: string | null;
}

export interface FiltrosComparacion {
  readonly presentacion_id?: string | null;
  readonly orden?: "precio_unitario" | "precio" | "distancia";
  readonly lat?: number | null;
  readonly lng?: number | null;
  readonly radio_km?: number | null;
}

function normalizarUrlApi(valorCrudo: string | undefined): string {
  let limpio = (valorCrudo ?? "").trim();
  while (limpio.endsWith("/")) {
    limpio = limpio.slice(0, -1);
  }
  if (!limpio) {
    return "http://localhost:8000";
  }
  const esLocal = /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(limpio);
  if (limpio.toLowerCase().startsWith("http://") || limpio.toLowerCase().startsWith("https://")) {
    return limpio;
  }
  return `${esLocal ? "http" : "https"}://${limpio}`;
}

const BASE_URL = normalizarUrlApi(process.env.NEXT_PUBLIC_API_URL);

function construirQuery(params: Record<string, string | number | null | undefined>): string {
  const sp = new URLSearchParams();
  for (const [clave, valor] of Object.entries(params)) {
    if (valor !== undefined && valor !== null && valor !== "") {
      sp.set(clave, String(valor));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export async function solicitarApi<T>(
  ruta: string,
  opciones: OpcionesPeticion = {}
): Promise<T> {
  const { token, idempotencyKey, headers: customHeaders, ...rest } = opciones;
  const cabeceras = new Headers(customHeaders);
  if (!cabeceras.has("Content-Type") && !(rest.body instanceof FormData)) {
    cabeceras.set("Content-Type", "application/json");
  }
  if (token) {
    cabeceras.set("Authorization", `Bearer ${token}`);
  }
  if (idempotencyKey) {
    cabeceras.set("Idempotency-Key", idempotencyKey);
  }

  const rutaNormalizada = ruta.startsWith("/") ? ruta : `/${ruta}`;
  const url = `${BASE_URL.replace(/\/$/, "")}${rutaNormalizada}`;
  const respuesta = await fetch(url, { ...rest, headers: cabeceras });

  if (!respuesta.ok) {
    let problema: ProblemDetails;
    try {
      problema = (await respuesta.json()) as ProblemDetails;
    } catch {
      problema = {
        type: "https://comparador.armenia.gov.co/errores/error-red",
        title: respuesta.statusText || "Error de comunicacion",
        status: respuesta.status,
        detail: `Error HTTP ${respuesta.status}`,
        instance: ruta,
        codigo: "ERROR_HTTP",
        request_id: respuesta.headers.get("X-Request-ID"),
      };
    }
    throw new ApiError(problema);
  }

  return (await respuesta.json()) as T;
}

export const clienteApi = {
  solicitar: solicitarApi,
  obtenerSalud: () => solicitarApi<RespuestaSalud>("/v1/salud"),
  obtenerSaludListo: () => solicitarApi<RespuestaListo>("/v1/salud/listo"),
  obtenerPerfilActual: (token: string) =>
    solicitarApi<RespuestaUsuario>("/v1/auth/perfil-actual", { token }),
  listarCategorias: () => solicitarApi<Categoria[]>("/v1/categorias"),
  buscarProductos: (filtros: FiltrosProductos = {}) => {
    const qs = construirQuery({
      q: filtros.q,
      categoria_id: filtros.categoria_id,
      limite: filtros.limite ?? 24,
      cursor: filtros.cursor,
    });
    return solicitarApi<ListaProductosRespuesta>(`/v1/productos${qs}`);
  },
  obtenerComparacionProducto: (id: string, filtros: FiltrosComparacion = {}) => {
    const qs = construirQuery({
      presentacion_id: filtros.presentacion_id,
      orden: filtros.orden ?? "precio_unitario",
      lat: filtros.lat,
      lng: filtros.lng,
      radio_km: filtros.radio_km,
    });
    return solicitarApi<RespuestaComparacion>(`/v1/productos/${id}/comparacion${qs}`);
  },
  obtenerEstablecimiento: (
    id: string,
    coords?: { readonly lat?: number | null; readonly lng?: number | null }
  ) => {
    const qs = construirQuery({ lat: coords?.lat, lng: coords?.lng });
    return solicitarApi<EstablecimientoDetalle>(`/v1/establecimientos/${id}${qs}`);
  },
  enviarSolicitudCorreccion: (id: string, entrada: SolicitudCorreccionEntrada) =>
    solicitarApi<SolicitudCorreccionRespuesta>(
      `/v1/establecimientos/${id}/solicitudes-correccion`,
      { method: "POST", body: JSON.stringify(entrada) }
    ),
  obtenerPoliticaTratamiento: () =>
    solicitarApi<PoliticaTratamiento>("/v1/legal/politica-tratamiento"),
  obtenerMiCuenta: (token: string) =>
    solicitarApi<PerfilUsuario>("/v1/mi-cuenta", { token }),
  registrarAutorizacion: (token: string, entrada: AutorizacionEntrada) =>
    solicitarApi<AutorizacionRespuesta>("/v1/mi-cuenta/autorizacion", {
      method: "POST",
      token,
      body: JSON.stringify(entrada),
    }),
};
