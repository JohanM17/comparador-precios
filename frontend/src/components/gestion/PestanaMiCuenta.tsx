"use client";

import React, { useState } from "react";
import { CheckCircle2, ShieldAlert, Trash2 } from "lucide-react";
import type { PerfilUsuario } from "@/lib/api/clienteApi";
import { clienteReportes } from "@/lib/api/clienteReportes";
import { crearClienteAuthNavegador } from "@/lib/auth/supabase";
import {
  extraerInfoError,
  formatearFechaBogota,
  type InfoErrorVisible,
} from "@/lib/formato";
import EstadoError from "@/components/EstadoError";

export interface PestanaMiCuentaProps {
  readonly token: string;
  readonly perfil: PerfilUsuario;
  readonly onPerfilActualizado: (nuevo: PerfilUsuario) => void;
  readonly onCuentaEliminada: () => void;
}

/**
 * Pestana Reportante: consulta de perfil Ley 1581, edicion de alias y supresion irreversible.
 */
export default function PestanaMiCuenta({
  token,
  perfil,
  onPerfilActualizado,
  onCuentaEliminada,
}: PestanaMiCuentaProps): React.JSX.Element {
  const [alias, setAlias] = useState(perfil.alias);
  const [guardando, setGuardando] = useState(false);
  const [exitoAlias, setExitoAlias] = useState<string | null>(null);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  const [modalEliminar, setModalEliminar] = useState(false);
  const [confirmacionTexto, setConfirmacionTexto] = useState("");
  const [eliminando, setEliminando] = useState(false);

  const guardarAlias = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setError(null);
    setExitoAlias(null);
    setGuardando(true);
    try {
      const actualizado = await clienteReportes.actualizarAlias(token, alias.trim());
      onPerfilActualizado(actualizado);
      setExitoAlias("Alias actualizado correctamente.");
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible actualizar tu alias."));
    } finally {
      setGuardando(false);
    }
  };

  const confirmarEliminacion = async (): Promise<void> => {
    setError(null);
    setEliminando(true);
    try {
      await clienteReportes.eliminarMiCuenta(token);
      const supabase = crearClienteAuthNavegador();
      await supabase.auth.signOut();
      setModalEliminar(false);
      onCuentaEliminada();
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible suprimir tu cuenta."));
      setModalEliminar(false);
    } finally {
      setEliminando(false);
    }
  };

  const versionPolitica =
    typeof perfil.autorizacion_vigente?.version_politica === "string"
      ? perfil.autorizacion_vigente.version_politica
      : "v1.0";

  return (
    <div className="space-y-6">
      {error && (
        <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />
      )}

      {exitoAlias && (
        <output className="flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-950">
          <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
          {exitoAlias}
        </output>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Mis datos personales (Ley 1581)</h2>
        <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <div className="rounded-xl bg-slate-50 p-3">
            <dt className="text-xs font-semibold text-slate-500">Rol y estado</dt>
            <dd className="mt-1 font-semibold text-slate-900">
              {perfil.rol} · {perfil.estado}
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <dt className="text-xs font-semibold text-slate-500">Reputación comunitaria</dt>
            <dd className="mt-1 font-semibold text-slate-900">
              {perfil.reputacion} ({perfil.reportes_corroborados} corroborados)
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <dt className="text-xs font-semibold text-slate-500">Cuenta creada en</dt>
            <dd className="mt-1 text-slate-800">{formatearFechaBogota(perfil.creado_en)}</dd>
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <dt className="text-xs font-semibold text-slate-500">Consentimiento Ley 1581</dt>
            <dd className="mt-1 text-slate-800">Política {versionPolitica} vigente</dd>
          </div>
        </dl>

        <form onSubmit={(e) => void guardarAlias(e)} className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="nuevo-alias" className="block text-xs font-semibold text-slate-700">
              Alias público
            </label>
            <input
              id="nuevo-alias"
              type="text"
              required
              minLength={3}
              maxLength={30}
              pattern="^[a-zA-Z0-9_.-]+$"
              value={alias}
              onChange={(e) => setAlias(e.target.value)}
              className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={guardando || alias.trim() === perfil.alias}
            className="min-h-11 rounded-xl bg-emerald-700 px-5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
          >
            {guardando ? "Guardando..." : "Actualizar alias"}
          </button>
        </form>
      </section>

      <section className="rounded-2xl border border-rose-200 bg-rose-50/50 p-5">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 text-rose-700" aria-hidden="true" />
          <div className="flex-1">
            <h2 className="text-base font-bold text-rose-950">
              Derecho de supresión y anonimización (Ley 1581)
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-rose-900">
              Al suprimir tu cuenta se eliminarán tus credenciales de acceso y fotografías de prueba,
              y tus reportes históricos quedarán completamente anonimizados. Esta acción es irreversible.
            </p>
            <button
              type="button"
              onClick={() => {
                setConfirmacionTexto("");
                setModalEliminar(true);
              }}
              className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-xl bg-rose-700 px-4 text-sm font-semibold text-white hover:bg-rose-800"
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              Suprimir cuenta y anonimizar datos (Ley 1581)
            </button>
          </div>
        </div>
      </section>

      {modalEliminar && (
        <dialog
          open
          aria-modal="true"
          aria-labelledby="titulo-confirmar-supresion"
          className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center border-0 bg-slate-900/60 p-4"
        >
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <h3 id="titulo-confirmar-supresion" className="text-lg font-bold text-slate-900">
              Confirmar supresión de cuenta
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Escribe <strong>ELIMINAR</strong> para confirmar la anonimización definitiva de tu cuenta.
            </p>
            <label htmlFor="confirmacion-eliminar" className="sr-only">
              Escribe ELIMINAR para confirmar
            </label>
            <input
              id="confirmacion-eliminar"
              type="text"
              value={confirmacionTexto}
              onChange={(e) => setConfirmacionTexto(e.target.value)}
              placeholder="ELIMINAR"
              className="mt-3 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
            <div className="mt-5 flex gap-3">
              <button
                type="button"
                onClick={() => setModalEliminar(false)}
                className="min-h-11 flex-1 rounded-xl border border-slate-300 bg-white text-sm font-semibold text-slate-800"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={eliminando || confirmacionTexto.trim().toUpperCase() !== "ELIMINAR"}
                onClick={() => void confirmarEliminacion()}
                className="min-h-11 flex-1 rounded-xl bg-rose-700 text-sm font-semibold text-white hover:bg-rose-800 disabled:opacity-50"
              >
                {eliminando ? "Anonimizando..." : "Confirmar supresión"}
              </button>
            </div>
          </div>
        </dialog>
      )}
    </div>
  );
}

