import React, { Suspense } from "react";
import Cargando from "@/components/Cargando";
import FormularioReportar from "@/components/FormularioReportar";

/**
 * Pantalla S4 (/reportar): captura rapida de precios frente a la gondola (EC-01 <= 15 s).
 */
export default function PaginaReportar(): React.JSX.Element {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
          <Cargando filas={4} etiqueta="Cargando formulario rápido de reporte..." />
        </div>
      }
    >
      <FormularioReportar />
    </Suspense>
  );
}

