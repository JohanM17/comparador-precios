import React from "react";
import Link from "next/link";
import { ArrowUpRight, Store } from "lucide-react";
import { formatearPesos } from "@/lib/formato";

export interface TarjetaProductoProps {
  readonly id: string;
  readonly nombre: string;
  readonly categoriaNombre: string;
  readonly precioDesdePorUnidadCop: number | null;
  readonly unidadVisualizacion: string;
  readonly nTiendas: number;
}

/**
 * Tarjeta de vitrina enlazada a la pantalla de comparacion del producto (S2).
 */
export default function TarjetaProducto({
  id,
  nombre,
  categoriaNombre,
  precioDesdePorUnidadCop,
  unidadVisualizacion,
  nTiendas,
}: TarjetaProductoProps): React.JSX.Element {
  const tienePrecio = precioDesdePorUnidadCop !== null;

  return (
    <Link
      href={`/producto/${id}`}
      className="group flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-emerald-600/50 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-emerald-700 focus:ring-offset-2"
    >
      <div>
        <div className="flex items-start justify-between gap-2">
          <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-800">
            {categoriaNombre}
          </span>
          <ArrowUpRight
            className="h-4 w-4 flex-shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-emerald-700"
            aria-hidden="true"
          />
        </div>

        <h3 className="mt-3 text-base font-semibold leading-snug text-slate-900 group-hover:text-emerald-800">
          {nombre}
        </h3>
      </div>

      <div className="mt-4 border-t border-slate-100 pt-3">
        {tienePrecio ? (
          <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-bold text-emerald-900">
            Desde {formatearPesos(precioDesdePorUnidadCop)} por {unidadVisualizacion}
          </p>
        ) : (
          <p className="rounded-lg bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700">
            Sin precios vigentes — ¡Sé el primero!
          </p>
        )}

        <p className="mt-2.5 flex items-center gap-1.5 text-xs font-medium text-slate-600">
          <Store className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
          <span>En {nTiendas} establecimientos</span>
        </p>
      </div>
    </Link>
  );
}

