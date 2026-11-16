import React from "react";

export interface CargandoProps {
  readonly filas?: number;
  readonly etiqueta?: string;
}

/**
 * Esqueleto accesible de carga (Skeleton Loader).
 * Respeta rigurosamente las preferencias del usuario de accesibilidad (prefers-reduced-motion)
 * utilizando clases motion-safe:animate-pulse de Tailwind CSS.
 */
export default function Cargando({
  filas = 4,
  etiqueta = "Cargando contenido...",
}: CargandoProps): React.JSX.Element {
  const elementos = Array.from({ length: Math.max(1, filas) }, (_, i) => i);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={etiqueta}
      className="w-full space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <span className="sr-only">{etiqueta}</span>
      <div className="h-6 w-1/3 rounded bg-slate-200 motion-safe:animate-pulse" />
      <div className="space-y-3 pt-2">
        {elementos.map((indice) => (
          <div
            key={indice}
            className="flex items-center justify-between gap-4 border-b border-slate-100 pb-3 last:border-b-0 last:pb-0"
          >
            <div className="flex-1 space-y-2">
              <div className="h-4 w-3/4 rounded bg-slate-200 motion-safe:animate-pulse" />
              <div className="h-3 w-1/2 rounded bg-slate-100 motion-safe:animate-pulse" />
            </div>
            <div className="h-7 w-20 rounded bg-slate-200 motion-safe:animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
