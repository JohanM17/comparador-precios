import React from "react";
import Link from "next/link";
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
    <div data-criterio-orden={criterioOrden}>
      <div
        role="note"
        aria-label="Garantía de neutralidad comercial"
        className="flex flex-col gap-1.5 pb-7 text-[13.5px] leading-relaxed text-slate-600 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6"
      >
        <p className="max-w-[62ch]">{textoNeutralidad}</p>
        <Link
          href="/legal#neutralidad"
          className="flex-shrink-0 text-slate-600 underline decoration-slate-300 underline-offset-4 transition-colors hover:text-slate-900 hover:decoration-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
        >
          Ver criterio de neutralidad
        </Link>
      </div>

      {bloquePrincipal.length > 0 && (
        <section aria-label="Precios vigentes confiables" className="border-b border-slate-200">
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
        <section aria-labelledby="titulo-bloque-secundario" className="mt-12">
          <h2 id="titulo-bloque-secundario" className="rotulo mb-1.5">
            Fuera de la comparación: precios desactualizados o en revisión
          </h2>
          <p className="mb-4 max-w-[58ch] text-[13.5px] text-slate-500">
            Se muestran para que nada quede oculto, pero no compiten por el primer lugar.
          </p>
          <div className="border-b border-slate-200">
            {bloqueSecundario.map((item) => (
              <FilaPrecio
                key={`${item.establecimiento.id}-${item.presentacion.id}`}
                item={item}
                productoId={productoId}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
