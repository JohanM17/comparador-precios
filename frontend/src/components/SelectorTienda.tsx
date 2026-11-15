"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { MapPin, Navigation, Search, Store } from "lucide-react";
import { clienteReportes, type EstablecimientoResumen } from "@/lib/api/clienteReportes";
import { formatearDistancia, formatearTipoEstablecimiento } from "@/lib/formato";
import {
  guardarCacheTiendas,
  leerCacheTiendas,
  leerTiendaReciente,
  type TiendaSeleccionada,
} from "@/lib/offline/cacheSelectores";

export type { TiendaSeleccionada };

export interface SelectorTiendaProps {
  readonly valor: string;
  readonly onChange: (id: string, tienda?: TiendaSeleccionada) => void;
  readonly tiendaRecienteId?: string | null;
}

function ListaOpcionesTienda({
  cargando,
  tiendas,
  valor,
  onSeleccionar,
}: {
  readonly cargando: boolean;
  readonly tiendas: readonly EstablecimientoResumen[];
  readonly valor: string;
  readonly onSeleccionar: (id: string, tienda: TiendaSeleccionada) => void;
}): React.JSX.Element {
  if (cargando && tiendas.length === 0) {
    return <p className="py-2 text-xs text-slate-500">Cargando tiendas de Armenia...</p>;
  }
  if (tiendas.length === 0) {
    return <p className="py-2 text-xs text-slate-500">No encontramos tiendas con ese filtro.</p>;
  }
  return (
    <>
      {tiendas.map((tienda) => {
        const activa = tienda.id === valor;
        return (
          <button
            key={tienda.id}
            type="button"
            role="option"
            aria-selected={activa}
            onClick={() =>
              onSeleccionar(tienda.id, {
                id: tienda.id,
                nombre: tienda.nombre,
                direccion: tienda.direccion,
                tipo: tienda.tipo,
              })
            }
            className={`flex min-h-11 w-full items-center justify-between gap-2 rounded-xl border px-3 py-2 text-left transition-colors ${
              activa
                ? "border-emerald-700 bg-emerald-700 text-white"
                : "border-slate-200 bg-white text-slate-900 hover:bg-slate-50"
            }`}
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{tienda.nombre}</p>
              <p className={`truncate text-xs ${activa ? "text-emerald-100" : "text-slate-500"}`}>
                {formatearTipoEstablecimiento(tienda.tipo)} · {tienda.direccion}
              </p>
            </div>
            {typeof tienda.distancia_m === "number" && (
              <span className={`inline-flex items-center gap-1 text-xs font-semibold ${activa ? "text-white" : "text-emerald-800"}`}>
                <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                {formatearDistancia(tienda.distancia_m)}
              </span>
            )}
          </button>
        );
      })}
    </>
  );
}

/**
 * Control tactil (min-h-11) de seleccion de establecimiento con memoria de 2 horas
 * en sessionStorage y busqueda por cercania GPS estrictamente en memoria.
 */
export default function SelectorTienda({
  valor,
  onChange,
  tiendaRecienteId,
}: SelectorTiendaProps): React.JSX.Element {
  const [busqueda, setBusqueda] = useState("");
  const [tiendas, setTiendas] = useState<EstablecimientoResumen[]>([]);
  const [cargando, setCargando] = useState(false);
  const [gpsEstado, setGpsEstado] = useState<string | null>(null);
  const [reciente, setReciente] = useState<TiendaSeleccionada | null>(null);

  const cargarTiendas = useCallback(
    async (coords?: { readonly lat: number; readonly lng: number }) => {
      setCargando(true);
      try {
        const res = await clienteReportes.listarEstablecimientos({
          q: busqueda.trim() || null,
          lat: coords?.lat ?? null,
          lng: coords?.lng ?? null,
          radio_km: coords ? 5 : null,
          limite: 25,
        });
        setTiendas(res.datos);
        guardarCacheTiendas(res.datos);
      } catch {
        setTiendas(leerCacheTiendas());
      } finally {
        setCargando(false);
      }
    },
    [busqueda]
  );

  useEffect(() => {
    const guardada = leerTiendaReciente();
    setReciente(guardada);
    if (!valor && (tiendaRecienteId || guardada?.id)) {
      const idObjetivo = tiendaRecienteId || guardada?.id || "";
      if (idObjetivo) {
        onChange(idObjetivo, guardada ?? undefined);
      }
    }
  }, [onChange, tiendaRecienteId, valor]);

  useEffect(() => {
    const temporizador = window.setTimeout(() => void cargarTiendas(), 200);
    return () => window.clearTimeout(temporizador);
  }, [cargarTiendas]);

  const buscarPorGps = (): void => {
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
      setGpsEstado("Tu navegador no soporta geolocalización.");
      return;
    }
    setGpsEstado("Buscando tiendas cercanas...");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsEstado("Ordenado por cercanía a tu ubicación actual.");
        void cargarTiendas({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      },
      () => setGpsEstado("No pudimos acceder al GPS. Selecciona la tienda por nombre."),
      { enableHighAccuracy: false, timeout: 6000, maximumAge: 60000 }
    );
  };

  const tiendasFiltradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return tiendas.slice(0, 8);
    return tiendas
      .filter(
        (t) =>
          t.nombre.toLowerCase().includes(q) ||
          t.direccion.toLowerCase().includes(q) ||
          (t.barrio?.toLowerCase().includes(q) ?? false)
      )
      .slice(0, 10);
  }, [busqueda, tiendas]);

  const seleccionada = useMemo(() => {
    return tiendas.find((t) => t.id === valor) ?? (reciente?.id === valor ? reciente : null);
  }, [reciente, tiendas, valor]);

  return (
    <fieldset className="space-y-2.5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <legend className="px-1 text-sm font-bold text-slate-900">1. ¿En qué tienda estás?</legend>

      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            aria-hidden="true"
          />
          <label htmlFor="buscar-tienda-reporte" className="sr-only">
            Buscar tienda por nombre o barrio
          </label>
          <input
            id="buscar-tienda-reporte"
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar tienda, supermercado o barrio..."
            className="min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 pl-9 pr-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
          />
        </div>

        <button
          type="button"
          onClick={buscarPorGps}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-emerald-700 bg-emerald-50 px-3.5 text-sm font-semibold text-emerald-900 hover:bg-emerald-100"
        >
          <Navigation className="h-4 w-4" aria-hidden="true" />
          <span>Cercanas (GPS)</span>
        </button>
      </div>

      {gpsEstado && (
        <output className="block text-xs font-medium text-emerald-800">
          {gpsEstado}
        </output>
      )}

      {seleccionada && (
        <div className="flex items-center justify-between rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs text-emerald-950">
          <span className="flex items-center gap-2 font-semibold">
            <Store className="h-4 w-4 text-emerald-700" aria-hidden="true" />
            Seleccionada: {seleccionada.nombre}
          </span>
          {reciente?.id === seleccionada.id && (
            <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-emerald-800">
              Reciente (&lt; 2 h)
            </span>
          )}
        </div>
      )}

      <div role="listbox" aria-label="Tiendas disponibles" className="max-h-52 space-y-1.5 overflow-y-auto">
        <ListaOpcionesTienda
          cargando={cargando}
          tiendas={tiendasFiltradas}
          valor={valor}
          onSeleccionar={onChange}
        />
      </div>
    </fieldset>
  );
}
