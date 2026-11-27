"use client";

import React, { useState } from "react";
import { Scale } from "lucide-react";
import { clienteModeracion, type CasoDetalle, type ResolverCasoEntrada } from "@/lib/api/clienteModeracion";
import { etiquetaTipoCaso } from "@/lib/casosModeracion";
import { formatearPesos } from "@/lib/formato";
import SelloConfianza from "@/components/SelloConfianza";

type DecisionCaso = "confirmar" | "descartar" | "sancionar" | "";

export interface DetalleCasoPanelProps {
  readonly token: string;
  readonly caso: CasoDetalle;
  readonly onCerrar: () => void;
  readonly onResuelto: (mensaje: string) => void;
  readonly onError: (err: unknown) => void;
}

function leerNumero(detalle: Readonly<Record<string, unknown>>, clave: string): number | null {
  const valor = detalle[clave];
  return typeof valor === "number" && Number.isFinite(valor) ? valor : null;
}

function leerTexto(detalle: Readonly<Record<string, unknown>>, clave: string): string | null {
  const valor = detalle[clave];
  return typeof valor === "string" && valor.trim() !== "" ? valor : null;
}

function formatearPorcentaje(valor: number): string {
  return `${(valor * 100).toFixed(1).replace(".", ",")} %`;
}

/**
 * Panel para inspeccionar evidencia y resolver un caso de moderacion.
 *
 * Una disputa de precio no es un reporte dudoso: enfrenta dos fuentes validas
 * (el precio oficial del comercio y la mediana de la comunidad), asi que la
 * decision se nombra por quien gana y no se ofrece sancionar, porque no hay un
 * unico reporte que castigar.
 */
