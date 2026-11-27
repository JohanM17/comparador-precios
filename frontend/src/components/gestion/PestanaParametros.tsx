"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Save } from "lucide-react";
import { clienteModeracion, type ParametroItem } from "@/lib/api/clienteModeracion";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";
import TablaGestion, { type ColumnaTablaGestion } from "@/components/TablaGestion";

export interface PestanaParametrosProps {
  readonly token: string;
}

function crearColumnasParametros(
  borradores: Readonly<Record<string, string>>,
  guardandoClave: string | null,
  onCambiar: (clave: string, valor: string) => void,
  onGuardar: (item: ParametroItem) => void
): readonly ColumnaTablaGestion<ParametroItem>[] {
  return [
    {
      clave: "clave",
      encabezado: "Clave / Descripción",
      celda: (p) => (
        <div>
          <p className="font-mono text-xs font-bold text-slate-900">{p.clave}</p>
          <p className="mt-0.5 text-xs text-slate-600">{p.descripcion}</p>
          <p className="mt-0.5 text-[11px] text-slate-500">Rango: {p.rango_valido}</p>
        </div>
      ),
    },
    {
      clave: "valor",
      encabezado: "Valor editable",
      celda: (p) => (
        <input
          type="text"
          aria-label={`Valor de ${p.clave}`}
          value={borradores[p.clave] ?? ""}
          onChange={(e) => onCambiar(p.clave, e.target.value)}
          className="min-h-11 w-full min-w-[160px] rounded-xl border border-slate-300 px-3 font-mono text-xs"
        />
      ),
    },
    {
      clave: "accion",
      encabezado: "Guardar",
      celda: (p) => (
        <button
          type="button"
          disabled={guardandoClave === p.clave}
          onClick={() => onGuardar(p)}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-xl bg-bosque-800 px-3.5 text-xs font-semibold text-white hover:bg-bosque-900 disabled:opacity-50"
        >
          <Save className="h-3.5 w-3.5" aria-hidden="true" />
          {guardandoClave === p.clave ? "..." : "Guardar"}
        </button>
      ),
    },
  ];
}

/**
 * Pestana Moderador: visualizacion y calibracion en caliente de los 43 parametros de negocio.
 */
export default function PestanaParametros({
  token,
}: PestanaParametrosProps): React.JSX.Element {
  const [parametros, setParametros] = useState<ParametroItem[]>([]);
  const [borradores, setBorradores] = useState<Record<string, string>>({});
  const [filtro, setFiltro] = useState("");
  const [cargando, setCargando] = useState(true);
  const [guardandoClave, setGuardandoClave] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const res = await clienteModeracion.listarParametros(token);
      setParametros(res.datos);
      const iniciales: Record<string, string> = {};
      for (const item of res.datos) {
        iniciales[item.clave] =
          typeof item.valor === "string" ? item.valor : JSON.stringify(item.valor);
      }
      setBorradores(iniciales);
    } catch (err) {
      setError(extraerInfoError(err, "No pudimos cargar los 43 parámetros de negocio."));
    } finally {
      setCargando(false);
    }
  }, [token]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const guardarParametro = useCallback(async (item: ParametroItem): Promise<void> => {
    setError(null);
    setExito(null);
    setGuardandoClave(item.clave);
    try {
      const texto = (borradores[item.clave] ?? "").trim();
      let valorParseado: unknown = texto;
      if (item.tipo === "int") {
        valorParseado = Number.parseInt(texto, 10);
      } else if (item.tipo === "float" || item.tipo === "number") {
        valorParseado = Number.parseFloat(texto);
      } else {
        try {
          valorParseado = JSON.parse(texto);
        } catch {
          valorParseado = texto;
        }
      }

      const res = await clienteModeracion.actualizarParametros(token, {
        [item.clave]: valorParseado,
      });
      setParametros(res.datos);
      setExito(`Parámetro ${item.clave} actualizado y auditado.`);
    } catch (err) {
      setError(extraerInfoError(err, `Error al actualizar ${item.clave}.`));
    } finally {
      setGuardandoClave(null);
    }
  }, [borradores, token]);

  const filtrados = useMemo(() => {
    const q = filtro.trim().toLowerCase();
    if (!q) {
      return parametros;
    }
    return parametros.filter(
      (p) =>
        p.clave.toLowerCase().includes(q) ||
        p.descripcion.toLowerCase().includes(q)
    );
  }, [filtro, parametros]);

  const columnas = useMemo(
    () =>
      crearColumnasParametros(
        borradores,
        guardandoClave,
        (clave, valor) => setBorradores((prev) => ({ ...prev, [clave]: valor })),
        (item) => void guardarParametro(item)
      ),
    [borradores, guardandoClave, guardarParametro]
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-300 bg-superficie p-4">
        <p className="text-sm font-semibold text-slate-800">
          Total parámetros activos: {parametros.length}
        </p>
        <div className="w-full sm:w-72">
          <label htmlFor="buscar-parametro" className="sr-only">
            Filtrar parámetros
          </label>
          <input
            id="buscar-parametro"
            type="search"
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
            placeholder="Filtrar por clave o descripción..."
            className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
          />
        </div>
      </div>

      {exito && (
        <output className="flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-950">
          <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
          {exito}
        </output>
      )}

      {error && <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />}

      <TablaGestion
        columnas={columnas}
        datos={filtrados}
        cargando={cargando}
        vacioTexto="No se encontraron parámetros con ese filtro"
        claveFila={(p) => p.clave}
        etiquetaTabla="Los 43 parámetros de negocio"
      />
    </div>
  );
}

