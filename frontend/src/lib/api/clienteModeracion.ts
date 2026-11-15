import { solicitarApi } from "@/lib/api/clienteApi";
import type { components } from "@/lib/api/esquema";

export type CasoDetalle = components["schemas"]["CasoDetalleRespuesta"];
export type ListaCasosRespuesta = components["schemas"]["ListaCasosRespuesta"];
export type ResolverCasoEntrada = components["schemas"]["ResolverCasoEntrada"];
export type ParametroItem = components["schemas"]["ParametroItem"];
export type ListaParametrosRespuesta = components["schemas"]["ListaParametrosRespuesta"];
export type ItemAuditoria = components["schemas"]["ItemAuditoriaRespuesta"];
export type ListaAuditoriaRespuesta = components["schemas"]["ListaAuditoriaRespuesta"];
export type ConsultaCatalogoExterno = components["schemas"]["ConsultaCatalogoExternoRespuesta"];
export type ProductoCrearEntrada = components["schemas"]["ProductoCrearEntrada"];
export type ProductoActualizarEntrada = components["schemas"]["ProductoActualizarEntrada"];
export type PresentacionCrearEntrada = components["schemas"]["PresentacionCrearEntrada"];
export type EstablecimientoCrearEntrada = components["schemas"]["EstablecimientoCrearEntrada"];
export type AprobarSugerenciaEntrada = components["schemas"]["AprobarSugerenciaEntrada"];

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

export const clienteModeracion = {
  listarCasos: (
    token: string,
    filtros: {
      readonly estado?: string | null;
      readonly tipo?: string | null;
      readonly prioridad?: number | null;
      readonly limite?: number;
      readonly offset?: number;
    } = {}
  ) => {
    const qs = construirQuery({
      estado: filtros.estado,
      tipo: filtros.tipo,
      prioridad: filtros.prioridad,
      limite: filtros.limite ?? 20,
      offset: filtros.offset ?? 0,
    });
    return solicitarApi<ListaCasosRespuesta>(`/v1/moderacion/casos${qs}`, { token });
  },

  obtenerCaso: (token: string, id: string) =>
    solicitarApi<CasoDetalle>(`/v1/moderacion/casos/${id}`, { token }),

  resolverCaso: (token: string, id: string, entrada: ResolverCasoEntrada) =>
    solicitarApi<CasoDetalle>(`/v1/moderacion/casos/${id}/resolver`, {
      method: "POST",
      token,
      body: JSON.stringify(entrada),
    }),

  aprobarSugerencia: (token: string, id: string, entrada: AprobarSugerenciaEntrada) =>
    solicitarApi<Record<string, unknown>>(`/v1/moderacion/sugerencias/${id}/aprobar`, {
      method: "POST",
      token,
      body: JSON.stringify(entrada),
    }),

  rechazarSugerencia: (token: string, id: string, motivo: string) =>
    solicitarApi<Record<string, unknown>>(`/v1/moderacion/sugerencias/${id}/rechazar`, {
      method: "POST",
      token,
      body: JSON.stringify({ motivo }),
    }),

  listarParametros: (token: string) =>
    solicitarApi<ListaParametrosRespuesta>("/v1/moderacion/parametros", { token }),

  actualizarParametros: (token: string, parametros: Record<string, unknown>) =>
    solicitarApi<ListaParametrosRespuesta>("/v1/moderacion/parametros", {
      method: "PUT",
      token,
      body: JSON.stringify({ parametros }),
    }),

  listarAuditoria: (
    token: string,
    filtros: {
      readonly entidad?: string | null;
      readonly accion?: string | null;
      readonly limite?: number;
      readonly offset?: number;
    } = {}
  ) => {
    const qs = construirQuery({
      entidad: filtros.entidad,
      accion: filtros.accion,
      limite: filtros.limite ?? 30,
      offset: filtros.offset ?? 0,
    });
    return solicitarApi<ListaAuditoriaRespuesta>(`/v1/moderacion/auditoria${qs}`, { token });
  },

  consultarCatalogoExterno: (token: string, codigoBarras: string) =>
    solicitarApi<ConsultaCatalogoExterno>(
      `/v1/moderacion/catalogo-externo?codigo_barras=${encodeURIComponent(codigoBarras)}`,
      { token }
    ),

  crearProducto: (token: string, entrada: ProductoCrearEntrada) =>
    solicitarApi<Record<string, unknown>>("/v1/moderacion/productos", {
      method: "POST",
      token,
      body: JSON.stringify(entrada),
    }),

  actualizarProducto: (token: string, id: string, entrada: ProductoActualizarEntrada) =>
    solicitarApi<Record<string, unknown>>(`/v1/moderacion/productos/${id}`, {
      method: "PATCH",
      token,
      body: JSON.stringify(entrada),
    }),

  crearPresentacion: (token: string, entrada: PresentacionCrearEntrada) =>
    solicitarApi<Record<string, unknown>>("/v1/moderacion/presentaciones", {
      method: "POST",
      token,
      body: JSON.stringify(entrada),
    }),

  crearEstablecimiento: (token: string, entrada: EstablecimientoCrearEntrada) =>
    solicitarApi<Record<string, unknown>>("/v1/moderacion/establecimientos", {
      method: "POST",
      token,
      body: JSON.stringify(entrada),
    }),
};

