import React from "react";
import ComparadorProducto from "@/components/ComparadorProducto";

interface PaginaProductoProps {
  readonly params: {
    readonly id: string;
  };
  readonly searchParams?: {
    readonly presentacion?: string | string[];
  };
}

export default function PaginaProducto({
  params,
  searchParams,
}: PaginaProductoProps): React.JSX.Element {
  const presentacion =
    typeof searchParams?.presentacion === "string" ? searchParams.presentacion : null;
  return <ComparadorProducto productoId={params.id} presentacionInicial={presentacion} />;
}

