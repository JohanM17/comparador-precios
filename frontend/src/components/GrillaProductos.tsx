import React from "react";
import { Loader2 } from "lucide-react";
import type { ProductoResumen } from "@/lib/api/clienteApi";
import TarjetaProducto from "@/components/TarjetaProducto";

export interface GrillaProductosProps {
  readonly productos: readonly ProductoResumen[];
  readonly categoriasPorId?: Readonly<Record<number, string>>;
  readonly siguienteCursor: string | null;
  readonly cargandoMas?: boolean;
  readonly onCargarMas: () => void;
}

/**
 * Cuadricula responsive de tarjetas de productos con paginacion por cursor.
 */
export default function GrillaProductos({
  productos,
  categoriasPorId = {},
  siguienteCursor,
  cargandoMas = false,
  onCargarMas,
}: GrillaProductosProps): React.JSX.Element {
  return (
    <div className="space-y-8">
      <div className="overflow-hidden rounded-2xl border border-slate-300 bg-superficie">
        <div className="-mb-px -mr-px grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 [&>a]:border-b [&>a]:border-r [&>a]:border-slate-300">
        {productos.map((producto) => (
          <TarjetaProducto
            key={producto.id}
            id={producto.id}
            nombre={producto.nombre}
            categoriaNombre={categoriasPorId[producto.categoria_id] ?? "Canasta familiar"}
            precioDesdePorUnidadCop={producto.precio_desde_por_unidad_cop ?? null}
            unidadVisualizacion={producto.unidad_visualizacion}
            nTiendas={producto.n_tiendas_con_precio}
          />
        ))}
        </div>
      </div>

      {siguienteCursor && (
        <div className="flex justify-center pt-2">
          <button
            type="button"
            onClick={onCargarMas}
            disabled={cargandoMas}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-bosque-800 px-7 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-bosque-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {cargandoMas && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            <span>{cargandoMas ? "Cargando productos..." : "Cargar más productos"}</span>
          </button>
        </div>
      )}
    </div>
  );
}

