"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, X } from "lucide-react";
import { clienteApi, type ProductoResumen } from "@/lib/api/clienteApi";
import { clienteReportes } from "@/lib/api/clienteReportes";
import { obtenerTokenAcceso } from "@/lib/auth/supabase";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";

export interface ModalSugerirPresentacionProps {
  readonly abierto: boolean;
  readonly productosIniciales: readonly ProductoResumen[];
  readonly onCerrar: () => void;
}

const UNIDADES_ENTRADA = ["g", "kg", "lb", "ml", "l", "unidad", "docena"] as const;

/**
 * Modal ligero para sugerir una presentacion faltante hacia POST /v1/sugerencias-presentacion.
 */
export default function ModalSugerirPresentacion({
  abierto,
  productosIniciales,
  onCerrar,
}: ModalSugerirPresentacionProps): React.JSX.Element | null {
  const [productos, setProductos] = useState<readonly ProductoResumen[]>(productosIniciales);
  const [productoId, setProductoId] = useState(productosIniciales[0]?.id ?? "");
  const [textoLibre, setTextoLibre] = useState("");
  const [marca, setMarca] = useState("");
  const [valorCantidad, setValorCantidad] = useState("");
  const [unidad, setUnidad] = useState<(typeof UNIDADES_ENTRADA)[number]>("g");
  const [codigoBarras, setCodigoBarras] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [exito, setExito] = useState<string | null>(null);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  useEffect(() => {
    if (!abierto) {
      return;
    }
    if (productosIniciales.length > 0) {
      setProductos(productosIniciales);
      if (!productoId) {
        setProductoId(productosIniciales[0].id);
      }
      return;
    }
    void clienteApi
      .buscarProductos({ limite: 24 })
      .then((res) => {
        setProductos(res.datos);
        if (res.datos.length > 0) {
          setProductoId(res.datos[0].id);
        }
      })
      .catch(() => {});
  }, [abierto, productoId, productosIniciales]);

  if (!abierto) {
    return null;
  }

  const enviar = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const token = await obtenerTokenAcceso();
      if (!token) {
        setError({ detalle: "Debes iniciar sesión en /ingresar para enviar sugerencias." });
        return;
      }
      const cantidadNum = valorCantidad.trim() ? Number(valorCantidad.replace(",", ".")) : null;
      const res = await clienteReportes.sugerirPresentacion(token, {
        producto_id: productoId,
        texto_libre: textoLibre.trim(),
        marca: marca.trim() || null,
        valor_cantidad: cantidadNum && !Number.isNaN(cantidadNum) ? cantidadNum : null,
        unidad: cantidadNum ? unidad : null,
        codigo_barras: codigoBarras.trim() || null,
      });
      setExito(res.mensaje);
      setTextoLibre("");
      setMarca("");
      setValorCantidad("");
      setCodigoBarras("");
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible enviar la sugerencia de presentación."));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <dialog
      open
      aria-modal="true"
      aria-labelledby="titulo-sugerencia-pres"
      className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center border-0 bg-black/60 p-4"
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-300 bg-superficie p-5 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <h2 id="titulo-sugerencia-pres" className="text-lg font-bold text-slate-900">
            Sugerir presentación faltante
          </h2>
          <button
            type="button"
            onClick={onCerrar}
            aria-label="Cerrar ventana de sugerencia"
            className="min-h-11 min-w-11 rounded-lg p-2 text-slate-500 hover:bg-slate-100"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {exito ? (
          <div className="mt-4 space-y-4">
            <output className="flex items-start gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-950">
              <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-700" aria-hidden="true" />
              <span>{exito}</span>
            </output>
            <button
              type="button"
              onClick={() => {
                setExito(null);
                onCerrar();
              }}
              className="min-h-11 w-full rounded-xl bg-bosque-800 px-4 text-sm font-semibold text-white"
            >
              Volver al reporte
            </button>
          </div>
        ) : (
          <form onSubmit={(e) => void enviar(e)} className="mt-4 space-y-3">
            {error && <EstadoError detalle={error.detalle} codigo={error.codigo} />}

            <div>
              <label htmlFor="sug-producto" className="block text-xs font-semibold text-slate-700">
                Producto base
              </label>
              <select
                id="sug-producto"
                required
                value={productoId}
                onChange={(e) => setProductoId(e.target.value)}
                className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
              >
                {productos.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="sug-texto" className="block text-xs font-semibold text-slate-700">
                Descripción de la presentación (ej. Bolsa x 900 g marca X)
              </label>
              <input
                id="sug-texto"
                required
                minLength={3}
                maxLength={200}
                value={textoLibre}
                onChange={(e) => setTextoLibre(e.target.value)}
                className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor="sug-cant" className="block text-xs font-semibold text-slate-700">
                  Cantidad (opcional)
                </label>
                <input
                  id="sug-cant"
                  inputMode="decimal"
                  value={valorCantidad}
                  onChange={(e) => setValorCantidad(e.target.value)}
                  placeholder="900"
                  className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
                />
              </div>
              <div>
                <label htmlFor="sug-unidad" className="block text-xs font-semibold text-slate-700">
                  Unidad
                </label>
                <select
                  id="sug-unidad"
                  value={unidad}
                  onChange={(e) =>
                    setUnidad(e.target.value as (typeof UNIDADES_ENTRADA)[number])
                  }
                  className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
                >
                  {UNIDADES_ENTRADA.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor="sug-marca" className="block text-xs font-semibold text-slate-700">
                  Marca (opcional)
                </label>
                <input
                  id="sug-marca"
                  value={marca}
                  onChange={(e) => setMarca(e.target.value)}
                  className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
                />
              </div>
              <div>
                <label htmlFor="sug-ean" className="block text-xs font-semibold text-slate-700">
                  Código barras (opcional)
                </label>
                <input
                  id="sug-ean"
                  inputMode="numeric"
                  value={codigoBarras}
                  onChange={(e) => setCodigoBarras(e.target.value)}
                  placeholder="7701234567890"
                  className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={enviando || !productoId}
              className="min-h-11 w-full rounded-xl bg-bosque-800 px-4 text-sm font-semibold text-white hover:bg-bosque-900 disabled:opacity-50"
            >
              {enviando ? "Enviando..." : "Enviar sugerencia"}
            </button>
          </form>
        )}
      </div>
    </dialog>
  );
}

