import React from "react";
import ComparadorProducto from "@/components/ComparadorProducto";

interface PaginaProductoProps {
  readonly params: {
    readonly id: string;
  };
}

export default function PaginaProducto({ params }: PaginaProductoProps): React.JSX.Element {
  return <ComparadorProducto productoId={params.id} />;
}

