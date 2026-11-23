"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, MapPin, Navigation } from "lucide-react";
import {
  clienteApi,
  type DatosComparacion,
  type DatosHistorial,
  type ItemPromocion,
} from "@/lib/api/clienteApi";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import AvisoDatosDemo from "@/components/AvisoDatosDemo";
import BloquePromociones from "@/components/BloquePromociones";
import Cargando from "@/components/Cargando";
import EstadoError from "@/components/EstadoError";
import EstadoVacio from "@/components/EstadoVacio";
import GraficaHistorialPrecios from "@/components/GraficaHistorialPrecios";
import ListaPrecios from "@/components/ListaPrecios";

type CriterioOrden = "precio_unitario" | "precio" | "distancia";

interface CoordenadasMemoria {
  readonly lat: number;
  readonly lng: number;
}

interface OpcionEstablecimientoHistorial {
  readonly id: string;
  readonly nombre: string;
  readonly barrio: string | null;
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

  const [establecimientoHistorialId, setEstablecimientoHistorialId] = useState<string>("");
  const [historial, setHistorial] = useState<DatosHistorial | null>(null);
  const [cargandoHistorial, setCargandoHistorial] = useState(false);
  const [errorHistorial, setErrorHistorial] = useState<InfoErrorVisible | null>(null);

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

  const establecimientosHistorial = useMemo<readonly OpcionEstablecimientoHistorial[]>(() => {
    const unicos = new Map<string, OpcionEstablecimientoHistorial>();
    for (const resultado of datos?.resultados ?? []) {
      const { id, nombre, barrio } = resultado.establecimiento;
      if (!unicos.has(id)) {
        unicos.set(id, { id, nombre, barrio: barrio ?? null });
      }
    }
    return Array.from(unicos.values());
  }, [datos]);

  const hayEstablecimientosHistorial = establecimientosHistorial.length > 0;

  // Mantiene una seleccion valida cuando cambian el producto o los resultados.
  useEffect(() => {
    if (establecimientosHistorial.length === 0) {
      setEstablecimientoHistorialId("");
      return;
    }
    const seleccionValida = establecimientosHistorial.some(
      (establecimiento) => establecimiento.id === establecimientoHistorialId
    );
    const primero = establecimientosHistorial[0];
    if (!seleccionValida && primero) {
      setEstablecimientoHistorialId(primero.id);
    }
  }, [establecimientosHistorial, establecimientoHistorialId]);

  // Numero de la ultima solicitud: descarta respuestas de selecciones anteriores.
  const solicitudHistorialRef = useRef(0);

  const cargarHistorial = useCallback(async (): Promise<void> => {
    if (!establecimientoHistorialId || !hayEstablecimientosHistorial) {
      solicitudHistorialRef.current += 1;
      setHistorial(null);
      setErrorHistorial(null);
      setCargandoHistorial(false);
      return;
    }

    const numeroSolicitud = solicitudHistorialRef.current + 1;
    solicitudHistorialRef.current = numeroSolicitud;

    setHistorial(null);
    setCargandoHistorial(true);
    setErrorHistorial(null);

    try {
      const respuesta = await clienteApi.obtenerHistorialProducto(productoId, {
        establecimiento_id: establecimientoHistorialId,
        presentacion_id: presentacionId || null,
        limite: 200,
      });
      if (solicitudHistorialRef.current !== numeroSolicitud) {
        return;
      }
      setHistorial(respuesta.datos);
    } catch (err) {
      if (solicitudHistorialRef.current !== numeroSolicitud) {
        return;
      }
      setErrorHistorial(extraerInfoError(err, "No pudimos cargar el historial de precios."));
    } finally {
      if (solicitudHistorialRef.current === numeroSolicitud) {
        setCargandoHistorial(false);
      }
    }
  }, [productoId, presentacionId, establecimientoHistorialId, hayEstablecimientosHistorial]);

  useEffect(() => {
    void cargarHistorial();
    return () => {
      // Invalida la solicitud en curso si la ficha se desmonta o cambia la seleccion.
      solicitudHistorialRef.current += 1;
    };
  }, [cargarHistorial]);

  const tituloHistorialId = React.useId();

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

