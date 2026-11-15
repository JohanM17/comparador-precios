"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Clock, Package, PlusCircle, Search } from "lucide-react";
import { clienteApi, type ProductoResumen } from "@/lib/api/clienteApi";
import { clienteReportes } from "@/lib/api/clienteReportes";
import {
  guardarCachePresentaciones,
  leerCachePresentaciones,
  leerPresentacionesRecientes,
  type PresentacionOpcion,
} from "@/lib/offline/cacheSelectores";
import ModalSugerirPresentacion from "@/components/ModalSugerirPresentacion";

export type { PresentacionOpcion };

export interface SelectorPresentacionProps {
  readonly valor: string;
  readonly onChange: (id: string, opcion?: PresentacionOpcion) => void;
  readonly recientesIds?: readonly string[];
}

function ListaOpcionesPresentacion({
  cargando,
  opciones,
  valor,
  onSeleccionar,
}: {
  readonly cargando: boolean;
  readonly opciones: readonly PresentacionOpcion[];
  readonly valor: string;
  readonly onSeleccionar: (id: string, op: PresentacionOpcion) => void;
}): React.JSX.Element {
  if (cargando && opciones.length === 0) {
    return <p className="py-2 text-xs text-slate-500">Buscando presentaciones...</p>;
  }
  if (opciones.length === 0) {
    return <p className="py-2 text-xs text-slate-500">No encontramos coincidencias. Puedes sugerir una presentación nueva arriba.</p>;
  }
  return (
    <>
      {opciones.map((op) => {
        const activa = op.id === valor;
        return (
          <button
            key={op.id}
            type="button"
            role="option"
            aria-selected={activa}
            onClick={() => onSeleccionar(op.id, op)}
            className={`flex min-h-11 w-full items-center justify-between gap-2 rounded-xl border px-3 py-2 text-left transition-colors ${
              activa ? "border-emerald-700 bg-emerald-700 text-white" : "border-slate-200 bg-white text-slate-900 hover:bg-slate-50"
            }`}
          >
            <span className="text-sm font-semibold">{op.etiqueta}</span>
            <span className={`text-xs ${activa ? "text-emerald-100" : "text-slate-500"}`}>{op.productoNombre}</span>
          </button>
        );
      })}
    </>
  );
}

/**
 * Control tactil (min-h-11) de busqueda de presentacion con las 5 recientes arriba
 * y enlace a modal de sugerencia de presentacion faltante.
 */
export default function SelectorPresentacion({
  valor,
  onChange,
  recientesIds = [],
}: SelectorPresentacionProps): React.JSX.Element {
  const [busqueda, setBusqueda] = useState("");
  const [recientes, setRecientes] = useState<PresentacionOpcion[]>([]);
  const [resultados, setResultados] = useState<PresentacionOpcion[]>([]);
  const [productosBase, setProductosBase] = useState<ProductoResumen[]>([]);
  const [cargando, setCargando] = useState(false);
  const [modalAbierto, setModalAbierto] = useState(false);

  const cargarOpciones = useCallback(async (termino: string) => {
    setCargando(true);
    try {
      const lista = await clienteApi.buscarProductos({ q: termino.trim() || null, limite: 6 });
      setProductosBase(lista.datos);
      const detalles = await Promise.all(
        lista.datos.slice(0, 5).map((prod) => clienteReportes.obtenerProductoDetalle(prod.id))
      );
      const opciones: PresentacionOpcion[] = [];
      for (const det of detalles) {
        for (const pres of det.presentaciones ?? []) {
          if (pres.activa) {
            opciones.push({ id: pres.id, etiqueta: pres.etiqueta, productoNombre: det.nombre, marca: pres.marca });
          }
        }
      }
      setResultados(opciones);
      guardarCachePresentaciones(opciones);
    } catch {
      setResultados(leerCachePresentaciones());
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => setRecientes(leerPresentacionesRecientes()), []);
  useEffect(() => {
    const timer = window.setTimeout(() => void cargarOpciones(busqueda), 200);
    return () => window.clearTimeout(timer);
  }, [busqueda, cargarOpciones]);

  const recientesPriorizadas = useMemo(() => {
    if (recientesIds.length === 0) return recientes.slice(0, 5);
    const mapa = new Map<string, PresentacionOpcion>();
    for (const item of [...recientes, ...resultados]) mapa.set(item.id, item);
    const porIds = recientesIds.map((id) => mapa.get(id)).filter((item): item is PresentacionOpcion => Boolean(item));
    return (porIds.length > 0 ? porIds : recientes).slice(0, 5);
  }, [recientes, recientesIds, resultados]);

  const catalogoVisible = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    const filtrados = q
      ? resultados.filter((r) => r.etiqueta.toLowerCase().includes(q) || r.productoNombre.toLowerCase().includes(q))
      : resultados;
    return filtrados.slice(0, 10);
  }, [busqueda, resultados]);

  const seleccionada = useMemo(
    () => [...recientesPriorizadas, ...resultados].find((o) => o.id === valor) ?? null,
    [recientesPriorizadas, resultados, valor]
  );

  return (
    <fieldset className="space-y-2.5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <legend className="px-1 text-sm font-bold text-slate-900">2. ¿Qué presentación reportas?</legend>
        <button
          type="button"
          onClick={() => setModalAbierto(true)}
          className="inline-flex min-h-11 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-emerald-800 underline underline-offset-4 hover:text-emerald-950"
        >
          <PlusCircle className="h-3.5 w-3.5" aria-hidden="true" />
          Sugerir presentación faltante
        </button>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
        <label htmlFor="buscar-presentacion-reporte" className="sr-only">
          Buscar producto o presentación
        </label>
        <input
          id="buscar-presentacion-reporte"
          type="search"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Ej. Arroz Diana 500 g, leche 1L, aceite..."
          className="min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 pl-9 pr-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
        />
      </div>

      {seleccionada && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-950">
          <Package className="h-4 w-4 text-emerald-700" aria-hidden="true" />
          <span>Seleccionada: {seleccionada.etiqueta}</span>
        </div>
      )}

      {recientesPriorizadas.length > 0 && (
        <div className="space-y-1">
          <p className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            <Clock className="h-3 w-3" aria-hidden="true" />
            Recientes
          </p>
          <div className="flex flex-wrap gap-1.5">
            {recientesPriorizadas.map((op) => {
              const activa = op.id === valor;
              return (
                <button
                  key={`rec-${op.id}`}
                  type="button"
                  onClick={() => onChange(op.id, op)}
                  className={`min-h-11 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors ${
                    activa ? "border-emerald-700 bg-emerald-700 text-white" : "border-slate-200 bg-slate-50 text-slate-800 hover:bg-slate-100"
                  }`}
                >
                  {op.etiqueta}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div role="listbox" aria-label="Presentaciones disponibles" className="max-h-48 space-y-1.5 overflow-y-auto">
        <ListaOpcionesPresentacion
          cargando={cargando}
          opciones={catalogoVisible}
          valor={valor}
          onSeleccionar={onChange}
        />
      </div>

      <ModalSugerirPresentacion abierto={modalAbierto} productosIniciales={productosBase} onCerrar={() => setModalAbierto(false)} />
    </fieldset>
  );
}
