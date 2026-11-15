"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, X } from "lucide-react";
import { clienteApi } from "@/lib/api/clienteApi";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";

export interface ModalCorreccionTiendaProps {
  readonly establecimientoId: string;
  readonly establecimientoNombre: string;
  readonly abierto: boolean;
  readonly onCerrar: () => void;
}

/**
 * Modal accesible para enviar solicitudes ciudadanas de correccion de tienda (incluye honeypot).
 */
export default function ModalCorreccionTienda({
  establecimientoId,
  establecimientoNombre,
  abierto,
  onCerrar,
}: ModalCorreccionTiendaProps): React.JSX.Element | null {
  const [correo, setCorreo] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [sitioWebTrampa, setSitioWebTrampa] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [exito, setExito] = useState<string | null>(null);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  useEffect(() => {
    if (!abierto) {
      return;
    }
    const alPresionarTecla = (ev: KeyboardEvent): void => {
      if (ev.key === "Escape") {
        onCerrar();
      }
    };
    window.addEventListener("keydown", alPresionarTecla);
    return () => window.removeEventListener("keydown", alPresionarTecla);
  }, [abierto, onCerrar]);

  if (!abierto) {
    return null;
  }

  const manejarEnvio = async (evento: React.FormEvent<HTMLFormElement>): Promise<void> => {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const res = await clienteApi.enviarSolicitudCorreccion(establecimientoId, {
        correo: correo.trim(),
        mensaje: mensaje.trim(),
        sitio_web_trampa: sitioWebTrampa || null,
      });
      setExito(res.mensaje);
      setCorreo("");
      setMensaje("");
      setSitioWebTrampa("");
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible enviar la solicitud de corrección."));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <dialog
      open
      aria-modal="true"
      aria-labelledby="titulo-modal-correccion"
      className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center border-0 bg-slate-900/60 p-4"
    >
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="titulo-modal-correccion" className="text-lg font-bold text-slate-900">
              ¿Hay información errónea sobre este negocio?
            </h2>
            <p className="mt-1 text-xs text-slate-600">{establecimientoNombre}</p>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            aria-label="Cerrar ventana"
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {exito ? (
          <div className="mt-5 space-y-4">
            <output className="flex items-start gap-3 rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-950">
              <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-700" aria-hidden="true" />
              <p>{exito}</p>
            </output>
            <button
              type="button"
              onClick={() => {
                setExito(null);
                onCerrar();
              }}
              className="min-h-11 w-full rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-700"
            >
              Cerrar
            </button>
          </div>
        ) : (
          <form onSubmit={(e) => void manejarEnvio(e)} className="mt-5 space-y-4">
            {error && (
              <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />
            )}

            <div>
              <label htmlFor="correccion-correo" className="block text-xs font-semibold text-slate-800">
                Correo de contacto
              </label>
              <input
                id="correccion-correo"
                type="email"
                required
                minLength={5}
                maxLength={120}
                value={correo}
                onChange={(e) => setCorreo(e.target.value)}
                placeholder="tucorreo@ejemplo.com"
                className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
              />
            </div>

            <div>
              <label htmlFor="correccion-mensaje" className="block text-xs font-semibold text-slate-800">
                Describe qué dato requiere corrección (mínimo 10 caracteres)
              </label>
              <textarea
                id="correccion-mensaje"
                required
                minLength={10}
                maxLength={1000}
                rows={4}
                value={mensaje}
                onChange={(e) => setMensaje(e.target.value)}
                placeholder="Ej. La dirección correcta es Cra 14 # 18-22 o el negocio cerró."
                className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
              />
            </div>

            {/* Campo oculto honeypot antispam */}
            <div className="hidden" aria-hidden="true">
              <label htmlFor="sitio-web-trampa">Sitio web</label>
              <input
                id="sitio-web-trampa"
                name="sitio_web_trampa"
                type="text"
                tabIndex={-1}
                autoComplete="off"
                value={sitioWebTrampa}
                onChange={(e) => setSitioWebTrampa(e.target.value)}
              />
            </div>

            <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={onCerrar}
                className="min-h-11 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-700"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={enviando}
                className="min-h-11 rounded-xl bg-emerald-700 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-700 disabled:opacity-60"
              >
                {enviando ? "Enviando..." : "Enviar solicitud"}
              </button>
            </div>
          </form>
        )}
      </div>
    </dialog>
  );
}

