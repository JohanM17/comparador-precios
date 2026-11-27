import { solicitarApi } from "@/lib/api/clienteApi";
import type { components } from "@/lib/api/esquema";

export type EstablecimientoComercio = components["schemas"]["EstablecimientoComercioResumen"];
export type PrecioOficialEntrada = components["schemas"]["PrecioOficialEntrada"];
export type PreciosLoteEntrada = components["schemas"]["PreciosLoteEntrada"];
export type PreciosLoteRespuesta = components["schemas"]["PreciosLoteRespuesta"];
export type RevalidarRespuesta = components["schemas"]["RevalidarRespuesta"];
export type PromocionEntrada = components["schemas"]["PromocionEntrada"];
export type PromocionRespuesta = components["schemas"]["PromocionRespuesta"];
export type ReclamoComercioEntrada = components["schemas"]["ReclamoComercioEntrada"];
export type ReclamoComercioRespuesta = components["schemas"]["ReclamoComercioRespuesta"];
export type SolicitudVerificacion = components["schemas"]["SolicitudVerificacionResumen"];
export type ListaSolicitudesRespuesta = components["schemas"]["ListaSolicitudesRespuesta"];
export type VerificarComercioEntrada = components["schemas"]["VerificarComercioEntrada"];
export type VerificarComercioRespuesta = components["schemas"]["VerificarComercioRespuesta"];

/**
 * Cliente del modulo comercial (Etapa 2).
 *
 * Igual que el resto de clientes, solo transporta: no calcula precios, no
 * ordena resultados y no decide sellos. Todo eso vive en el backend.
 */
export const clienteComercio = {
  /** Cualquier cuenta autenticada puede reclamar; decide un moderador. */
  reclamarTitularidad: (token: string, entrada: ReclamoComercioEntrada) =>
    solicitarApi<ReclamoComercioRespuesta>("/v1/comercio/reclamos", {
      method: "POST",
      token,
      body: JSON.stringify(entrada),
    }),

  /** Cola de reclamos sin resolver. Solo rol moderador o admin. */
  listarSolicitudes: (token: string, limite = 50) =>
    solicitarApi<ListaSolicitudesRespuesta>(`/v1/moderacion/comercios?limite=${limite}`, {
      token,
    }),

  verificarComercio: (token: string, solicitudId: string, entrada: VerificarComercioEntrada) =>
    solicitarApi<VerificarComercioRespuesta>(`/v1/moderacion/comercios/${solicitudId}/verificar`, {
      method: "POST",
      token,
      body: JSON.stringify(entrada),
    }),

  listarEstablecimientos: (token: string) =>
    solicitarApi<EstablecimientoComercio[]>("/v1/comercio/establecimientos", { token }),

  /** Lote de precios oficiales. El backend acepta hasta 200 por envio. */
  publicarPrecios: (token: string, establecimientoId: string, precios: PrecioOficialEntrada[]) =>
    solicitarApi<PreciosLoteRespuesta>(
      `/v1/comercio/establecimientos/${establecimientoId}/precios`,
      { method: "PUT", token, body: JSON.stringify({ precios }) }
    ),

  /** «Todo sigue igual»: revalida sin reescribir precio por precio (D-06). */
  revalidar: (token: string, establecimientoId: string) =>
    solicitarApi<RevalidarRespuesta>(
      `/v1/comercio/establecimientos/${establecimientoId}/revalidar`,
      { method: "POST", token }
    ),

  listarPromociones: (token: string, establecimientoId: string) =>
    solicitarApi<PromocionRespuesta[]>(
      `/v1/comercio/establecimientos/${establecimientoId}/promociones`,
      { token }
    ),

  crearPromocion: (token: string, establecimientoId: string, entrada: PromocionEntrada) =>
    solicitarApi<PromocionRespuesta>(
      `/v1/comercio/establecimientos/${establecimientoId}/promociones`,
      { method: "POST", token, body: JSON.stringify(entrada) }
    ),

  revocarPromocion: (token: string, establecimientoId: string, promocionId: string) =>
    solicitarApi<Record<string, unknown>>(
      `/v1/comercio/establecimientos/${establecimientoId}/promociones/${promocionId}`,
      { method: "DELETE", token }
    ),
};
