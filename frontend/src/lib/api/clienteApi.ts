import type { components } from "./esquema";

export type ProblemDetails = components["schemas"]["DetalleProblema"];
export type RespuestaSalud = components["schemas"]["RespuestaSalud"];
export type RespuestaListo = components["schemas"]["RespuestaListo"];
export type RespuestaUsuario = components["schemas"]["RespuestaUsuario"];

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

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  const urlBase = BASE_URL.replace(/\/$/, "");
  const url = `${urlBase}${rutaNormalizada}`;

  const respuesta = await fetch(url, {
    ...rest,
    headers: cabeceras,
  });

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
};
