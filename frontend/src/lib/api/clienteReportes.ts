import { solicitarApi } from "@/lib/api/clienteApi";
import type { components } from "@/lib/api/esquema";

export type ListaEstablecimientosRespuesta = components["schemas"]["ListaEstablecimientosRespuesta"];
export type EstablecimientoResumen = components["schemas"]["EstablecimientoResumen"];
export type ProductoDetalle = components["schemas"]["ProductoDetalleRespuesta"];
export type PresentacionResumen = components["schemas"]["PresentacionResumen"];
export type SolicitudUrlSubida = components["schemas"]["SolicitudUrlSubida"];
export type RespuestaUrlSubida = components["schemas"]["RespuestaUrlSubida"];
export type CrearReporteEntrada = components["schemas"]["CrearReporteEntrada"];
export type CrearReporteRespuesta = components["schemas"]["CrearReporteRespuesta"];
export type SugerenciaPresentacionEntrada = components["schemas"]["SugerenciaPresentacionEntrada"];
export type MisReportesRespuesta = components["schemas"]["MisReportesRespuesta"];
export type ElementoReportePropio = components["schemas"]["ElementoReportePropio"];
export type PerfilUsuario = components["schemas"]["PerfilUsuarioRespuesta"];
export type EliminarCuentaRespuesta = components["schemas"]["EliminarCuentaRespuesta"];

export interface FiltrosEstablecimientos {
  readonly q?: string | null;
  readonly tipo?: string | null;
  readonly municipio?: string | null;
  readonly lat?: number | null;
  readonly lng?: number | null;
  readonly radio_km?: number | null;
  readonly limite?: number;
}

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

export const clienteReportes = {
  listarEstablecimientos: (filtros: FiltrosEstablecimientos = {}) => {
    const qs = construirQuery({
      q: filtros.q,
      tipo: filtros.tipo,
      municipio: filtros.municipio,
      lat: filtros.lat,
      lng: filtros.lng,
      radio_km: filtros.radio_km,
      limite: filtros.limite ?? 50,
    });
    return solicitarApi<ListaEstablecimientosRespuesta>(`/v1/establecimientos${qs}`);
  },

  obtenerProductoDetalle: (id: string) =>
    solicitarApi<ProductoDetalle>(`/v1/productos/${id}`),

  solicitarUrlSubidaFoto: (token: string, entrada: SolicitudUrlSubida) =>
    solicitarApi<RespuestaUrlSubida>("/v1/fotos/url-subida", {
      method: "POST",
      token,
      body: JSON.stringify(entrada),
    }),

  crearReporte: (
    token: string,
    idempotencyKey: string,
    entrada: CrearReporteEntrada
  ) =>
    solicitarApi<CrearReporteRespuesta>("/v1/reportes", {
      method: "POST",
      token,
      idempotencyKey,
      body: JSON.stringify(entrada),
    }),

  sugerirPresentacion: (token: string, entrada: SugerenciaPresentacionEntrada) =>
    solicitarApi<{ id: string; caso_id: string; estado: string; mensaje: string }>(
      "/v1/sugerencias-presentacion",
      {
        method: "POST",
        token,
        body: JSON.stringify(entrada),
      }
    ),

  obtenerMisReportes: (token: string, pagina = 1, limite = 20) =>
    solicitarApi<MisReportesRespuesta>(
      `/v1/mis-reportes?pagina=${pagina}&limite=${limite}`,
      { token }
    ),

  actualizarAlias: (token: string, alias: string) =>
    solicitarApi<PerfilUsuario>("/v1/mi-cuenta", {
      method: "PATCH",
      token,
      body: JSON.stringify({ alias }),
    }),

  eliminarMiCuenta: (token: string) =>
    solicitarApi<EliminarCuentaRespuesta>("/v1/mi-cuenta", {
      method: "DELETE",
      token,
    }),
};

