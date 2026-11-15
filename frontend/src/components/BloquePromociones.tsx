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

/**
 * Contenedor independiente para promociones comerciales (EC-06 y Ley 1480).
 * Retorna null si el producto no tiene promociones activas.
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
      className="mt-8 rounded-2xl border border-slate-300 bg-slate-100/80 p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <Megaphone className="h-4 w-4 text-slate-700" aria-hidden="true" />
          <h2 id="titulo-bloque-promociones" className="text-sm font-bold text-slate-900">
            Promoción — Contenido comercial que no altera el ranking
          </h2>
        </div>
        <span className="rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-xs font-semibold text-slate-700">
          Ley 1480 de 2011
        </span>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        {promociones.map((promo, indice) => {
          const beneficio = describirBeneficio(promo);
          const clave = promo.id ?? `promo-${indice}`;
          return (
            <article
              key={clave}
              className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-bold text-slate-900">
                  {promo.titulo || "Promoción comercial vigente"}
                </h3>
                {beneficio && (
                  <span className="flex-shrink-0 rounded-md bg-blue-50 px-2 py-0.5 text-xs font-bold text-blue-900">
                    {beneficio}
                  </span>
                )}
              </div>

              {(promo.establecimiento_nombre || promo.presentacion_etiqueta) && (
                <p className="mt-1 text-xs font-medium text-slate-700">
                  {[promo.establecimiento_nombre, promo.presentacion_etiqueta]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              )}

              {promo.condiciones && (
                <p className="mt-2 text-xs text-slate-600">
                  <strong>Condiciones:</strong> {promo.condiciones}
                </p>
              )}

              <p className="mt-2 text-[11px] text-slate-500">
                {promo.vigente_desde ? `Desde ${formatearFechaBogota(promo.vigente_desde)}` : "Vigente"}
                {promo.hasta_revocar
                  ? " · Válido hasta revocar"
                  : promo.vigente_hasta
                  ? ` · Hasta ${formatearFechaBogota(promo.vigente_hasta)}`
                  : ""}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

