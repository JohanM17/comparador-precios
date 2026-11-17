"use client";

import React, { useState } from "react";
import { clienteModeracion, type CasoDetalle, type ResolverCasoEntrada } from "@/lib/api/clienteModeracion";

export interface DetalleCasoPanelProps {
  readonly token: string;
  readonly caso: CasoDetalle;
  readonly onCerrar: () => void;
  readonly onResuelto: (mensaje: string) => void;
  readonly onError: (err: unknown) => void;
}

/**
 * Panel para inspeccionar evidencia y resolver un caso de moderacion.
 */
export default function DetalleCasoPanel({
  token,
  caso,
  onCerrar,
  onResuelto,
  onError,
}: DetalleCasoPanelProps): React.JSX.Element {
  const [decision, setDecision] = useState<"confirmar" | "descartar" | "sancionar">("descartar");
  const [nota, setNota] = useState("");
  const [tipoSancion, setTipoSancion] = useState<"advertencia" | "suspension" | "bloqueo">("suspension");
  const [diasSuspension, setDiasSuspension] = useState(7);
  const [resolviendo, setResolviendo] = useState(false);

  const enviarResolucion = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setResolviendo(true);
    try {
      const payload: ResolverCasoEntrada = {
        decision,
        nota: nota.trim(),
        sancion:
          decision === "sancionar"
            ? {
                tipo: tipoSancion,
                motivo: nota.trim(),
                dias_suspension: tipoSancion === "suspension" ? diasSuspension : null,
              }
            : null,
      };
      await clienteModeracion.resolverCaso(token, caso.id, payload);
      onResuelto(`Caso ${caso.id.slice(0, 8)} resuelto (${decision}).`);
    } catch (err) {
      onError(err);
    } finally {
      setResolviendo(false);
    }
  };

  return (
    <section className="rounded-2xl border border-emerald-300 bg-superficie p-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-bold text-slate-900">
          Caso {caso.tipo} ({caso.id.slice(0, 8)})
        </h3>
        <button
          type="button"
          onClick={onCerrar}
          className="min-h-11 rounded-xl px-3 text-xs font-semibold text-slate-600 hover:bg-slate-100"
        >
          Cerrar detalle
        </button>
      </div>
      <pre className="mt-3 max-h-48 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">
        {JSON.stringify({ detalle: caso.detalle, referencia: caso.referencia_datos }, null, 2)}
      </pre>

      {caso.estado !== "resuelto" && (
        <form onSubmit={(e) => void enviarResolucion(e)} className="mt-4 space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label htmlFor="decision-caso" className="block text-xs font-semibold text-slate-700">
                Decisión
              </label>
              <select
                id="decision-caso"
                value={decision}
                onChange={(e) =>
                  setDecision(e.target.value as "confirmar" | "descartar" | "sancionar")
                }
                className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
              >
                <option value="descartar">Descartar (aceptar reporte)</option>
                <option value="confirmar">Confirmar anomalía (rechazar)</option>
                <option value="sancionar">Confirmar y sancionar cuenta</option>
              </select>
            </div>

            {decision === "sancionar" && (
              <>
                <div>
                  <label htmlFor="tipo-sancion" className="block text-xs font-semibold text-slate-700">
                    Tipo sanción
                  </label>
                  <select
                    id="tipo-sancion"
                    value={tipoSancion}
                    onChange={(e) =>
                      setTipoSancion(e.target.value as "advertencia" | "suspension" | "bloqueo")
                    }
                    className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
                  >
                    <option value="advertencia">Advertencia</option>
                    <option value="suspension">Suspensión temporal</option>
                    <option value="bloqueo">Bloqueo definitivo</option>
                  </select>
                </div>
                {tipoSancion === "suspension" && (
                  <div>
                    <label htmlFor="dias-sancion" className="block text-xs font-semibold text-slate-700">
                      Días suspensión
                    </label>
                    <input
                      id="dias-sancion"
                      type="number"
                      min={1}
                      max={365}
                      value={diasSuspension}
                      onChange={(e) => setDiasSuspension(Number(e.target.value))}
                      className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
                    />
                  </div>
                )}
              </>
            )}
          </div>

          <div>
            <label htmlFor="nota-caso" className="block text-xs font-semibold text-slate-700">
              Nota de auditoría (mín. 5 caracteres)
            </label>
            <input
              id="nota-caso"
              required
              minLength={5}
              value={nota}
              onChange={(e) => setNota(e.target.value)}
              className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </div>

          <button
            type="submit"
            disabled={resolviendo}
            className="min-h-11 rounded-xl bg-bosque-800 px-5 text-sm font-semibold text-white hover:bg-bosque-900 disabled:opacity-50"
          >
            {resolviendo ? "Aplicando resolución..." : "Guardar resolución"}
          </button>
        </form>
      )}
    </section>
  );
}

