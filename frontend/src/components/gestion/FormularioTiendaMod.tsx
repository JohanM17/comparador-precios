"use client";

import React, { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { clienteModeracion } from "@/lib/api/clienteModeracion";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";

const TIPOS_TIENDA = ["tienda_barrio", "minimercado", "supermercado", "cadena"] as const;

export interface FormularioTiendaModProps {
  readonly token: string;
}

/**
 * Formulario de moderacion para dar de alta establecimientos georreferenciados.
 */
export default function FormularioTiendaMod({
  token,
}: FormularioTiendaModProps): React.JSX.Element {
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState<(typeof TIPOS_TIENDA)[number]>("tienda_barrio");
  const [direccion, setDireccion] = useState("");
  const [barrio, setBarrio] = useState("");
  const [lat, setLat] = useState("4.5339");
  const [lng, setLng] = useState("-75.6811");
  const [enviando, setEnviando] = useState(false);
  const [exito, setExito] = useState<string | null>(null);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  const crear = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setError(null);
    setExito(null);
    setEnviando(true);
    try {
      await clienteModeracion.crearEstablecimiento(token, {
        nombre: nombre.trim(),
        tipo,
        direccion: direccion.trim(),
        barrio: barrio.trim() || null,
        municipio: "Armenia",
        departamento: "Quindío",
        lat: Number.parseFloat(lat),
        lng: Number.parseFloat(lng),
        activo: true,
      });
      setExito(`Establecimiento "${nombre.trim()}" creado y auditado.`);
      setNombre("");
      setDireccion("");
      setBarrio("");
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible crear el establecimiento."));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form
      onSubmit={(e) => void crear(e)}
      className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h3 className="text-base font-bold text-slate-900">Nuevo establecimiento</h3>

      {exito && (
        <output className="flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-xs font-semibold text-emerald-950">
          <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
          {exito}
        </output>
      )}
      {error && <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="mod-tienda-nombre" className="block text-xs font-semibold text-slate-700">
            Nombre
          </label>
          <input
            id="mod-tienda-nombre"
            required
            minLength={2}
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
          />
        </div>
        <div>
          <label htmlFor="mod-tienda-tipo" className="block text-xs font-semibold text-slate-700">
            Tipo
          </label>
          <select
            id="mod-tienda-tipo"
            value={tipo}
            onChange={(e) => setTipo(e.target.value as (typeof TIPOS_TIENDA)[number])}
            className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
          >
            {TIPOS_TIENDA.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="mod-tienda-dir" className="block text-xs font-semibold text-slate-700">
            Dirección
          </label>
          <input
            id="mod-tienda-dir"
            required
            minLength={3}
            value={direccion}
            onChange={(e) => setDireccion(e.target.value)}
            className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
          />
        </div>
        <div>
          <label htmlFor="mod-tienda-barrio" className="block text-xs font-semibold text-slate-700">
            Barrio (opcional)
          </label>
          <input
            id="mod-tienda-barrio"
            value={barrio}
            onChange={(e) => setBarrio(e.target.value)}
            className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
          />
        </div>
        <div>
          <label htmlFor="mod-tienda-lat" className="block text-xs font-semibold text-slate-700">
            Latitud
          </label>
          <input
            id="mod-tienda-lat"
            required
            value={lat}
            onChange={(e) => setLat(e.target.value)}
            className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
          />
        </div>
        <div>
          <label htmlFor="mod-tienda-lng" className="block text-xs font-semibold text-slate-700">
            Longitud
          </label>
          <input
            id="mod-tienda-lng"
            required
            value={lng}
            onChange={(e) => setLng(e.target.value)}
            className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={enviando}
        className="min-h-11 rounded-xl bg-emerald-700 px-5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
      >
        {enviando ? "Creando..." : "Crear establecimiento"}
      </button>
    </form>
  );
}

