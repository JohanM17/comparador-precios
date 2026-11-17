import React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
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
 * Casilla del tablon de precios, enlazada a la pantalla de comparacion del producto (S2).
 * El precio por unidad base es el protagonista; el resto es contexto.
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
      className="group relative flex min-h-[200px] flex-col justify-between bg-superficie p-5 transition-colors duration-200 hover:bg-bosque-900 focus:outline-none focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cereza-600"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 transition-colors group-hover:text-bosque-200">
          {categoriaNombre}
        </span>
        <ArrowUpRight
          className="h-5 w-5 flex-shrink-0 text-slate-400 transition-all duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-miel-300"
          aria-hidden="true"
        />
      </div>

      <div>
        <h3 className="font-display text-xl font-semibold leading-tight tracking-tight text-slate-900 transition-colors group-hover:text-white">
          {nombre}
        </h3>

        {tienePrecio ? (
          <p className="mt-3 flex flex-wrap items-baseline gap-x-1.5">
            <span className="text-xs font-medium text-slate-600 transition-colors group-hover:text-bosque-200">
              Desde
            </span>
            <span className="cifras font-display text-3xl font-bold tracking-tight text-emerald-800 transition-colors group-hover:text-miel-300">
              {formatearPesos(precioDesdePorUnidadCop)}
            </span>
            <span className="text-sm font-medium text-slate-700 transition-colors group-hover:text-bosque-100">
              por {unidadVisualizacion}
            </span>
          </p>
        ) : (
          <p className="mt-3 text-sm font-semibold text-cereza-700 transition-colors group-hover:text-miel-300">
            Sin precios vigentes. Sé el primero.
          </p>
        )}

        <p className="mt-2 text-xs font-medium text-slate-600 transition-colors group-hover:text-bosque-200">
          En {nTiendas} establecimientos
        </p>
      </div>
    </Link>
  );
}
