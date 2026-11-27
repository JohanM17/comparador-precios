import React from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import ToggleTema from "@/components/ToggleTema";

interface AppShellProps {
  readonly children: React.ReactNode;
}

/**
 * Contenedor estructural principal (AppShell).
 *
 * El armazon aporta lo minimo: una barra superior sobre papel separada por una
 * linea de un pixel, el area de contenido y un pie discreto. No hay franja de
 * color ni sombras, la jerarquia la pone la tipografia.
 *
 * - Barra superior pegajosa con marca, buscador global y accesos.
 * - Boton flotante de captura rapida (min-h-11, objetivo tactil WCAG 2.2 AA).
 * - Pie con enlace legal y atribucion obligatoria ODbL.
 */
export default function AppShell({ children }: AppShellProps): React.JSX.Element {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 antialiased">
      <header
        role="banner"
        className="sticky top-0 z-40 border-b border-slate-200 bg-slate-50/90 backdrop-blur"
      >
        <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-5 py-3.5 sm:px-6">
          <Link
            href="/"
            className="text-[15px] font-semibold tracking-tight text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
          >
            La canasta de{" "}
            <span className="font-cursiva text-[19px] font-normal italic tracking-normal">
              Armenia
            </span>
            <span className="sr-only"> — Comparador de precios, ir al inicio</span>
          </Link>

          <div className="order-last w-full sm:order-none sm:w-auto sm:max-w-xs sm:flex-1">
            <form action="/" method="GET" role="search" className="relative">
              <label htmlFor="buscador-global" className="sr-only">
                Buscar productos o marcas
              </label>
              <Search
                className="pointer-events-none absolute left-0 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
                aria-hidden="true"
              />
              <input
                id="buscador-global"
                name="q"
                type="search"
                autoComplete="off"
                placeholder="Buscar arroz, leche, aceite…"
                className="w-full border-0 border-b border-slate-300 bg-transparent py-1.5 pl-6 pr-2 text-sm text-slate-900 placeholder-slate-500 transition-colors focus:border-slate-900 focus:outline-none focus:ring-0"
              />
            </form>
          </div>

          <nav aria-label="Navegacion principal" className="flex items-center gap-1">
            <ToggleTema />
            <Link
              href="/gestion"
              className="rounded px-2.5 py-1.5 text-sm text-slate-600 transition-colors hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
            >
              Gestión
            </Link>
            <Link
              href="/ingresar"
              className="rounded px-2.5 py-1.5 text-sm font-medium text-slate-900 underline decoration-slate-300 underline-offset-4 transition-colors hover:decoration-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
            >
              Ingresar
            </Link>
          </nav>
        </div>
      </header>

      <main id="contenido-principal" className="flex-1">
        {children}
      </main>

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

      <footer
        role="contentinfo"
        className="mt-16 border-t border-slate-200 pb-28 pt-10 text-[13px] leading-relaxed text-slate-500"
      >
        <div className="mx-auto flex max-w-5xl flex-col justify-between gap-6 px-5 sm:flex-row sm:px-6">
          <p className="max-w-sm">
            El orden de la comparación responde únicamente a los criterios que aparecen en
            pantalla. Ninguna relación comercial lo altera. Armenia, Quindío &copy;{" "}
            {new Date().getFullYear()}.
          </p>
          <div className="flex flex-col gap-1.5 sm:items-end">
            <span>Datos geográficos &copy; OpenStreetMap contribuyentes (ODbL).</span>
            <span>Datos nutricionales Open Food Facts.</span>
            <Link
              href="/legal"
              className="text-slate-600 underline decoration-slate-300 underline-offset-4 transition-colors hover:text-slate-900 hover:decoration-slate-900"
            >
              Términos y Privacidad (Ley 1581)
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
