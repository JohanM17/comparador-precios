"use client";

import React, { useCallback, useEffect, useState } from "react";
import { clienteModeracion, type ItemAuditoria } from "@/lib/api/clienteModeracion";
import {
  extraerInfoError,
  formatearFechaBogota,
  type InfoErrorVisible,
} from "@/lib/formato";
import EstadoError from "@/components/EstadoError";
import TablaGestion, { type ColumnaTablaGestion } from "@/components/TablaGestion";

const LIMITE = 25;

const COLUMNAS_AUDITORIA: readonly ColumnaTablaGestion<ItemAuditoria>[] = [
  {
    clave: "fecha",
    encabezado: "Fecha",
    celda: (a) => (
      <span className="text-xs text-slate-600">{formatearFechaBogota(a.creado_en)}</span>
    ),
  },
  {
    clave: "accion",
    encabezado: "Acción / Entidad",
    celda: (a) => (
      <div>
        <p className="font-semibold text-slate-900">{a.accion}</p>
        <p className="text-xs text-slate-500">
          {a.entidad} {a.entidad_id ? `(${a.entidad_id.slice(0, 8)})` : ""}
        </p>
      </div>
    ),
  },
  {
    clave: "actor",
    encabezado: "Actor",
    celda: (a) => (
      <span className="text-xs text-slate-700">
        {a.rol ?? "sistema"} · {a.actor_id ? a.actor_id.slice(0, 8) : "-"}
      </span>
    ),
  },
  {
    clave: "cambio",
    encabezado: "Antes / Después",
    celda: (a) => (
      <details className="text-xs">
        <summary className="cursor-pointer font-semibold text-emerald-800">Ver JSON</summary>
        <pre className="mt-1 max-w-xs overflow-auto rounded bg-slate-900 p-2 text-[11px] text-slate-100">
          {JSON.stringify({ antes: a.antes, despues: a.despues }, null, 2)}
        </pre>
      </details>
    ),
  },
];

export interface PestanaAuditoriaProps {
  readonly token: string;
}

/**
 * Pestana Moderador: bitacora inmutable append-only (GET /v1/moderacion/auditoria).
 */
export default function PestanaAuditoria({
  token,
}: PestanaAuditoriaProps): React.JSX.Element {
  const [entidad, setEntidad] = useState("");
  const [accion, setAccion] = useState("");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<ItemAuditoria[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const res = await clienteModeracion.listarAuditoria(token, {
        entidad: entidad.trim() || null,
        accion: accion.trim() || null,
        limite: LIMITE,
        offset,
      });
      setItems(res.datos);
      setTotal(res.total);
    } catch (err) {
      setError(extraerInfoError(err, "No pudimos consultar la bitácora de auditoría."));
    } finally {
      setCargando(false);
    }
  }, [accion, entidad, offset, token]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 rounded-2xl border border-slate-300 bg-superficie p-4">
        <div>
          <label htmlFor="filtro-entidad-aud" className="block text-xs font-semibold text-slate-600">
            Entidad
          </label>
          <input
            id="filtro-entidad-aud"
            type="search"
            value={entidad}
            onChange={(e) => {
              setOffset(0);
              setEntidad(e.target.value);
            }}
            placeholder="caso_moderacion, config_parametro..."
            className="mt-1 min-h-11 rounded-xl border border-slate-300 px-3 text-sm"
          />
        </div>
        <div>
          <label htmlFor="filtro-accion-aud" className="block text-xs font-semibold text-slate-600">
            Acción
          </label>
          <input
            id="filtro-accion-aud"
            type="search"
            value={accion}
            onChange={(e) => {
              setOffset(0);
              setAccion(e.target.value);
            }}
            placeholder="resolver_caso..."
            className="mt-1 min-h-11 rounded-xl border border-slate-300 px-3 text-sm"
          />
        </div>
      </div>

      {error && <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />}

      <TablaGestion
        columnas={COLUMNAS_AUDITORIA}
        datos={items}
        cargando={cargando}
        vacioTexto="Sin registros en auditoría"
        claveFila={(a) => String(a.id)}
        tieneAnterior={offset > 0}
        onAnterior={() => setOffset((o) => Math.max(0, o - LIMITE))}
        siguienteCursor={offset + LIMITE < total ? String(offset + LIMITE) : null}
        onSiguiente={() => setOffset((o) => o + LIMITE)}
        etiquetaTabla="Bitácora inmutable de auditoría"
      />
    </div>
  );
}

