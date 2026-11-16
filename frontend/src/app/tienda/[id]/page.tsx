import React from "react";
import FichaTienda from "@/components/FichaTienda";

interface PaginaTiendaProps {
  readonly params: {
    readonly id: string;
  };
}

export default function PaginaTienda({ params }: PaginaTiendaProps): React.JSX.Element {
  return <FichaTienda establecimientoId={params.id} />;
}

