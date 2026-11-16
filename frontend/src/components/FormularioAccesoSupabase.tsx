"use client";

import React, { useState } from "react";
import { LogIn, UserPlus } from "lucide-react";
import { crearClienteAuthNavegador } from "@/lib/auth/supabase";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";

type ModoAuth = "iniciar" | "registrar";

export interface FormularioAccesoSupabaseProps {
  readonly errorInicial?: InfoErrorVisible | null;
  readonly onSesionActiva: () => Promise<void>;
}

/**
 * Formulario de inicio de sesion y registro mediante Supabase Auth.
 */
export default function FormularioAccesoSupabase({
  errorInicial = null,
  onSesionActiva,
}: FormularioAccesoSupabaseProps): React.JSX.Element {
  const [modo, setModo] = useState<ModoAuth>("iniciar");
  const [correo, setCorreo] = useState("");
  const [clave, setClave] = useState("");
  const [avisoCorreo, setAvisoCorreo] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<InfoErrorVisible | null>(errorInicial);

  const manejarAutenticacion = async (
    evento: React.FormEvent<HTMLFormElement>
  ): Promise<void> => {
    evento.preventDefault();
    setError(null);
    setAvisoCorreo(null);
    setEnviando(true);

    try {
      const supabase = crearClienteAuthNavegador();
      if (modo === "iniciar") {
        const { error: errAuth } = await supabase.auth.signInWithPassword({
          email: correo.trim(),
          password: clave,
        });
        if (errAuth) {
          throw new Error(errAuth.message);
        }
        await onSesionActiva();
        return;
      }

      const { data, error: errRegistro } = await supabase.auth.signUp({
        email: correo.trim(),
        password: clave,
      });
      if (errRegistro) {
        throw new Error(errRegistro.message);
      }
      if (data.session) {
        await onSesionActiva();
      } else {
        setAvisoCorreo(
          "Revisa tu correo electrónico para confirmar tu cuenta y luego inicia sesión."
        );
      }
    } catch (err) {
      setError(extraerInfoError(err, "Error al autenticar tu cuenta."));
    } finally {
      setEnviando(false);
    }
  };

  const etiquetaAccion = modo === "iniciar" ? "Ingresar" : "Registrarme";
  const textoBoton = enviando ? "Procesando..." : etiquetaAccion;

  return (
    <div className="space-y-5">
      <div role="tablist" aria-label="Modo de acceso" className="grid grid-cols-2 gap-2">
        <button
          type="button"
          role="tab"
          aria-selected={modo === "iniciar"}
          onClick={() => setModo("iniciar")}
          className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border text-sm font-semibold ${
            modo === "iniciar"
              ? "border-emerald-700 bg-emerald-700 text-white"
              : "border-slate-300 bg-white text-slate-800 hover:bg-slate-50"
          }`}
        >
          <LogIn className="h-4 w-4" aria-hidden="true" />
          Iniciar sesión
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={modo === "registrar"}
          onClick={() => setModo("registrar")}
          className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border text-sm font-semibold ${
            modo === "registrar"
              ? "border-emerald-700 bg-emerald-700 text-white"
              : "border-slate-300 bg-white text-slate-800 hover:bg-slate-50"
          }`}
        >
          <UserPlus className="h-4 w-4" aria-hidden="true" />
          Crear cuenta
        </button>
      </div>

      {error && (
        <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />
      )}

      {avisoCorreo && (
        <output className="block rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-950">
          {avisoCorreo}
        </output>
      )}

      <form onSubmit={(e) => void manejarAutenticacion(e)} className="space-y-4">
        <div>
          <label htmlFor="auth-correo" className="block text-xs font-semibold text-slate-800">
            Correo electrónico
          </label>
          <input
            id="auth-correo"
            type="email"
            required
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
            placeholder="tu@correo.com"
            className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
          />
        </div>
        <div>
          <label htmlFor="auth-clave" className="block text-xs font-semibold text-slate-800">
            Contraseña (mínimo 6 caracteres)
          </label>
          <input
            id="auth-clave"
            type="password"
            required
            minLength={6}
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 text-sm text-slate-900 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
          />
        </div>
        <button
          type="submit"
          disabled={enviando}
          className="min-h-11 w-full rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-700 disabled:opacity-60"
        >
          {textoBoton}
        </button>
      </form>
    </div>
  );
}

