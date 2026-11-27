"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Plus } from "lucide-react";

/*
 * Rutas donde el botón flotante estorba en vez de ayudar.
 *
 * En `/reportar` el usuario ya está reportando. En `/ingresar` y `/gestion` la
 * pantalla es un formulario largo, y un botón fijo abajo a la derecha se
 * monta encima de los campos: en el modo rápido de precios tapaba uno de los
 * campos de la lista. `/gestion` además ya tiene «Nuevo reporte» en su
 * cabecera.
 */
const RUTAS_SIN_BOTON: readonly string[] = ["/reportar", "/gestion", "/ingresar", "/offline"];

/**
 * Botón flotante de captura rápida (min-h-11, objetivo táctil WCAG 2.2 AA).
 */
export default function BotonCaptura(): React.JSX.Element | null {
  const ruta = usePathname();

  if (RUTAS_SIN_BOTON.some((base) => ruta === base || ruta.startsWith(`${base}/`))) {
    return null;
  }

  return (
    <aside aria-label="Accion rapida de captura de precio">
      <Link
        href="/reportar"
        className="fixed bottom-5 right-5 z-50 inline-flex min-h-11 items-center gap-2 rounded-full bg-slate-900 py-3 pl-4 pr-5 text-sm font-medium text-slate-50 shadow-lg shadow-slate-900/15 transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
        aria-label="Reportar precio de producto"
      >
        <Plus className="h-5 w-5" strokeWidth={2} aria-hidden="true" />
        <span>Reportar precio</span>
      </Link>
    </aside>
  );
}
