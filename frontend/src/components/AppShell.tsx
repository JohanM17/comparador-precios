import React from "react";
import Link from "next/link";
import { PlusCircle, Search } from "lucide-react";

interface AppShellProps {
  readonly children: React.ReactNode;
}

/**
 * Contenedor estructural principal (AppShell) de la aplicacion.
 *
 * Implementa la arquitectura institucional sobria definida en docs/PLAN_CONSTRUCCION.md:
 * - Barra superior fija (h-16) con marca institucional, buscador global y accesos a gestion/ingreso.
 * - Area de contenido principal con margen superior para no solapar la barra fija.
 * - Pie de pagina accesible con enlace legal y atribucion obligatoria ODbL.
 * - Boton flotante de accion (FAB) para reporte rapido mobile-first (min-h-11 para objetivo tactil WCAG).
 */
export default function AppShell({ children }: AppShellProps): React.JSX.Element {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 antialiased">
      {/* Barra superior de navegacion fija */}
      <header
        role="banner"
        className="fixed inset-x-0 top-0 z-40 flex h-16 items-center border-b border-slate-200 bg-white/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-white/80 sm:px-6"
      >
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4">
          {/* Marca / Logotipo */}
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-bold tracking-tight text-emerald-800 transition-colors hover:text-emerald-900"
            aria-label="Ir al inicio - Comparador de Precios"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-700 text-base font-black text-white shadow-sm">
              CP
            </span>
            <span className="hidden sm:inline font-semibold text-slate-900">
              Comparador <span className="text-emerald-700">Precios</span>
            </span>
          </Link>

          {/* Buscador global accesible */}
          <div className="flex-1 max-w-md mx-2">
            <form action="/buscar" method="GET" role="search" className="relative w-full">
              <label htmlFor="buscador-global" className="sr-only">
                Buscar productos o marcas
              </label>
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <Search className="h-4 w-4" aria-hidden="true" />
              </div>
              <input
                id="buscador-global"
                name="q"
                type="search"
                autoComplete="off"
                placeholder="Buscar arroz, leche, aceite..."
                className="w-full rounded-full border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm text-slate-900 placeholder-slate-400 transition-all focus:border-emerald-600 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-600/20"
              />
            </form>
          </div>

          {/* Enlaces de navegacion secundaria */}
          <nav aria-label="Navegacion principal" className="flex items-center gap-2 sm:gap-3">
            <Link
              href="/gestion"
              className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-600"
            >
              Gestion
            </Link>
            <Link
              href="/ingresar"
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-600"
            >
              Ingresar
            </Link>
          </nav>
        </div>
      </header>

      {/* Contenido principal con espaciado superior compensatorio */}
      <main id="contenido-principal" className="flex-1 pt-16">
        {children}
      </main>

      {/* Boton flotante de accion rapida (FAB) mobile-first para reporte */}
      <aside aria-label="Accion rapida de captura de precio">
        <Link
          href="/reportar"
          className="fixed bottom-5 right-5 z-50 flex min-h-11 items-center gap-2 rounded-full bg-emerald-700 px-5 py-3 text-sm font-semibold text-white shadow-lg transition-transform hover:bg-emerald-800 hover:shadow-xl active:scale-95 focus:outline-none focus:ring-4 focus:ring-emerald-600/30"
          aria-label="Registrar o capturar nuevo precio de producto"
        >
          <PlusCircle className="h-5 w-5" aria-hidden="true" />
          <span>Reportar precio</span>
        </Link>
      </aside>

      {/* Pie de pagina institucional */}
      <footer role="contentinfo" className="border-t border-slate-200 bg-white py-8 text-xs text-slate-500">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
          <p className="text-center sm:text-left">
            Plataforma Colaborativa de Comparacion de Precios de la Canasta Familiar &copy;{" "}
            {new Date().getFullYear()}.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <span className="text-slate-400">
              Datos geograficos &copy; OpenStreetMap contribuyentes (ODbL).
            </span>
            <span className="text-slate-400">
              Datos nutricionales Open Food Facts.
            </span>
            <Link
              href="/legal"
              className="font-medium text-slate-700 underline decoration-slate-300 underline-offset-4 hover:text-emerald-700"
            >
              Terminos y Privacidad (Ley 1581)
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