      <div className="mx-auto max-w-5xl px-5 py-8 sm:px-6">
        <Link
          href="/"
          className="inline-flex min-h-10 items-center gap-1.5 text-[13.5px] text-slate-600 underline decoration-slate-300 underline-offset-4 transition-colors hover:text-slate-900 hover:decoration-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Volver al catálogo
        </Link>

        {datos && (
          <section className="mb-10 mt-7">
            <p className="rotulo">Comparado por {datos.producto.unidad_visualizacion}</p>
            <h1 className="mt-3 font-cursiva text-[clamp(2.1rem,6vw,3.3rem)] font-normal leading-[1.04] tracking-[-0.012em] text-slate-900">
              {datos.producto.nombre}
            </h1>

            <div className="mt-8 flex flex-col gap-5 border-t border-slate-200 pt-6 sm:flex-row sm:items-end sm:gap-10">
              <div className="min-w-0 flex-1">
                <label
                  htmlFor="filtro-presentacion"
                  className="block text-[12.5px] font-medium text-slate-500"
                >
                  Presentación comercial
                </label>
                <select
                  id="filtro-presentacion"
                  value={presentacionId}
                  onChange={(e) => manejarCambioPresentacion(e.target.value)}
                  className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
                >
                  <option value="">Todas las presentaciones</option>
                  {datos.producto.presentaciones.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.etiqueta}
                    </option>
                  ))}
                </select>
              </div>

              <div className="min-w-0 flex-1">
                <label
                  htmlFor="selector-orden"
                  className="block text-[12.5px] font-medium text-slate-500"
                >
                  Criterio de ordenamiento
                </label>
                <select
                  id="selector-orden"
                  value={orden}
                  onChange={(e) => setOrden(e.target.value as CriterioOrden)}
                  className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
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

              <button
                type="button"
                onClick={activarCercania}
                disabled={buscandoGps}
                className="inline-flex min-h-11 flex-none items-center gap-2 pb-2 text-[13.5px] text-slate-600 underline decoration-slate-300 underline-offset-4 transition-colors hover:text-slate-900 hover:decoration-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 disabled:opacity-60"
              >
                {ubicacion ? (
                  <MapPin className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                ) : (
                  <Navigation className="h-4 w-4" aria-hidden="true" />
                )}
                <span>{etiquetaGps}</span>
              </button>
            </div>

            {errorGps && (
              <p role="alert" className="mt-3 text-[13px] text-cereza-600">
                {errorGps}
              </p>
            )}
          </section>
        )}

        {cargando && <Cargando filas={5} etiqueta="Cargando comparación de precios…" />}

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

        {!cargando &&
          !error &&
          datos &&
          establecimientoHistorialId &&
          hayEstablecimientosHistorial && (
            <section
              aria-labelledby={tituloHistorialId}
              className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
            >
              <h2 id={tituloHistorialId} className="text-lg font-semibold text-slate-900 sm:text-xl">
                Historial de precios
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                Consulta cómo ha cambiado el precio en un establecimiento. Esta selección es
                independiente del orden de la comparación.
              </p>

              <div className="mt-4">
                <label
                  htmlFor="selector-establecimiento-historial"
                  className="block text-xs font-semibold text-slate-700"
                >
                  Establecimiento del historial
                </label>
                <select
                  id="selector-establecimiento-historial"
                  value={establecimientoHistorialId}
                  onChange={(e) => setEstablecimientoHistorialId(e.target.value)}
                  className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/20 sm:max-w-md"
                >
                  {establecimientosHistorial.map((establecimiento) => (
                    <option key={establecimiento.id} value={establecimiento.id}>
                      {establecimiento.barrio
                        ? `${establecimiento.nombre} · ${establecimiento.barrio}`
                        : establecimiento.nombre}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-5">
                <GraficaHistorialPrecios
                  datos={historial}
                  cargando={cargandoHistorial}
                  error={errorHistorial?.detalle ?? null}
                  onReintentar={() => void cargarHistorial()}
                />
              </div>
            </section>
          )}

        {!cargando && !error && datos && <BloquePromociones promociones={promociones} />}
      </div>
    </div>
  );
}

