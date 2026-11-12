import React from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, ShieldCheck, Sparkles, TrendingDown } from "lucide-react";

export default function PaginaInicio(): React.JSX.Element {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Seccion Hero de Bienvenida */}
      <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm sm:p-12 lg:p-16">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 ring-1 ring-inset ring-emerald-600/20">
            <Sparkles className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
            <span>Transparencia comunitaria</span>
          </div>
          <h1 className="mt-4 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl lg:text-5xl">
            Compara precios reales de la canasta familiar en tu barrio
          </h1>
          <p className="mt-4 text-base text-slate-600 sm:text-lg">
            Encuentra los alimentos y productos de aseo mas economicos cerca de ti. Precios
            verificados colaborativamente por vecinos, auditados con algoritmos transparentes
            y sin favoritismos comerciales.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              href="/buscar"
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-700 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2"
            >
              <span>Explorar productos</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link
              href="/reportar"
              className="inline-flex min-h-11 items-center justify-center rounded-xl border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-800 shadow-sm transition-all hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2"
            >
              Reportar un precio
            </Link>
          </div>
        </div>
      </section>

      {/* Pilares de Transparencia y Principios del Sistema */}
      <section aria-labelledby="titulo-pilares" className="mt-12">
        <h2 id="titulo-pilares" className="text-xl font-bold tracking-tight text-slate-900">
          Nuestros principios de confianza
        </h2>
        <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {/* Tarjeta 1: Neutralidad comercial */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
              <TrendingDown className="h-5 w-5" aria-hidden="true" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-slate-900">
              Neutralidad comercial
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Ningun supermercado o marca puede pagar para posicionarse primero. Los precios
              se ordenan estrictamente por costo por unidad base (kg, litro o unidad).
            </p>
          </div>

          {/* Tarjeta 2: Privacidad Ley 1581 */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-slate-900">
              Privacidad por diseno
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Tus coordenadas GPS exactas jamas se almacenan ni registran en logs. Cumplimiento
              riguroso del regimen colombiano de proteccion de datos (Ley 1581 de 2012).
            </p>
          </div>

          {/* Tarjeta 3: Auditoria y confianza */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
              <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-slate-900">
              Sellos de confianza
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Precios validados con fotografias anonimizadas de tiquetes y reputacion
              comunitaria para prevenir especulacion y reportes falsos.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

