"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Camera, CheckCircle2, Clock, RefreshCw, Trash2, WifiOff } from "lucide-react";
import { obtenerTokenAcceso } from "@/lib/auth/supabase";
import { comprimirFotoWebP } from "@/lib/imagen/comprimirFoto";
import {
  guardarPresentacionReciente,
  guardarTiendaReciente,
  type PresentacionOpcion,
  type TiendaSeleccionada,
} from "@/lib/offline/cacheSelectores";
import {
  contarColaReportes,
  encolarReporteOffline,
  registrarSincronizacionAutomatica,
  sincronizarColaReportes,
} from "@/lib/offline/colaReportes";
import CampoPrecio from "@/components/CampoPrecio";
import EstadoError from "@/components/EstadoError";
import SelectorPresentacion from "@/components/SelectorPresentacion";
import SelectorTienda from "@/components/SelectorTienda";

/**
 * Formulario movil rapido S4 (/reportar) con 3 controles, compresion WebP sin EXIF,
 * cola offline IndexedDB (Flujo F4) y cronometro ?medicion=1 para EC-01.
 */
export default function FormularioReportar(): React.JSX.Element {
  const modoMedicion = useSearchParams().get("medicion") === "1";
  const inicioMsRef = useRef<number>(typeof performance !== "undefined" ? performance.now() : 0);
  const [msTranscurridos, setMsTranscurridos] = useState(0);
  const [msFinal, setMsFinal] = useState<number | null>(null);

  const [tiendaId, setTiendaId] = useState("");
  const [tiendaMeta, setTiendaMeta] = useState<TiendaSeleccionada | undefined>(undefined);
  const [presentacionId, setPresentacionId] = useState("");
  const [presentacionMeta, setPresentacionMeta] = useState<PresentacionOpcion | undefined>(undefined);
  const [precioTexto, setPrecioTexto] = useState("");
  const [precioCop, setPrecioCop] = useState<number | null>(null);
  const [fotoBlob, setFotoBlob] = useState<Blob | null>(null);
  const [fotoResumen, setFotoResumen] = useState<string | null>(null);
  const [comprimiendoFoto, setComprimiendoFoto] = useState(false);

  const [enLinea, setEnLinea] = useState(true);
  const [pendientesCola, setPendientesCola] = useState(0);
  const [enviando, setEnviando] = useState(false);
  const [exitoMensaje, setExitoMensaje] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [requiereIngreso, setRequiereIngreso] = useState(false);

  const actualizarConteoCola = useCallback(async () => setPendientesCola(await contarColaReportes()), []);

  useEffect(() => {
    if (!modoMedicion || msFinal !== null) return;
    inicioMsRef.current = performance.now();
    const id = window.setInterval(() => setMsTranscurridos(Math.round(performance.now() - inicioMsRef.current)), 50);
    return () => window.clearInterval(id);
  }, [modoMedicion, msFinal]);

  useEffect(() => {
    setEnLinea(typeof navigator !== "undefined" ? navigator.onLine : true);
    const alConectar = (): void => setEnLinea(true);
    const alDesconectar = (): void => setEnLinea(false);
    window.addEventListener("online", alConectar);
    window.addEventListener("offline", alDesconectar);
    const desuscribirSync = registrarSincronizacionAutomatica(obtenerTokenAcceso, (r) => setPendientesCola(r.pendientes));
    void actualizarConteoCola();
    return () => {
      window.removeEventListener("online", alConectar);
      window.removeEventListener("offline", alDesconectar);
      desuscribirSync();
    };
  }, [actualizarConteoCola]);

  const manejarFoto = async (ev: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
    const archivo = ev.target.files?.[0];
    if (!archivo) return;
    setErrorMsg(null);
    setComprimiendoFoto(true);
    try {
      const res = await comprimirFotoWebP(archivo);
      setFotoBlob(res.blob);
      setFotoResumen(`${Math.max(1, Math.round(res.tamanoBytes / 1024))} KB WebP (${res.ancho}x${res.alto}, sin EXIF)`);
    } catch (err) {
      setFotoBlob(null);
      setFotoResumen(null);
      setErrorMsg(err instanceof Error ? err.message : "No pudimos comprimir la foto.");
    } finally {
      setComprimiendoFoto(false);
    }
  };

  const enviarReporte = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setErrorMsg(null);
    setExitoMensaje(null);
    setRequiereIngreso(false);
    if (!tiendaId || !presentacionId || !precioCop || precioCop <= 0) {
      setErrorMsg("Completa tienda, presentación y un precio válido en COP.");
      return;
    }

    setEnviando(true);
    try {
      if (tiendaMeta) guardarTiendaReciente(tiendaMeta);
      if (presentacionMeta) guardarPresentacionReciente(presentacionMeta);
      await encolarReporteOffline({
        idempotency_key: crypto.randomUUID(),
        presentacion_id: presentacionId,
        presentacion_etiqueta: presentacionMeta?.etiqueta,
        establecimiento_id: tiendaId,
        establecimiento_nombre: tiendaMeta?.nombre,
        precio_cop: precioCop,
        observado_en: new Date().toISOString(),
        foto_blob: fotoBlob,
      });

      const cerrarEnvio = (msg: string): void => {
        if (modoMedicion) setMsFinal(Math.round(performance.now() - inicioMsRef.current));
        setExitoMensaje(msg);
        setPrecioTexto("");
        setPrecioCop(null);
        setFotoBlob(null);
        setFotoResumen(null);
      };

      if (!navigator.onLine) {
        await actualizarConteoCola();
        cerrarEnvio("Sin señal: reporte guardado en tu dispositivo. Se enviará al reconectar.");
        return;
      }

      if (!(await obtenerTokenAcceso())) {
        await actualizarConteoCola();
        setRequiereIngreso(true);
        setErrorMsg("Guardado en cola local. Inicia sesión para enviarlo al servidor.");
        return;
      }

      const resumen = await sincronizarColaReportes(obtenerTokenAcceso, { forzar: true });
      setPendientesCola(resumen.pendientes);
      if (resumen.descartados422 > 0 && resumen.sincronizados === 0) {
        setErrorMsg(resumen.errores[0] || "El precio o los datos no superaron la validación.");
        return;
      }
      cerrarEnvio(resumen.pendientes === 0 ? "Precio registrado y sincronizado correctamente." : "Guardado en cola local: se reintentará automáticamente.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl space-y-4 px-4 py-5 pb-24 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Reportar precio</h1>
          <p className="text-xs text-slate-600">3 pasos frente a la góndola, incluso sin conexión móvil.</p>
        </div>
        {pendientesCola > 0 && (
          <button
            type="button"
            onClick={() => void sincronizarColaReportes(obtenerTokenAcceso, { forzar: true }).then((r) => setPendientesCola(r.pendientes))}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-amber-300 bg-amber-50 px-3 text-xs font-semibold text-amber-950"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            {pendientesCola} en cola
          </button>
        )}
      </header>

      {!enLinea && (
        <output className="flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs font-semibold text-amber-950">
          <WifiOff className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span>Modo sin conexión activo: los reportes y fotos se guardan en IndexedDB.</span>
        </output>
      )}

      {modoMedicion && (
        <output data-testid="cronometro-ec01" className="flex items-center justify-between rounded-xl border border-slate-300 bg-slate-900 px-4 py-2.5 font-mono text-xs text-white">
          <span className="flex items-center gap-1.5"><Clock className="h-4 w-4 text-emerald-400" aria-hidden="true" />Medición EC-01:</span>
          <span className="font-bold">{msFinal !== null ? `${msFinal} ms (${(msFinal / 1000).toFixed(2)} s)` : `${msTranscurridos} ms`}</span>
        </output>
      )}

      {errorMsg && <EstadoError detalle={errorMsg} />}
      {requiereIngreso && (
        <Link href="/ingresar" className="inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-emerald-700 bg-emerald-50 px-4 text-sm font-semibold text-emerald-900">
          Ir a iniciar sesión y autorizar Ley 1581
        </Link>
      )}
      {exitoMensaje && (
        <output className="flex items-start gap-2.5 rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm font-semibold text-emerald-950">
          <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-700" aria-hidden="true" />
          <div>
            <p>{exitoMensaje}</p>
            {modoMedicion && msFinal !== null && <p className="mt-1 text-xs font-normal">{msFinal <= 15000 ? "Umbral EC-01 cumplido (<= 15 s)." : "Superó 15 s; revisar pasos."}</p>}
          </div>
        </output>
      )}

      <form onSubmit={(e) => void enviarReporte(e)} className="space-y-4">
        <SelectorTienda valor={tiendaId} onChange={(id, meta) => { setTiendaId(id); setTiendaMeta(meta); }} />
        <SelectorPresentacion valor={presentacionId} onChange={(id, meta) => { setPresentacionId(id); setPresentacionMeta(meta); }} />
        <CampoPrecio valor={precioTexto} onChange={(d, cop) => { setPrecioTexto(d); setPrecioCop(cop); }} />

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label htmlFor="foto-evidencia" className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-slate-300 bg-slate-50 px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100">
              <Camera className="h-4 w-4 text-emerald-700" aria-hidden="true" />
              <span>{comprimiendoFoto ? "Comprimiendo WebP..." : "Foto de etiqueta (opcional)"}</span>
              <input id="foto-evidencia" type="file" accept="image/*" capture="environment" onChange={(e) => void manejarFoto(e)} className="sr-only" />
            </label>
            {fotoResumen && (
              <div className="flex items-center gap-2 text-xs font-medium text-emerald-800">
                <span>{fotoResumen}</span>
                <button type="button" aria-label="Quitar fotografía" onClick={() => { setFotoBlob(null); setFotoResumen(null); }} className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-rose-700 hover:bg-rose-50">
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            )}
          </div>
        </div>

        <button type="submit" disabled={enviando || comprimiendoFoto} className="min-h-12 w-full rounded-xl bg-emerald-700 px-5 py-3 text-base font-bold text-white shadow-md hover:bg-emerald-800 disabled:opacity-50">
          {enviando ? "Guardando precio..." : "Guardar precio"}
        </button>
      </form>
    </div>
  );
}
