"use client";

import React, { useCallback, useEffect, useState } from "react";
import { RefreshCw, UploadCloud } from "lucide-react";
import {
  clienteReportes,
  type ElementoReportePropio,
} from "@/lib/api/clienteReportes";
import { obtenerTokenAcceso } from "@/lib/auth/supabase";
import {
  extraerInfoError,
  formatearFechaBogota,
  formatearPesos,
  type InfoErrorVisible,
} from "@/lib/formato";
import {
  listarColaReportes,
  sincronizarColaReportes,
  type ReporteEnCola,
} from "@/lib/offline/colaReportes";
import EstadoError from "@/components/EstadoError";
import TablaGestion, { type ColumnaTablaGestion } from "@/components/TablaGestion";

const ETIQUETA_ESTADO_VISIBLE: Readonly<Record<string, string>> = {
  recibido: "Recibido",
  en_revision: "En revisión",
  rechazado: "Rechazado",
};

const CLASE_ESTADO_VISIBLE: Readonly<Record<string, string>> = {
  recibido: "bg-emerald-50 text-emerald-900 border-emerald-300",
  en_revision: "bg-amber-50 text-amber-900 border-amber-300",
  rechazado: "bg-rose-50 text-rose-900 border-rose-300",
};

const LIMITE = 20;

const COLUMNAS_MIS_REPORTES: readonly ColumnaTablaGestion<ElementoReportePropio>[] = [
  {
    clave: "producto",
    encabezado: "Producto / Presentación",
    celda: (r) => (
      <div>
        <p className="font-semibold text-slate-900">{r.producto_nombre}</p>
        <p className="text-xs text-slate-500">{r.presentacion_etiqueta}</p>
      </div>
    ),
  },
  {
    clave: "tienda",
    encabezado: "Establecimiento",
    celda: (r) => <span className="text-sm">{r.establecimiento_nombre}</span>,
  },
  {
    clave: "precio",
    encabezado: "Precio",
    celda: (r) => (
      <span className="font-bold text-slate-900">{formatearPesos(r.precio_cop)}</span>
    ),
  },
  {
    clave: "estado",
    encabezado: "Estado visible",
    celda: (r) => (
      <span
        className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
          CLASE_ESTADO_VISIBLE[r.estado_visible] ?? "border-slate-300 bg-slate-100 text-slate-700"
        }`}
      >
        {ETIQUETA_ESTADO_VISIBLE[r.estado_visible] ?? r.estado_visible}
      </span>
    ),
  },
  {
    clave: "fecha",
    encabezado: "Observado en",
    celda: (r) => (
      <span className="text-xs text-slate-600">{formatearFechaBogota(r.observado_en)}</span>
    ),
  },
];

export interface PestanaMisReportesProps {
  readonly token: string;
}

/**
 * Pestana Reportante: historial paginado (GET /v1/mis-reportes) + cola offline en IndexedDB.
 */
export default function PestanaMisReportes({
  token,
}: PestanaMisReportesProps): React.JSX.Element {
  const [pagina, setPagina] = useState(1);
  const [reportes, setReportes] = useState<ElementoReportePropio[]>([]);
  const [total, setTotal] = useState(0);
  const [pendientesLocales, setPendientesLocales] = useState<ReporteEnCola[]>([]);
  const [cargando, setCargando] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const [remotos, locales] = await Promise.all([
        clienteReportes.obtenerMisReportes(token, pagina, LIMITE),
        listarColaReportes(),
      ]);
      setReportes(remotos.datos);
      setTotal(remotos.total);
      setPendientesLocales(locales);
    } catch (err) {
      setError(extraerInfoError(err, "No pudimos cargar tu historial de reportes."));
    } finally {
      setCargando(false);
    }
  }, [pagina, token]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const sincronizarAhora = async (): Promise<void> => {
    setSincronizando(true);
    await sincronizarColaReportes(obtenerTokenAcceso, { forzar: true });
    await cargar();
    setSincronizando(false);
  };

  const hayMas = pagina * LIMITE < total;

  return (
    <div className="space-y-4">
      {pendientesLocales.length > 0 && (
        <section
          aria-label="Reportes pendientes en cola offline"
          className="rounded-2xl border border-amber-300 bg-amber-50 p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-bold text-amber-950">
              <UploadCloud className="h-5 w-5" aria-hidden="true" />
              <span>{pendientesLocales.length} pendiente(s) en cola local IndexedDB</span>
            </div>
            <button
              type="button"
              onClick={() => void sincronizarAhora()}
              disabled={sincronizando}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-xl bg-[#78350f] px-3.5 text-xs font-semibold text-white hover:bg-[#451a03] disabled:opacity-50"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              {sincronizando ? "Sincronizando..." : "Sincronizar ahora"}
            </button>
          </div>
          <ul className="mt-3 space-y-1.5 text-xs text-amber-950">
            {pendientesLocales.map((item) => (
              <li key={item.idempotency_key} className="rounded-lg bg-white/80 px-3 py-2">
                <strong>{formatearPesos(item.precio_cop)}</strong> ·{" "}
                {item.presentacion_etiqueta ?? item.presentacion_id} en{" "}
                {item.establecimiento_nombre ?? item.establecimiento_id} (intentos: {item.intentos})
              </li>
            ))}
          </ul>
        </section>
      )}

      {error && (
        <EstadoError
          detalle={error.detalle}
          codigo={error.codigo}
          requestId={error.requestId}
          onReintentar={() => void cargar()}
        />
      )}

      <TablaGestion
        columnas={COLUMNAS_MIS_REPORTES}
        datos={reportes}
        cargando={cargando}
        vacioTexto="Aún no tienes reportes enviados"
        vacioDescripcion="Cuando reportes precios desde la góndola aparecerán aquí con su estado visible."
        claveFila={(r) => r.id}
        tieneAnterior={pagina > 1}
        onAnterior={() => setPagina((p) => Math.max(1, p - 1))}
        siguienteCursor={hayMas ? String(pagina + 1) : null}
        onSiguiente={() => setPagina((p) => p + 1)}
        etiquetaTabla="Historial de mis reportes de precios"
      />
    </div>
  );
}

