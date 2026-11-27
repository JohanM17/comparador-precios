"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import {
  clienteComercio,
  type SolicitudVerificacion,
} from "@/lib/api/clienteComercio";
import { extraerInfoError, formatearFechaBogota, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";

export interface PestanaReclamosComercioProps {
  readonly token: string;
}

/**
 * Pestaña «Reclamos de comercio» de S6, para moderadores.
 *
 * Aprobar un reclamo le entrega a una cuenta el control de los precios
 * oficiales de un establecimiento. Es una decisión humana por diseño (`D-09`),
 * así que la pantalla muestra el teléfono y el mensaje con los que el
 * moderador puede verificar antes de decidir, y pide una nota que queda en la
 * auditoría.
 */
export default function PestanaReclamosComercio({
  token,
}: PestanaReclamosComercioProps): React.JSX.Element {
  const [solicitudes, setSolicitudes] = useState<readonly SolicitudVerificacion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<InfoErrorVisible | null>(null);
  const [exito, setExito] = useState<string | null>(null);
  const [notas, setNotas] = useState<Record<string, string>>({});
  const [procesando, setProcesando] = useState<string | null>(null);

  const cargar = useCallback(async (): Promise<void> => {
    setCargando(true);
    setError(null);
    try {
      const res = await clienteComercio.listarSolicitudes(token);
      setSolicitudes(res.datos);
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible cargar los reclamos."));
    } finally {
      setCargando(false);
    }
  }, [token]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const decidir = async (solicitud: SolicitudVerificacion, aprobar: boolean): Promise<void> => {
    setError(null);
    setExito(null);
    setProcesando(solicitud.id);
    try {
      await clienteComercio.verificarComercio(token, solicitud.id, {
        aprobar,
        nota: notas[solicitud.id]?.trim() || null,
      });
      setExito(
        aprobar
          ? `${solicitud.solicitante_alias} queda como responsable de ${solicitud.establecimiento_nombre}.`
          : `Reclamo sobre ${solicitud.establecimiento_nombre} rechazado.`
      );
      await cargar();
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible resolver el reclamo."));
    } finally {
      setProcesando(null);
    }
  };

  return (
    <div className="space-y-8">
      <section aria-labelledby="titulo-reclamos">
        <h2 id="titulo-reclamos" className="rotulo mb-1.5">
          Reclamos de titularidad
        </h2>
        <p className="max-w-[62ch] text-[13.5px] leading-relaxed text-slate-500">
          Aprobar le entrega a esta cuenta el control de los precios oficiales del
          establecimiento y le asigna el rol de comercio. Verifica por teléfono antes de decidir.
        </p>
      </section>

      {error && (
        <EstadoError
          detalle={error.detalle}
          codigo={error.codigo}
          requestId={error.requestId}
          onReintentar={() => void cargar()}
        />
      )}

      {exito && (
        <p
          role="status"
          className="flex items-start gap-2 border-l-2 border-emerald-600 pl-3 text-[13.5px] leading-relaxed text-slate-700"
        >
          <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-600" aria-hidden="true" />
          <span>{exito}</span>
        </p>
      )}

      {cargando && <p className="rotulo">Cargando reclamos…</p>}

      {!cargando && solicitudes.length === 0 && (
        <p className="text-[13.5px] text-slate-500">No hay reclamos pendientes.</p>
      )}

      {!cargando && solicitudes.length > 0 && (
        <ul className="border-t border-slate-200">
          {solicitudes.map((s) => (
            <li key={s.id} className="border-b border-slate-200 py-5">
              <p className="text-[15px] font-medium tracking-[-0.015em] text-slate-900">
                {s.establecimiento_nombre}
              </p>
              <p className="mt-1 text-[13px] text-slate-600">
                {[s.establecimiento_barrio, s.establecimiento_direccion].filter(Boolean).join(" · ") ||
                  "Sin dirección registrada"}
              </p>
              <p className="cifras mt-2 text-[13px] text-slate-700">
                {s.solicitante_alias} · {s.telefono_contacto}
              </p>
              <p className="mt-2 max-w-[62ch] text-[13px] leading-relaxed text-slate-600">
                {s.mensaje}
              </p>
              <p className="cifras mt-2 text-[12.5px] text-slate-500">
                Recibido el {formatearFechaBogota(s.creado_en)}
              </p>

              <div className="mt-4 sm:max-w-md">
                <label
                  htmlFor={`nota-${s.id}`}
                  className="block text-[12.5px] font-medium text-slate-500"
                >
                  Nota para la auditoría
                </label>
                <input
                  id={`nota-${s.id}`}
                  maxLength={1000}
                  value={notas[s.id] ?? ""}
                  onChange={(ev) =>
                    setNotas((previas) => ({ ...previas, [s.id]: ev.target.value }))
                  }
                  placeholder="Llamé al número y confirmó el nombre del local"
                  className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[14.5px] text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-0"
                />
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-x-8 gap-y-3">
                <button
                  type="button"
                  disabled={procesando === s.id}
                  onClick={() => void decidir(s, true)}
                  className="inline-flex min-h-11 items-center justify-center rounded-full bg-brasa-600 px-5 text-[13.5px] font-medium text-slate-50 transition-colors hover:bg-brasa-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:opacity-50"
                >
                  {procesando === s.id ? "Procesando…" : "Aprobar"}
                </button>
                <button
                  type="button"
                  disabled={procesando === s.id}
                  onClick={() => void decidir(s, false)}
                  className="min-h-11 text-[13.5px] text-cereza-600 underline decoration-cereza-300 underline-offset-4 transition-colors hover:decoration-cereza-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 disabled:opacity-50"
                >
                  Rechazar
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
