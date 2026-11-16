"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw, UploadCloud, WifiOff } from "lucide-react";

async function contarReportesPendientes(): Promise<number> {
  if (typeof window === "undefined" || !("indexedDB" in window)) {
    return 0;
  }
  return new Promise((resolver) => {
    try {
      const solicitud = window.indexedDB.open("comparador_precios_offline");
      solicitud.onerror = () => resolver(0);
      solicitud.onupgradeneeded = () => {
        // Si la base aun no existia, cerramos sin crear stores vacios inesperados
        solicitud.transaction?.abort();
        resolver(0);
      };
      solicitud.onsuccess = () => {
        const db = solicitud.result;
        if (!db.objectStoreNames.contains("cola_reportes")) {
          db.close();
          resolver(0);
          return;
        }
        const tx = db.transaction("cola_reportes", "readonly");
        const conteo = tx.objectStore("cola_reportes").count();
        conteo.onsuccess = () => {
          db.close();
          resolver(conteo.result);
        };
        conteo.onerror = () => {
          db.close();
          resolver(0);
        };
      };
    } catch {
      resolver(0);
    }
  });
}

/**
 * Vista /offline para navegacion sin internet con acceso a la cola local de reportes.
 */
export default function PaginaOffline(): React.JSX.Element {
  const [pendientes, setPendientes] = useState<number>(0);

  useEffect(() => {
    void contarReportesPendientes().then(setPendientes);
  }, []);

  const etiquetaUnidad = pendientes === 1 ? "reporte pendiente" : "reportes pendientes";
  const textoPendientes =
    pendientes === 0
      ? "No hay reportes pendientes por sincronizar"
      : `${pendientes} ${etiquetaUnidad} en cola local`;

  return (
    <div className="mx-auto max-w-xl px-4 py-10 sm:px-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm sm:p-8">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-amber-50 text-amber-800">
          <WifiOff className="h-7 w-7" aria-hidden="true" />
        </div>

        <h1 className="mt-4 text-2xl font-bold text-slate-900">Estás sin conexión a internet</h1>
        <p className="mt-2 text-sm text-slate-600">
          Puedes seguir capturando precios en campo desde la pantalla de reporte; se guardarán de
          forma segura en tu dispositivo y se enviarán cuando recuperes la señal.
        </p>

        <output className="mt-5 flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-800">
          <UploadCloud className="h-4 w-4 text-emerald-700" aria-hidden="true" />
          <span>{textoPendientes}</span>
        </output>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/reportar"
            className="inline-flex min-h-11 flex-1 items-center justify-center rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800"
          >
            Ir a reportar offline
          </Link>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Reintentar conexión
          </button>
        </div>

        <div className="mt-5 flex justify-center gap-4 text-xs font-medium text-slate-600">
          <Link href="/" className="underline underline-offset-4 hover:text-emerald-800">
            Volver al inicio
          </Link>
          <Link href="/legal" className="underline underline-offset-4 hover:text-emerald-800">
            Transparencia y Privacidad
          </Link>
        </div>
      </section>
    </div>
  );
}

