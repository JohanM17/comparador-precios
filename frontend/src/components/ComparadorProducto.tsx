"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, MapPin, Navigation } from "lucide-react";
import {
  clienteApi,
  type DatosComparacion,
  type ItemPromocion,
} from "@/lib/api/clienteApi";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import AvisoDatosDemo from "@/components/AvisoDatosDemo";
import BloquePromociones from "@/components/BloquePromociones";
import Cargando from "@/components/Cargando";
import EstadoError from "@/components/EstadoError";
import EstadoVacio from "@/components/EstadoVacio";
import ListaPrecios from "@/components/ListaPrecios";

type CriterioOrden = "precio_unitario" | "precio" | "distancia";

interface CoordenadasMemoria {
  readonly lat: number;
  readonly lng: number;
}

export interface ComparadorProductoProps {
  readonly productoId: string;
}

/**
 * Pantalla interactiva S2 (/producto/[id]) conectada con GET /v1/productos/{id}/comparacion.
 */
export default function ComparadorProducto({
  productoId,
}: ComparadorProductoProps): React.JSX.Element {
  const [presentacionId, setPresentacionId] = useState<string>("");
  const [orden, setOrden] = useState<CriterioOrden>("precio_unitario");
  const [ubicacion, setUbicacion] = useState<CoordenadasMemoria | null>(null);
  const [buscandoGps, setBuscandoGps] = useState(false);
  const [errorGps, setErrorGps] = useState<string | null>(null);

  const [datos, setDatos] = useState<DatosComparacion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  const cargarComparacion = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const res = await clienteApi.obtenerComparacionProducto(productoId, {
        presentacion_id: presentacionId || null,
        orden,
        lat: ubicacion?.lat ?? null,
        lng: ubicacion?.lng ?? null,
      });
      setDatos(res.datos);
    } catch (err) {
      setError(extraerInfoError(err, "No pudimos cargar la comparación de precios."));
    } finally {
      setCargando(false);
    }
  }, [productoId, presentacionId, orden, ubicacion]);

  useEffect(() => {
    void cargarComparacion();
  }, [cargarComparacion]);

  const manejarCambioPresentacion = (nuevoId: string): void => {
    setPresentacionId(nuevoId);
    if (!nuevoId && orden === "precio") {
      setOrden("precio_unitario");
    }
  };

  const activarCercania = (): void => {
    setErrorGps(null);
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setErrorGps("Tu navegador no soporta geolocalización.");
      return;
    }
    setBuscandoGps(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUbicacion({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setOrden("distancia");
        setBuscandoGps(false);
      },
      () => {
        setErrorGps("No pudimos obtener tu ubicación. Revisa los permisos del navegador.");
        setBuscandoGps(false);
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 }
    );
  };

  const promociones = (datos?.promociones ?? []) as ItemPromocion[];
  let etiquetaGps = "Ordenar por cercanía a mi ubicación";
  if (buscandoGps) {
    etiquetaGps = "Ubicando...";
  } else if (ubicacion) {
    etiquetaGps = "Ubicación activa en memoria";
  }

  return (
    <div>
      <AvisoDatosDemo visible={Boolean(datos?.meta.datos_de_demostracion)} />

      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="mb-4">
          <Link
            href="/"
            className="inline-flex min-h-10 items-center gap-1.5 text-sm font-semibold text-emerald-800 hover:text-cereza-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Volver al catálogo
          </Link>
        </div>

        {datos && (
          <section className="mb-8 rounded-2xl border border-slate-300 bg-superficie p-6 sm:p-8">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
              <div>
                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-cereza-700">
                  Comparado por {datos.producto.unidad_visualizacion}
                </span>
                <h1 className="mt-2 font-display text-4xl font-bold leading-none tracking-tight text-slate-900 sm:text-5xl">
                  {datos.producto.nombre}
                </h1>
              </div>

              <button
                type="button"
                onClick={activarCercania}
                disabled={buscandoGps}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-slate-400 bg-superficie px-5 py-2 text-sm font-semibold text-slate-900 transition-colors hover:border-emerald-800 hover:bg-emerald-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 disabled:opacity-60"
              >
                {ubicacion ? (
                  <MapPin className="h-4 w-4 text-emerald-700" aria-hidden="true" />
                ) : (
                  <Navigation className="h-4 w-4 text-slate-600" aria-hidden="true" />
                )}
                <span>{etiquetaGps}</span>
              </button>
            </div>

            {errorGps && (
              <p role="alert" className="mt-3 text-xs font-medium text-rose-700">
                {errorGps}
              </p>
            )}

            <div className="mt-5 grid grid-cols-1 gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="filtro-presentacion"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Presentación comercial
                </label>
                <select
                  id="filtro-presentacion"
                  value={presentacionId}
                  onChange={(e) => manejarCambioPresentacion(e.target.value)}
                  className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-superficie focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
                >
                  <option value="">Todas las presentaciones</option>
                  {datos.producto.presentaciones.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.etiqueta}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="selector-orden"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Criterio de ordenamiento
                </label>
                <select
                  id="selector-orden"
                  value={orden}
                  onChange={(e) => setOrden(e.target.value as CriterioOrden)}
                  className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-superficie focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
                >
                  <option value="precio_unitario">
                    Precio por {datos.producto.unidad_visualizacion} (menor primero)
                  </option>
                  <option value="precio" disabled={!presentacionId}>
                    Precio del empaque {!presentacionId ? "(elige presentación)" : ""}
                  </option>
                  <option value="distancia">Distancia al establecimiento</option>
                </select>
              </div>
            </div>
          </section>
        )}

        {cargando && <Cargando filas={5} etiqueta="Cargando comparación de precios..." />}

        {!cargando && error && (
          <EstadoError
            detalle={error.detalle}
            codigo={error.codigo}
            requestId={error.requestId}
            onReintentar={() => void cargarComparacion()}
          />
        )}

        {!cargando && !error && datos?.resultados.length === 0 && (
          <EstadoVacio
            titulo="Aún no hay precios reportados para este filtro"
            descripcion="Sé el primero en compartir un precio real desde la góndola para ayudar a tu comunidad."
            accionTexto="Reportar precio ahora"
            accionHref="/reportar"
          />
        )}

        {!cargando && !error && datos && datos.resultados.length > 0 && (
          <ListaPrecios
            resultados={datos.resultados}
            textoNeutralidad={datos.meta.texto_neutralidad}
            criterioOrden={datos.meta.criterio_orden}
            productoId={productoId}
          />
        )}

        {!cargando && !error && datos && <BloquePromociones promociones={promociones} />}
      </div>
    </div>
  );
}

