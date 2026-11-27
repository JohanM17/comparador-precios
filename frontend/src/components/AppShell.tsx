import React from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import BotonCaptura from "@/components/BotonCaptura";
import Marca from "@/components/Marca";
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
 * - Barra superior pegajosa con el simbolo y el nombre, buscador global y accesos.
 * - Boton flotante de captura rapida, que se oculta solo donde estorbaria
 *   (ver `BotonCaptura`).
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
            className="flex items-center gap-2.5 text-[15px] font-semibold tracking-tight text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50"
          >
            {/*
              Decorativo: el nombre va escrito justo al lado. Va con contorno y
              no macizo porque en tinta el nivel verde se perderia contra el
              propio simbolo, y el nivel es lo unico que la marca mide.
            */}
            <Marca className="h-[26px] w-[26px] shrink-0" />
            <span className="font-cursiva text-[23px] font-normal italic tracking-normal">
              Quimbaya
            </span>
            <span className="sr-only">
              {" "}
              — precios de la canasta en Armenia y Quindío, ir al inicio
            </span>
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
                className="w-full border-0 border-b border-slate-300 bg-transparent py-1.5 pl-6 pr-2 text-sm text-slate-900 placeholder-slate-500 transition-colors focus:border-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
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

      <BotonCaptura />

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
