"use client";

import React from "react";

export interface CampoPrecioProps {
  readonly valor: string;
  readonly onChange: (digitosCrudos: string, precioCop: number | null) => void;
  readonly error?: string | null;
}

const FORMATEADOR_MILES = new Intl.NumberFormat("es-CO", {
  maximumFractionDigits: 0,
});

function extraerDigitos(entrada: string): string {
  return entrada.replace(/\D+/g, "").slice(0, 8);
}

/**
 * Control tactil numerico para capturar el precio total en COP (min-h-11).
 * Formatea separadores de miles en vivo y exige declaracion con IVA incluido.
 */
export default function CampoPrecio({
  valor,
  onChange,
  error,
}: CampoPrecioProps): React.JSX.Element {
  const digitos = extraerDigitos(valor);
  const numero = digitos ? Number.parseInt(digitos, 10) : null;
  const textoFormateado = numero !== null ? FORMATEADOR_MILES.format(numero) : "";

  const manejarCambio = (ev: React.ChangeEvent<HTMLInputElement>): void => {
    const limpios = extraerDigitos(ev.target.value);
    const parsed = limpios ? Number.parseInt(limpios, 10) : null;
    onChange(limpios, parsed);
  };

  return (
    <div className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <label htmlFor="campo-precio-cop" className="block text-sm font-bold text-slate-900">
        3. Precio observado en góndola
      </label>

      <div className="relative flex items-center">
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-4 text-xl font-black text-emerald-800"
        >
          $
        </span>
        <input
          id="campo-precio-cop"
          name="precio_cop"
          type="text"
          inputMode="numeric"
          autoComplete="off"
          required
          aria-describedby="ayuda-precio-iva"
          aria-invalid={Boolean(error)}
          value={textoFormateado}
          onChange={manejarCambio}
          placeholder="2.600"
          className={`min-h-14 w-full rounded-xl border py-3 pl-10 pr-16 text-2xl font-extrabold tracking-tight text-slate-900 focus:outline-none focus:ring-2 ${
            error
              ? "border-rose-500 bg-rose-50/40 focus:border-rose-600 focus:ring-rose-600/20"
              : "border-slate-300 bg-slate-50 focus:border-emerald-700 focus:bg-white focus:ring-emerald-700/20"
          }`}
        />
        <span className="pointer-events-none absolute right-4 text-xs font-bold text-slate-500">
          COP
        </span>
      </div>

      <p id="ayuda-precio-iva" className="text-xs font-medium text-slate-600">
        Precio en pesos colombianos (COP), con IVA e impuestos incluidos
      </p>

      {error && (
        <p role="alert" className="text-xs font-semibold text-rose-700">
          {error}
        </p>
      )}
    </div>
  );
}

