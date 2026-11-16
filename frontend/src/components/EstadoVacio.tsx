import React from "react";
import Link from "next/link";
import { Inbox } from "lucide-react";

export interface EstadoVacioProps {
  readonly titulo: string;
  readonly descripcion: string;
  readonly accionTexto?: string;
  readonly accionHref?: string;
  readonly icono?: React.ReactNode;
}

/**
 * Componente accesible para indicar ausencia de resultados o coleccion vacia.
 */
export default function EstadoVacio({
  titulo,
  descripcion,
  accionTexto,
  accionHref,
  icono,
}: EstadoVacioProps): React.JSX.Element {
  return (
    <section
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center sm:p-12"
    >
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        {icono ?? <Inbox className="h-7 w-7 stroke-[1.5]" aria-hidden="true" />}
      </div>
      <h3 className="text-base font-semibold text-slate-900">{titulo}</h3>
      <p className="mt-1 max-w-md text-sm text-slate-500">{descripcion}</p>
      {accionTexto && accionHref && (
        <div className="mt-6">
          <Link
            href={accionHref}
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2"
          >
            {accionTexto}
          </Link>
        </div>
      )}
    </section>
  );
}
