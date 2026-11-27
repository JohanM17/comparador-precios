"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BadgeCheck, Clock, Flag, MapPin, Store } from "lucide-react";
import { clienteApi, type EstablecimientoDetalle } from "@/lib/api/clienteApi";
import {
  extraerInfoError,
  formatearAntiguedadRelativa,
  formatearDistancia,
  formatearFechaBogota,
  formatearPesos,
  formatearTipoEstablecimiento,
  type InfoErrorVisible,
} from "@/lib/formato";
import Cargando from "@/components/Cargando";
import EstadoError from "@/components/EstadoError";
import EstadoVacio from "@/components/EstadoVacio";
import ModalCorreccionTienda from "@/components/ModalCorreccionTienda";
import SelloConfianza from "@/components/SelloConfianza";

export interface FichaTiendaProps {
  readonly establecimientoId: string;
}

const ELEMENTOS_POR_PAGINA = 20;

/**
 * Ficha publica de establecimiento (S3) conectada con GET /v1/establecimientos/{id}.
 */
export default function FichaTienda({
  establecimientoId,
}: FichaTiendaProps): React.JSX.Element {
  const [tienda, setTienda] = useState<EstablecimientoDetalle | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<InfoErrorVisible | null>(null);
  const [modalAbierto, setModalAbierto] = useState(false);
  const [pagina, setPagina] = useState(1);

  const cargarTienda = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const data = await clienteApi.obtenerEstablecimiento(establecimientoId);
      setTienda(data);
      setPagina(1);
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible cargar la ficha del establecimiento."));
    } finally {
      setCargando(false);
    }
  }, [establecimientoId]);

  useEffect(() => {
    void cargarTienda();
  }, [cargarTienda]);

  const precios = tienda?.precios_vigentes ?? [];
  const totalPaginas = Math.max(1, Math.ceil(precios.length / ELEMENTOS_POR_PAGINA));
  const inicio = (pagina - 1) * ELEMENTOS_POR_PAGINA;
  const preciosVisibles = precios.slice(inicio, inicio + ELEMENTOS_POR_PAGINA);

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-4">
        <Link
          href="/"
          className="inline-flex min-h-10 items-center gap-1.5 text-sm font-semibold text-emerald-800 hover:text-emerald-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Volver al inicio
        </Link>
      </div>

      {cargando && <Cargando filas={5} etiqueta="Cargando ficha del establecimiento..." />}

      {!cargando && error && (
        <EstadoError
          detalle={error.detalle}
          codigo={error.codigo}
          requestId={error.requestId}
          onReintentar={() => void cargarTienda()}
        />
      )}

      {!cargando && !error && tienda && (
        <div className="space-y-6">
          <section className="rounded-2xl border border-slate-300 bg-superficie p-6">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-0.5 text-xs font-semibold text-slate-800">
                    <Store className="h-3.5 w-3.5" aria-hidden="true" />
                    {formatearTipoEstablecimiento(tienda.tipo)}
                  </span>
                  {tienda.estado_verificacion === "verificado" && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-blue-300 bg-blue-50 px-3 py-0.5 text-xs font-semibold text-blue-900">
                      <BadgeCheck className="h-3.5 w-3.5" aria-hidden="true" />
                      Comercio verificado
                    </span>
                  )}
                  {tienda.distancia_m !== null && tienda.distancia_m !== undefined && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-0.5 text-xs font-semibold text-emerald-900">
                      <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                      {formatearDistancia(tienda.distancia_m)}
                    </span>
                  )}
                </div>

                <h1 className="mt-3 text-2xl font-bold text-slate-900 sm:text-3xl">
                  {tienda.nombre}
                </h1>
                {tienda.cadena && (
                  <p className="mt-0.5 text-sm font-medium text-slate-600">Cadena: {tienda.cadena}</p>
                )}
                <p className="mt-2 text-sm text-slate-700">
                  {[tienda.direccion, tienda.barrio, tienda.municipio, tienda.departamento]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>

              <button
                type="button"
                onClick={() => setModalAbierto(true)}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-superficie px-4 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-700"
              >
                <Flag className="h-4 w-4 text-slate-600" aria-hidden="true" />
                <span>¿Hay información errónea sobre este negocio?</span>
              </button>
            </div>
          </section>

          <section aria-labelledby="titulo-precios-tienda" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="titulo-precios-tienda" className="text-lg font-bold text-slate-900">
                Precios vigentes en este establecimiento ({precios.length})
              </h2>
            </div>

            {precios.length === 0 ? (
              <EstadoVacio
                titulo="Este establecimiento aún no tiene precios vigentes"
                descripcion="Ayuda a tus vecinos reportando el primer precio observado en góndola."
                accionTexto="Reportar precio aquí"
                accionHref="/reportar"
              />
            ) : (
              <div className="space-y-3">
                {preciosVisibles.map((p) => (
                  <article
                    key={p.presentacion_id}
                    className="flex flex-col justify-between gap-4 rounded-xl border border-slate-300 bg-superficie p-4 sm:flex-row sm:items-center"
                  >
                    <div className="space-y-1.5">
                      <SelloConfianza
                        sello={p.sello}
                        motivoSello={p.motivo_sello ?? null}
                        avisoRevalidacion={
                          p.requiere_revalidacion
                            ? p.motivo_sello || "Precio oficial por revalidar"
                            : null
                        }
                      />
                      <div>
                        <Link
                          href={`/producto/${p.producto_id}`}
                          className="text-base font-bold text-slate-900 underline decoration-slate-300 underline-offset-4 hover:text-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                        >
                          {p.producto_nombre}
                        </Link>
                        <p className="text-xs font-medium text-slate-600">{p.presentacion_etiqueta}</p>
                      </div>
                      <time
                        dateTime={p.ultimo_reporte_en}
                        title={formatearFechaBogota(p.ultimo_reporte_en)}
                        className="inline-flex items-center gap-1 text-xs text-slate-500"
                      >
                        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                        {formatearAntiguedadRelativa(p.ultimo_reporte_en)}
                      </time>
                    </div>

                    <div className="flex items-center justify-between gap-4 sm:flex-col sm:items-end">
                      <p className="text-xl font-extrabold text-slate-900">
                        {formatearPesos(p.precio_cop)} COP
                      </p>
                      <Link
                        href={`/reportar?tienda=${tienda.id}&presentacion=${p.presentacion_id}`}
                        className="inline-flex min-h-10 items-center rounded-xl bg-bosque-800 px-3.5 py-2 text-xs font-semibold text-white hover:bg-bosque-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                      >
                        Confirmar / Actualizar
                      </Link>
                    </div>
                  </article>
                ))}

                {totalPaginas > 1 && (
                  <div className="flex items-center justify-between pt-2">
                    <button
                      type="button"
                      disabled={pagina <= 1}
                      onClick={() => setPagina((prev) => Math.max(1, prev - 1))}
                      className="min-h-10 rounded-lg border border-slate-300 bg-superficie px-3 py-1.5 text-xs font-semibold text-slate-800 disabled:opacity-50"
                    >
                      Anterior
                    </button>
                    <span className="text-xs font-medium text-slate-600">
                      Página {pagina} de {totalPaginas}
                    </span>
                    <button
                      type="button"
                      disabled={pagina >= totalPaginas}
                      onClick={() => setPagina((prev) => Math.min(totalPaginas, prev + 1))}
                      className="min-h-10 rounded-lg border border-slate-300 bg-superficie px-3 py-1.5 text-xs font-semibold text-slate-800 disabled:opacity-50"
                    >
                      Siguiente
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>

          <ModalCorreccionTienda
            establecimientoId={tienda.id}
            establecimientoNombre={tienda.nombre}
            abierto={modalAbierto}
            onCerrar={() => setModalAbierto(false)}
          />
        </div>
      )}
    </div>
  );
}

