import React from "react";
import Link from "next/link";
import { AlertCircle, ShieldCheck } from "lucide-react";
import type { ItemComparacion } from "@/lib/api/clienteApi";
import FilaPrecio from "@/components/FilaPrecio";

export interface ListaPreciosProps {
  readonly resultados: readonly ItemComparacion[];
  readonly textoNeutralidad: string;
  readonly criterioOrden: string;
  readonly productoId: string;
}

/**
 * Renderiza el aviso obligatorio de neutralidad y los dos bloques devueltos por FastAPI
 * sin alterar en el cliente el orden entregado por el servidor.
 */
export default function ListaPrecios({
  resultados,
  textoNeutralidad,
  criterioOrden,
  productoId,
}: ListaPreciosProps): React.JSX.Element {
  const bloquePrincipal = resultados.filter((item) => !item.es_bloque_secundario);
  const bloqueSecundario = resultados.filter((item) => item.es_bloque_secundario);

  return (
    <div data-criterio-orden={criterioOrden} className="space-y-8">
      <div
        role="note"
        aria-label="Garantía de neutralidad comercial"
        className="flex flex-col justify-between gap-2 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-950 sm:flex-row sm:items-center"
      >
        <div className="flex items-start gap-2.5 sm:items-center">
          <ShieldCheck className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-800 sm:mt-0" aria-hidden="true" />
          <p className="font-medium">{textoNeutralidad}</p>
        </div>
        <Link
          href="/legal#neutralidad"
          className="flex-shrink-0 text-xs font-semibold text-emerald-900 underline decoration-emerald-600 underline-offset-4 hover:text-cereza-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700"
        >
          Ver criterio de neutralidad
        </Link>
      </div>

      {bloquePrincipal.length > 0 && (
        <section aria-label="Precios vigentes confiables" className="space-y-5 pt-2">
          {bloquePrincipal.map((item, indice) => (
            <FilaPrecio
              key={`${item.establecimiento.id}-${item.presentacion.id}`}
              item={item}
              productoId={productoId}
              posicion={indice + 1}
              destacada={indice === 0 && criterioOrden === "precio_unitario"}
            />
          ))}
        </section>
      )}

      {bloqueSecundario.length > 0 && (
        <section aria-labelledby="titulo-bloque-secundario" className="space-y-3 pt-2">
          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-slate-400" aria-hidden="true" />
            <h2
              id="titulo-bloque-secundario"
              className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.14em] text-slate-700"
            >
              <AlertCircle className="h-3.5 w-3.5 text-slate-600" aria-hidden="true" />
              Precios desactualizados o en revisión
            </h2>
            <div className="h-px flex-1 bg-slate-300" aria-hidden="true" />
          </div>

          {bloqueSecundario.map((item) => (
            <FilaPrecio
              key={`${item.establecimiento.id}-${item.presentacion.id}`}
              item={item}
              productoId={productoId}
            />
          ))}
        </section>
      )}
    </div>
  );
}