export default function DetalleCasoPanel({
  token,
  caso,
  onCerrar,
  onResuelto,
  onError,
}: DetalleCasoPanelProps): React.JSX.Element {
  const [decision, setDecision] = useState<DecisionCaso>("");
  const [nota, setNota] = useState("");
  const [tipoSancion, setTipoSancion] = useState<"advertencia" | "suspension" | "bloqueo">("suspension");
  const [diasSuspension, setDiasSuspension] = useState(7);
  const [resolviendo, setResolviendo] = useState(false);

  const esDisputa = caso.tipo === "disputa_precio";
  const detalle = caso.detalle;
  const precioOficial = leerNumero(detalle, "precio_oficial_cop");
  const precioComunidad = leerNumero(detalle, "precio_comunidad_cop");
  const diferenciaPct = leerNumero(detalle, "diferencia_pct");
  const nReportes = leerNumero(detalle, "n_reportes_validos");
  const nFuentes = leerNumero(detalle, "n_fuentes");
  const sello = leerTexto(detalle, "sello") ?? "en_disputa";

  const partesResumen: string[] = [];
  if (diferenciaPct !== null) {
    partesResumen.push(`Diferencia: ${formatearPorcentaje(diferenciaPct)}`);
  }
  if (nReportes !== null) {
    partesResumen.push(`${nReportes} ${nReportes === 1 ? "reporte" : "reportes"}`);
  }
  if (nFuentes !== null) {
    partesResumen.push(`${nFuentes} ${nFuentes === 1 ? "fuente" : "fuentes"}`);
  }
  const resumenDisputa = partesResumen.join(" · ");

  /*
   * `sancionar` no existe para una disputa: el backend lo rechaza con 422. Si el
   * estado quedo en esa opcion por un caso anterior, se normaliza antes de enviar.
   * Sin decision explicita no se envia nada: el moderador debe elegir.
   */
  const decisionEnviada: "confirmar" | "descartar" | "sancionar" | null =
    decision === "" ? null : esDisputa && decision === "sancionar" ? "descartar" : decision;

  const enviarResolucion = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    if (decisionEnviada === null) {
      return;
    }
    setResolviendo(true);
    try {
      const payload: ResolverCasoEntrada = {
        decision: decisionEnviada,
        nota: nota.trim(),
        sancion:
          decisionEnviada === "sancionar"
            ? {
                tipo: tipoSancion,
                motivo: nota.trim(),
                dias_suspension: tipoSancion === "suspension" ? diasSuspension : null,
              }
            : null,
      };
      await clienteModeracion.resolverCaso(token, caso.id, payload);
      const mensaje = esDisputa
        ? `Caso ${caso.id.slice(0, 8)} resuelto: gana ${
            decisionEnviada === "confirmar" ? "el comercio" : "la comunidad"
          }.`
        : `Caso ${caso.id.slice(0, 8)} resuelto (${decisionEnviada}).`;
      onResuelto(mensaje);
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
          Caso {etiquetaTipoCaso(caso.tipo)} ({caso.id.slice(0, 8)})
        </h3>
        <button
          type="button"
          onClick={onCerrar}
          className="min-h-11 rounded-xl px-3 text-xs font-semibold text-slate-600 hover:bg-slate-100"
        >
          Cerrar detalle
        </button>
      </div>

      {esDisputa ? (
        <section
          aria-labelledby="titulo-disputa-precio"
          data-prueba="detalle-disputa"
          className="mt-4 rounded-xl border border-cereza-200 bg-cereza-50 p-4"
        >
          <h4
            id="titulo-disputa-precio"
            className="inline-flex items-center gap-1.5 text-sm font-bold text-cereza-700"
          >
            <Scale className="h-4 w-4" aria-hidden="true" />
            Contraste de precios en disputa
          </h4>
          <p className="mt-1 max-w-[62ch] text-[13px] leading-relaxed text-slate-700">
            El comercio y la comunidad reportan precios distintos. Decide a quién dar la razón;
            la decisión queda auditada y no modifica el historial.
          </p>

          <dl className="mt-3 grid gap-4 sm:grid-cols-2">
            <div className="border-l-2 border-blue-600 pl-3">
              <dt className="text-xs font-semibold text-slate-600">Precio oficial del comercio</dt>
              <dd
                data-prueba="precio-oficial-disputa"
                className="cifras mt-1 text-2xl font-semibold tracking-tight text-slate-900"
              >
                {precioOficial === null ? "Sin dato" : formatearPesos(precioOficial)}
              </dd>
            </div>
            <div className="border-l-2 border-cereza-600 pl-3">
              <dt className="text-xs font-semibold text-slate-600">Precio de la comunidad</dt>
              <dd
                data-prueba="precio-comunidad-disputa"
                className="cifras mt-1 text-2xl font-semibold tracking-tight text-slate-900"
              >
                {precioComunidad === null ? "Sin dato" : formatearPesos(precioComunidad)}
              </dd>
            </div>
          </dl>

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
            <SelloConfianza sello={sello} motivoSello={null} />
            {resumenDisputa && (
              <p className="text-[12.5px] text-slate-600">{resumenDisputa}</p>
            )}
          </div>
        </section>
      ) : (
        <pre className="mt-3 max-h-48 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">
          {JSON.stringify({ detalle: caso.detalle, referencia: caso.referencia_datos }, null, 2)}
        </pre>
      )}

      {esDisputa && (
        <details className="mt-3 rounded-xl border border-slate-300 bg-superficie p-3">
          <summary className="cursor-pointer text-xs font-semibold text-slate-700">
            Datos técnicos del caso
          </summary>
          <pre className="mt-2 max-h-48 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">
            {JSON.stringify({ detalle: caso.detalle, referencia: caso.referencia_datos }, null, 2)}
          </pre>
        </details>
      )}

      {caso.estado !== "resuelto" && (
        <form onSubmit={(e) => void enviarResolucion(e)} className="mt-4 space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label htmlFor="decision-caso" className="block text-xs font-semibold text-slate-700">
                Decisión
              </label>
              <select
                id="decision-caso"
                required
                value={decision}
                onChange={(e) => setDecision(e.target.value as DecisionCaso)}
                className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
              >
                <option value="" disabled>
                  Elige una decisión
                </option>
                {esDisputa ? (
                  <>
                    <option value="confirmar">Dar la razón al comercio (confirmar)</option>
                    <option value="descartar">Dar la razón a la comunidad (descartar)</option>
                  </>
                ) : (
                  <>
                    <option value="descartar">Descartar (aceptar reporte)</option>
                    <option value="confirmar">Confirmar anomalía (rechazar)</option>
                    <option value="sancionar">Confirmar y sancionar cuenta</option>
                  </>
                )}
              </select>
            </div>

            {!esDisputa && decision === "sancionar" && (
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
