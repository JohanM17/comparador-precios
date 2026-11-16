"use client";

import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Cargando from "@/components/Cargando";
import EstadoVacio from "@/components/EstadoVacio";

export interface ColumnaTablaGestion<T> {
  readonly clave: string;
  readonly encabezado: string;
  readonly celda: (fila: T) => React.ReactNode;
  readonly clase?: string;
}

export interface TablaGestionProps<T> {
  readonly columnas: readonly ColumnaTablaGestion<T>[];
  readonly datos: readonly T[];
  readonly cargando: boolean;
  readonly vacioTexto: string;
  readonly vacioDescripcion?: string;
  readonly siguienteCursor?: string | boolean | null;
  readonly onSiguiente?: () => void;
  readonly tieneAnterior?: boolean;
  readonly onAnterior?: () => void;
  readonly claveFila?: (fila: T, indice: number) => string;
  readonly etiquetaTabla?: string;
}

/**
 * Tabla paginada reutilizable y accesible para todas las pestanas de S6 (/gestion).
 */
export default function TablaGestion<T>({
  columnas,
  datos,
  cargando,
  vacioTexto,
  vacioDescripcion = "No hay registros disponibles con los filtros seleccionados.",
  siguienteCursor,
  onSiguiente,
  tieneAnterior = false,
  onAnterior,
  claveFila,
  etiquetaTabla = "Tabla de gestion",
}: TablaGestionProps<T>): React.JSX.Element {
  if (cargando && datos.length === 0) {
    return <Cargando filas={4} etiqueta="Cargando tabla..." />;
  }

  if (!cargando && datos.length === 0) {
    return <EstadoVacio titulo={vacioTexto} descripcion={vacioDescripcion} />;
  }

  return (
    <div className="space-y-3">
      {/* Vista en tarjetas para pantallas pequenas (evita scroll horizontal en movil) */}
      <ul aria-label={etiquetaTabla} className="space-y-3 md:hidden">
        {datos.map((fila, idx) => {
          const idFila = claveFila ? claveFila(fila, idx) : String(idx);
          return (
            <li
              key={idFila}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <dl className="space-y-2 text-sm">
                {columnas.map((col) => (
                  <div key={col.clave} className="flex flex-col gap-0.5 border-b border-slate-100 pb-1.5 last:border-b-0 last:pb-0">
                    <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      {col.encabezado}
                    </dt>
                    <dd className={`text-slate-800 ${col.clase ?? ""}`}>
                      {col.celda(fila)}
                    </dd>
                  </div>
                ))}
              </dl>
            </li>
          );
        })}
      </ul>

      {/* Vista tabular para escritorio */}
      <section
        aria-label={etiquetaTabla}
        className="hidden overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm md:block"
      >
        <table className="w-full divide-y divide-slate-200 text-left text-sm">
          <caption className="sr-only">{etiquetaTabla}</caption>
          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
            <tr>
              {columnas.map((col) => (
                <th key={col.clave} scope="col" className={`px-4 py-3 ${col.clase ?? ""}`}>
                  {col.encabezado}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white text-slate-800">
            {datos.map((fila, idx) => {
              const idFila = claveFila ? claveFila(fila, idx) : String(idx);
              return (
                <tr key={idFila} className="hover:bg-slate-50/70">
                  {columnas.map((col) => (
                    <td key={col.clave} className={`px-4 py-3 align-top break-words ${col.clase ?? ""}`}>
                      {col.celda(fila)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {(tieneAnterior || Boolean(siguienteCursor)) && (
        <div className="flex items-center justify-end gap-2">
          {tieneAnterior && onAnterior && (
            <button
              type="button"
              onClick={onAnterior}
              disabled={cargando}
              className="inline-flex min-h-11 items-center gap-1 rounded-xl border border-slate-300 bg-white px-4 text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              Anterior
            </button>
          )}
          {Boolean(siguienteCursor) && onSiguiente && (
            <button
              type="button"
              onClick={onSiguiente}
              disabled={cargando}
              className="inline-flex min-h-11 items-center gap-1 rounded-xl border border-slate-300 bg-white px-4 text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50"
            >
              Siguiente
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

