import React from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import ToggleTema from "@/components/ToggleTema";

interface AppShellProps {
  readonly children: React.ReactNode;
}

/** Marca: dos circulos que se cruzan (dos precios frente a frente). */
function MarcaComparador(): React.JSX.Element {
  return (
    <svg viewBox="0 0 40 40" className="h-9 w-9" aria-hidden="true">
      <circle cx="15" cy="20" r="11" fill="#e7ece5" />
      <circle cx="26" cy="20" r="11" fill="#dc4234" />
      <path d="M20.5 11.2a11 11 0 0 1 0 17.6 11 11 0 0 1 0-17.6Z" fill="#9f2520" />
    </svg>
  );
}

/**
 * Contenedor estructural principal (AppShell) de la aplicacion.
 *
 * - Barra superior fija (h-16) en verde de cafetal, con marca, buscador global y accesos.
 * - Area de contenido principal con margen superior para no solapar la barra fija.
 * - Pie de pagina accesible con enlace legal y atribucion obligatoria ODbL.
 * - Boton flotante de accion (FAB) para reporte rapido mobile-first (min-h-11, objetivo tactil WCAG).
 */
export default function AppShell({ children }: AppShellProps): React.JSX.Element {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 antialiased">
      <header
        role="banner"
        className="fixed inset-x-0 top-0 z-40 flex h-16 items-center bg-bosque-900 px-4 sm:px-6"
      >
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4">
          <Link
            href="/"
            className="flex items-center gap-2.5 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-miel-300"
          >
            <MarcaComparador />
            <span className="hidden font-display text-lg font-semibold tracking-tight text-white sm:inline">
              Comparador <span className="text-miel-300">Precios</span>
            </span>
            <span className="sr-only">Comparador de Precios - Ir al inicio</span>
          </Link>

          <div className="mx-2 max-w-md flex-1">
            <form action="/" method="GET" role="search" className="relative w-full">
              <label htmlFor="buscador-global" className="sr-only">
                Buscar productos o marcas
              </label>
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-bosque-200">
                <Search className="h-4 w-4" aria-hidden="true" />
              </div>
              <input
                id="buscador-global"
                name="q"
                type="search"
                autoComplete="off"
                placeholder="Buscar arroz, leche, aceite..."
                className="w-full rounded-full border border-white/15 bg-white/10 py-2 pl-9 pr-4 text-sm text-white placeholder-bosque-200 transition-colors focus:border-miel-300 focus:bg-white/15 focus:outline-none focus:ring-2 focus:ring-miel-300/40"
              />
            </form>
          </div>

          <nav aria-label="Navegacion principal" className="flex items-center gap-1 sm:gap-2">
            <ToggleTema />
            <Link
              href="/gestion"
              className="rounded-lg px-3 py-2 text-sm font-medium text-bosque-100 transition-colors hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-miel-300"
            >
              Gestion
            </Link>
            <Link
              href="/ingresar"
              className="rounded-lg bg-white px-3.5 py-2 text-sm font-semibold text-bosque-900 transition-colors hover:bg-miel-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-miel-300"
            >
              Ingresar
            </Link>
          </nav>
        </div>
      </header>

      <main id="contenido-principal" className="flex-1 pt-16">
        {children}
      </main>

      <aside aria-label="Accion rapida de captura de precio">
        <Link
          href="/reportar"
          className="fixed bottom-5 right-5 z-50 flex min-h-11 items-center gap-2 rounded-full bg-brasa-700 py-3 pl-4 pr-5 text-sm font-semibold text-white shadow-[0_10px_30px_-8px_rgba(159,37,32,0.7)] transition-all hover:-translate-y-0.5 hover:bg-brasa-600 active:translate-y-0 focus:outline-none focus-visible:ring-4 focus-visible:ring-brasa-400/40"
          aria-label="Reportar precio de producto"
        >
          <Plus className="h-5 w-5" strokeWidth={2.5} aria-hidden="true" />
          <span>Reportar precio</span>
        </Link>
      </aside>

      <footer role="contentinfo" className="bg-bosque-950 pb-24 pt-10 text-xs text-bosque-100">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-6 px-4 sm:flex-row sm:px-6">
          <div className="max-w-sm">
            <p className="font-display text-base font-semibold text-white">Comparador Precios</p>
            <p className="mt-1 leading-relaxed">
              Plataforma colaborativa de comparacion de precios de la canasta familiar &copy;{" "}
              {new Date().getFullYear()}. Armenia, Quindio.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:items-end">
            <span>Datos geograficos &copy; OpenStreetMap contribuyentes (ODbL).</span>
            <span>Datos nutricionales Open Food Facts.</span>
            <Link
              href="/legal"
              className="font-medium text-miel-300 underline decoration-miel-300/40 underline-offset-4 hover:text-miel-100"
            >
              Terminos y Privacidad (Ley 1581)
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
