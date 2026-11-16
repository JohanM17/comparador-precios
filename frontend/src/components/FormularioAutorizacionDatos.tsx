"use client";

import React, { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { clienteApi, type PoliticaTratamiento } from "@/lib/api/clienteApi";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import Cargando from "@/components/Cargando";
import EstadoError from "@/components/EstadoError";

const PATRON_ALIAS = /^[a-zA-Z0-9_.-]{3,30}$/;

export interface FormularioAutorizacionDatosProps {
  readonly token: string;
  readonly onAutorizado: (alias: string) => void;
}

/**
 * Paso obligatorio de consentimiento previo, expreso e informado (Ley 1581 de 2012).
 * La casilla inicia desmarcada por defecto.
 */
export default function FormularioAutorizacionDatos({
  token,
  onAutorizado,
}: FormularioAutorizacionDatosProps): React.JSX.Element {
  const [politica, setPolitica] = useState<PoliticaTratamiento | null>(null);
  const [cargando, setCargando] = useState(true);
  const [alias, setAlias] = useState("");
  const [acepta, setAcepta] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  useEffect(() => {
    let activo = true;
    clienteApi
      .obtenerPoliticaTratamiento()
      .then((res) => {
        if (activo) {
          setPolitica(res);
        }
      })
      .catch((err) => {
        if (activo) {
          setError(extraerInfoError(err, "No fue posible cargar la política de tratamiento."));
        }
      })
      .finally(() => {
        if (activo) {
          setCargando(false);
        }
      });
    return () => {
      activo = false;
    };
  }, []);

  const manejarEnvio = async (evento: React.FormEvent<HTMLFormElement>): Promise<void> => {
    evento.preventDefault();
    setError(null);

    const aliasLimpio = alias.trim();
    if (!PATRON_ALIAS.test(aliasLimpio)) {
      setError({
        detalle:
          "El alias debe tener entre 3 y 30 caracteres y solo usar letras, números, puntos, guiones o guion bajo.",
        codigo: "ALIAS_INVALIDO",
      });
      return;
    }
    if (!acepta) {
      setError({
        detalle: "Debes marcar la casilla de aceptación expresa de la política de datos.",
        codigo: "AUTORIZACION_REQUERIDA",
      });
      return;
    }

    setEnviando(true);
    try {
      const res = await clienteApi.registrarAutorizacion(token, {
        alias: aliasLimpio,
        version_politica: politica?.version ?? "1.0",
        acepta: true,
      });
      onAutorizado(res.alias);
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible registrar tu autorización."));
    } finally {
      setEnviando(false);
    }
  };

  if (cargando) {
    return <Cargando filas={3} etiqueta="Cargando política de tratamiento de datos..." />;
  }

  return (
    <form onSubmit={(e) => void manejarEnvio(e)} className="space-y-5">
      <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-4 text-sm text-blue-950">
        <div className="flex items-center gap-2 font-bold">
          <ShieldCheck className="h-5 w-5 text-blue-800" aria-hidden="true" />
          <span>
            Autorización previa de datos personales (Ley 1581 · v{politica?.version ?? "1.0"})
          </span>
        </div>
        <p className="mt-2 leading-relaxed">{politica?.texto_completo}</p>
        {politica && politica.finalidades.length > 0 && (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-blue-900">
            {politica.finalidades.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
      </div>

      {error && (
        <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />
      )}

      <div>
        <label htmlFor="autorizacion-alias" className="block text-xs font-semibold text-slate-800">
          Elige tu alias público (3 a 30 caracteres)
        </label>
        <input
          id="autorizacion-alias"
          type="text"
          required
          minLength={3}
          maxLength={30}
          pattern="[a-zA-Z0-9_.\-]{3,30}"
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          placeholder="ej. vecino_armenia"
          className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
        />
        <p className="mt-1 text-xs text-slate-500">
          Solo letras, números y los símbolos <code>.</code>, <code>_</code> o <code>-</code>.
        </p>
      </div>

      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-sm text-slate-800">
        <input
          type="checkbox"
          checked={acepta}
          onChange={(e) => setAcepta(e.target.checked)}
          className="mt-0.5 h-5 w-5 rounded border-slate-300 text-emerald-700 focus:ring-emerald-700"
        />
        <span>
          He leído y otorgo mi consentimiento previo, expreso e informado para el tratamiento de mis
          datos personales conforme a la política vigente (v{politica?.version ?? "1.0"}).
        </span>
      </label>

      <button
        type="submit"
        disabled={enviando}
        className="min-h-11 w-full rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-700 disabled:opacity-60"
      >
        {enviando ? "Guardando autorización..." : "Aceptar y activar mi cuenta"}
      </button>
    </form>
  );
}

