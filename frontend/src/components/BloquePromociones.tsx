import React from "react";
import { Megaphone } from "lucide-react";
import type { ItemPromocion } from "@/lib/api/clienteApi";
import { formatearFechaBogota, formatearPesos } from "@/lib/formato";

export interface BloquePromocionesProps {
  readonly promociones: readonly ItemPromocion[];
}

function describirBeneficio(promo: ItemPromocion): string | null {
  if (typeof promo.porcentaje_descuento === "number") {
    return `${promo.porcentaje_descuento}% de descuento`;
  }
  if (typeof promo.precio_especial_cop === "number") {
    return `Precio promocional: ${formatearPesos(promo.precio_especial_cop)} COP`;
  }
  if (typeof promo.pague_x === "number" && typeof promo.lleve_y === "number") {
    return `Pague ${promo.pague_x} y lleve ${promo.lleve_y}`;
  }
  return null;
}

function formatearVigencia(promo: ItemPromocion): string {
  const inicio = promo.vigente_desde
    ? `Desde ${formatearFechaBogota(promo.vigente_desde)}`
    : "Vigente";
  if (promo.hasta_revocar) {
    return `${inicio} · Válido hasta revocar`;
  }
  if (promo.vigente_hasta) {
    return `${inicio} · Hasta ${formatearFechaBogota(promo.vigente_hasta)}`;
  }
  return inicio;
}

/*
 * Contenedor independiente para promociones comerciales (EC-06 y Ley 1480).
 * Retorna null si el producto no tiene promociones activas.
 *
 * Es el unico bloque de la pantalla con marco cerrado: la ley exige que el
 * contenido comercial se distinga del editorial, y ese marco es lo que lo
 * distingue. El beneficio va en azul sobrio, el color reservado al dato que
 * publica un comercio; en esmeralda leeria como ahorro verificado y sesgaria
 * la comparacion, que es justo lo que EC-06 prohibe.
 */
export default function BloquePromociones({
  promociones,
}: BloquePromocionesProps): React.JSX.Element | null {
  if (promociones.length === 0) {
    return null;
  }

  return (
    <section
      aria-labelledby="titulo-bloque-promociones"
      className="mt-12 border border-slate-300 bg-slate-100 px-5 py-4 sm:px-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-300 pb-3">
        <div className="flex items-center gap-2">
          <Megaphone className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
          <h2 id="titulo-bloque-promociones" className="rotulo">
            Promoción — Contenido comercial que no altera el ranking
          </h2>
        </div>
        <span className="rotulo border border-slate-300 px-2 py-1">Ley 1480 de 2011</span>
      </div>

      <div className="divide-y divide-slate-300">
        {promociones.map((promo, indice) => {
          const beneficio = describirBeneficio(promo);
          const clave = promo.id ?? `promo-${indice}`;
          return (
            <article key={clave} className="py-4">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h3 className="text-[15px] font-medium tracking-[-0.015em] text-slate-900">
                  {promo.titulo || "Promoción comercial vigente"}
                </h3>
                {beneficio && (
                  <span className="cifras flex-shrink-0 text-[13.5px] font-medium text-blue-700">
                    {beneficio}
                  </span>
                )}
              </div>

              {(promo.establecimiento_nombre || promo.presentacion_etiqueta) && (
                <p className="mt-1 text-[13px] text-slate-600">
                  {[promo.establecimiento_nombre, promo.presentacion_etiqueta]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              )}

              {promo.condiciones && (
                <p className="mt-2 max-w-[62ch] text-[12.5px] leading-relaxed text-slate-600">
                  <span className="text-slate-500">Condiciones:</span> {promo.condiciones}
                </p>
              )}

              <p className="cifras mt-2 text-[12px] text-slate-500">{formatearVigencia(promo)}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

