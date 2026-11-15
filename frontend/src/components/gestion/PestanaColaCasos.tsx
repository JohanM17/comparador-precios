"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Eye } from "lucide-react";
import { clienteModeracion, type CasoDetalle } from "@/lib/api/clienteModeracion";
import { extraerInfoError, formatearFechaBogota, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";
import TablaGestion, { type ColumnaTablaGestion } from "@/components/TablaGestion";
import DetalleCasoPanel from "@/components/gestion/DetalleCasoPanel";

const LIMITE = 15;

function crearColumnasCasos(
  onRevisar: (id: string) => void
): readonly ColumnaTablaGestion<CasoDetalle>[] {
  return [
    {
      clave: "tipo",
      encabezado: "Tipo / Prioridad",
      celda: (c) => (
        <div>
          <p className="font-semibold text-slate-900">{c.tipo}</p>
          <p className="text-xs text-slate-500">Prioridad P{c.prioridad}</p>
        </div>
      ),
    },
    {
      clave: "estado",
      encabezado: "Estado",
      celda: (c) => (
        <span className="inline-flex rounded-full border border-slate-300 bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-800">
          {c.estado}
        </span>
      ),
    },
    {
      clave: "creado",
      encabezado: "Creado en",
      celda: (c) => <span className="text-xs text-slate-600">{formatearFechaBogota(c.creado_en)}</span>,
    },
    {
      clave: "acciones",
      encabezado: "Acciones",
      celda: (c) => (
        <button
          type="button"
          onClick={() => onRevisar(c.id)}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-emerald-700 bg-emerald-50 px-3 text-xs font-semibold text-emerald-900 hover:bg-emerald-100"
        >
          <Eye className="h-3.5 w-3.5" aria-hidden="true" />
          Revisar
        </button>
      ),
    },
  ];
}

export interface PestanaColaCasosProps {
  readonly token: string;
}

/**
 * Pestana Moderador: Cola priorizada de casos (GET /v1/moderacion/casos).
 */
export default function PestanaColaCasos({
  token,
}: PestanaColaCasosProps): React.JSX.Element {
  const [estadoFiltro, setEstadoFiltro] = useState("abierto");
  const [tipoFiltro, setTipoFiltro] = useState("");
  const [offset, setOffset] = useState(0);
  const [casos, setCasos] = useState<CasoDetalle[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<InfoErrorVisible | null>(null);
  const [casoActivo, setCasoActivo] = useState<CasoDetalle | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const res = await clienteModeracion.listarCasos(token, {
        estado: estadoFiltro || null,
        tipo: tipoFiltro || null,
        limite: LIMITE,
        offset,
      });
      setCasos(res.datos);
      setTotal(res.total);
    } catch (err) {
      setError(extraerInfoError(err, "No pudimos cargar la cola de casos."));
    } finally {
      setCargando(false);
    }
  }, [estadoFiltro, offset, tipoFiltro, token]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const abrirDetalle = useCallback(async (id: string): Promise<void> => {
    setError(null);
    setExito(null);
    try {
      setCasoActivo(await clienteModeracion.obtenerCaso(token, id));
    } catch (err) {
      setError(extraerInfoError(err, "No pudimos cargar el detalle del caso."));
    }
  }, [token]);

  const columnas = useMemo(
    () => crearColumnasCasos((id) => void abrirDetalle(id)),
    [abrirDetalle]
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 rounded-2xl border border-slate-200 bg-white p-4">
        <div>
          <label htmlFor="filtro-estado-caso" className="block text-xs font-semibold text-slate-600">Estado</label>
          <select
            id="filtro-estado-caso"
            value={estadoFiltro}
            onChange={(e) => {
              setOffset(0);
              setEstadoFiltro(e.target.value);
            }}
            className="mt-1 min-h-11 rounded-xl border border-slate-300 px-3 text-sm"
          >
            <option value="abierto">Abierto</option>
            <option value="en_revision">En revisión</option>
            <option value="resuelto">Resuelto</option>
            <option value="">Todos</option>
          </select>
        </div>
        <div>
          <label htmlFor="filtro-tipo-caso" className="block text-xs font-semibold text-slate-600">Tipo de caso</label>
          <select
            id="filtro-tipo-caso"
            value={tipoFiltro}
            onChange={(e) => {
              setOffset(0);
              setTipoFiltro(e.target.value);
            }}
            className="mt-1 min-h-11 rounded-xl border border-slate-300 px-3 text-sm"
          >
            <option value="">Todos</option>
            <option value="reporte_dudoso">Reporte dudoso</option>
            <option value="rafaga">Ráfaga</option>
            <option value="solicitud_correccion">Solicitud corrección</option>
            <option value="sugerencia_presentacion">Sugerencia presentación</option>
          </select>
        </div>
      </div>

      {exito && (
        <output className="flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-950">
          <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
          {exito}
        </output>
      )}
      {error && <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />}

      {casoActivo && (
        <DetalleCasoPanel
          token={token}
          caso={casoActivo}
          onCerrar={() => setCasoActivo(null)}
          onResuelto={(msg) => {
            setExito(msg);
            setCasoActivo(null);
            void cargar();
          }}
          onError={(err) => setError(extraerInfoError(err, "No fue posible resolver el caso."))}
        />
      )}

      <TablaGestion
        columnas={columnas}
        datos={casos}
        cargando={cargando}
        vacioTexto="No hay casos en la bandeja"
        claveFila={(c) => c.id}
        tieneAnterior={offset > 0}
        onAnterior={() => setOffset((o) => Math.max(0, o - LIMITE))}
        siguienteCursor={offset + LIMITE < total ? String(offset + LIMITE) : null}
        onSiguiente={() => setOffset((o) => o + LIMITE)}
        etiquetaTabla="Cola de casos de moderación"
      />
    </div>
  );
}
