import React from "react";
import { Info } from "lucide-react";

export interface AvisoDatosDemoProps {
  readonly visible: boolean;
}

/**
 * Banda informativa superior cuando se muestran datos semilla o de demostracion.
 */
export default function AvisoDatosDemo({
  visible,
}: AvisoDatosDemoProps): React.JSX.Element | null {
  if (!visible) {
    return null;
  }

  return (
    <div
      role="region"
      aria-label="Aviso de datos de demostración"
      className="border-b border-amber-300 bg-amber-50 px-4 py-3 text-amber-950"
    >
      <div className="mx-auto flex max-w-7xl items-start gap-3 sm:items-center">
        <Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-800 sm:mt-0" aria-hidden="true" />
        <p className="text-sm font-medium leading-snug">
          Aviso: Algunos precios mostrados corresponden a datos iniciales de demostración mientras la
          comunidad completa reportes vigentes en tu zona.
        </p>
      </div>
    </div>
  );
}

