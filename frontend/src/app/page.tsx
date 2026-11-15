import React, { Suspense } from "react";
import Cargando from "@/components/Cargando";
import VitrinaInicio from "@/components/VitrinaInicio";

export default function PaginaInicio(): React.JSX.Element {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <Cargando filas={6} etiqueta="Cargando vitrina de inicio..." />
        </div>
      }
    >
      <VitrinaInicio />
    </Suspense>
  );
}
