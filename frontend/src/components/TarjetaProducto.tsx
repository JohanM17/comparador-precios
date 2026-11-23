import React from "react";
import Link from "next/link";
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
 * Renglon del catalogo, enlazado a la pantalla de comparacion del producto (S2).
 *
 * El catalogo es una lista, no una cuadricula de tarjetas: el nombre manda a la
 * izquierda y el precio mas bajo por unidad base cierra a la derecha. La
 * separacion es una linea de un pixel, sin sombras ni bordes redondeados.
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
      className="group flex items-baseline justify-between gap-5 border-t border-slate-200 px-2 py-4 transition-colors hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-600 sm:px-3"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-[17px] font-medium leading-snug tracking-tight text-slate-900 underline decoration-transparent underline-offset-4 transition-colors group-hover:decoration-slate-400">
          {nombre}
        </span>
        <span className="mt-0.5 block text-[13px] text-slate-500">
          {categoriaNombre} ·{" "}
          {nTiendas === 1 ? "1 establecimiento" : `${nTiendas} establecimientos`}
        </span>
      </span>

      {tienePrecio ? (
        <span className="flex-none text-right">
          <span className="cifras block text-[19px] font-medium tracking-tight text-slate-900">
            {formatearPesos(precioDesdePorUnidadCop)}
          </span>
          <span className="mt-0.5 block text-[12.5px] text-slate-500">
            desde, por {unidadVisualizacion}
          </span>
        </span>
      ) : (
        <span className="flex-none text-right text-[13px] text-cereza-600">
          Sin precios vigentes
        </span>
      )}
    </Link>
  );
}
