"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, Search } from "lucide-react";
import { clienteApi, type Categoria, type ProductoResumen } from "@/lib/api/clienteApi";
import { clienteModeracion } from "@/lib/api/clienteModeracion";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";
import FormularioTiendaMod from "@/components/gestion/FormularioTiendaMod";

const UNIDADES_BASE = ["g", "ml", "unidad"] as const;
const UNIDADES_ENTRADA = ["g", "kg", "lb", "ml", "l", "unidad", "docena"] as const;

export interface PestanaCatalogoTiendasProps {
  readonly token: string;
}

/**
 * Pestana Moderador: alta/edicion de productos, presentaciones (con Open Food Facts) y tiendas.
 */
export default function PestanaCatalogoTiendas({
  token,
}: PestanaCatalogoTiendasProps): React.JSX.Element {
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [productos, setProductos] = useState<ProductoResumen[]>([]);
  const [exito, setExito] = useState<string | null>(null);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  const [prodNombre, setProdNombre] = useState("");
  const [prodCatId, setProdCatId] = useState(1);
  const [prodUnidad, setProdUnidad] = useState<(typeof UNIDADES_BASE)[number]>("g");

  const [presProdId, setPresProdId] = useState("");
  const [presMarca, setPresMarca] = useState("");
  const [presValor, setPresValor] = useState("500");
  const [presUnidad, setPresUnidad] = useState<(typeof UNIDADES_ENTRADA)[number]>("g");
  const [presMult, setPresMult] = useState(1);
  const [presEan, setPresEan] = useState("");
  const [fuenteCat, setFuenteCat] = useState<"manual" | "open_food_facts">("manual");
  const [offInfo, setOffInfo] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([
      clienteApi.listarCategorias(),
      clienteApi.buscarProductos({ limite: 50 }),
    ])
      .then(([cats, prods]) => {
        setCategorias(cats);
        setProductos(prods.datos);
        if (prods.datos.length > 0) {
          setPresProdId(prods.datos[0].id);
        }
      })
      .catch(() => {});
  }, []);

  const crearProducto = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setError(null);
    setExito(null);
    try {
      await clienteModeracion.crearProducto(token, {
        nombre: prodNombre.trim(),
        categoria_id: prodCatId,
        unidad_base: prodUnidad,
      });
      setExito(`Producto "${prodNombre.trim()}" creado correctamente.`);
      setProdNombre("");
      const lista = await clienteApi.buscarProductos({ limite: 50 });
      setProductos(lista.datos);
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible crear el producto."));
    }
  };

  const consultarOff = async (): Promise<void> => {
    setError(null);
    setOffInfo(null);
    try {
      const res = await clienteModeracion.consultarCatalogoExterno(token, presEan.trim());
      if (!res.encontrado || !res.producto) {
        setOffInfo("Código de barras no encontrado en Open Food Facts.");
        return;
      }
      const marcaExt = typeof res.producto.marca === "string" ? res.producto.marca : "";
      const nombreExt = typeof res.producto.nombre === "string" ? res.producto.nombre : "";
      if (marcaExt) {
        setPresMarca(marcaExt);
      }
      setFuenteCat("open_food_facts");
      const sufijoMarca = marcaExt ? ` (${marcaExt})` : "";
      setOffInfo(`Open Food Facts: ${nombreExt}${sufijoMarca}`);
    } catch (err) {
      setError(extraerInfoError(err, "Error consultando Open Food Facts."));
    }
  };

  const crearPresentacion = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setError(null);
    setExito(null);
    try {
      await clienteModeracion.crearPresentacion(token, {
        producto_id: presProdId,
        marca: presMarca.trim() || null,
        valor_cantidad: Number(presValor.replace(",", ".")),
        unidad: presUnidad,
        multiplicador: presMult,
        codigo_barras: presEan.trim() || null,
        fuente_catalogo: fuenteCat,
      });
      setExito("Presentación creada con cantidad_base calculada en el dominio.");
      setPresMarca("");
      setPresEan("");
      setFuenteCat("manual");
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible crear la presentación."));
    }
  };

  return (
    <div className="space-y-6">
      {exito && (
        <output className="flex items-center gap-2 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-950">
          <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
          {exito}
        </output>
      )}
      {error && <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />}

      <form onSubmit={(e) => void crearProducto(e)} className="space-y-3 rounded-2xl border border-slate-300 bg-superficie p-5">
        <h3 className="text-base font-bold text-slate-900">Nuevo producto</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor="mod-prod-nombre" className="block text-xs font-semibold text-slate-700">Nombre</label>
            <input id="mod-prod-nombre" required minLength={2} value={prodNombre} onChange={(e) => setProdNombre(e.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm" />
          </div>
          <div>
            <label htmlFor="mod-prod-cat" className="block text-xs font-semibold text-slate-700">Categoría</label>
            <select id="mod-prod-cat" value={prodCatId} onChange={(e) => setProdCatId(Number(e.target.value))} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm">
              {categorias.map((c) => (<option key={c.id} value={c.id}>{c.nombre}</option>))}
            </select>
          </div>
          <div>
            <label htmlFor="mod-prod-ubase" className="block text-xs font-semibold text-slate-700">Unidad base</label>
            <select id="mod-prod-ubase" value={prodUnidad} onChange={(e) => setProdUnidad(e.target.value as (typeof UNIDADES_BASE)[number])} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm">
              {UNIDADES_BASE.map((u) => (<option key={u} value={u}>{u}</option>))}
            </select>
          </div>
        </div>
        <button type="submit" className="min-h-11 rounded-full bg-bosque-800 px-5 text-sm font-semibold text-white hover:bg-bosque-900">
          Crear producto
        </button>
      </form>

      <form onSubmit={(e) => void crearPresentacion(e)} className="space-y-3 rounded-2xl border border-slate-300 bg-superficie p-5">
        <h3 className="text-base font-bold text-slate-900">Nueva presentación (+ Open Food Facts)</h3>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="mod-pres-ean" className="block text-xs font-semibold text-slate-700">Código de barras (opcional)</label>
            <input id="mod-pres-ean" inputMode="numeric" value={presEan} onChange={(e) => setPresEan(e.target.value)} placeholder="7702001001234" className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm" />
          </div>
          <button type="button" onClick={() => void consultarOff()} disabled={!presEan.trim()} className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-emerald-700 bg-emerald-50 px-4 text-xs font-semibold text-emerald-900 disabled:opacity-50">
            <Search className="h-3.5 w-3.5" aria-hidden="true" />
            Consultar Open Food Facts
          </button>
        </div>
        {offInfo && <p className="text-xs font-semibold text-emerald-800">{offInfo}</p>}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <div>
            <label htmlFor="mod-pres-prod" className="block text-xs font-semibold text-slate-700">Producto</label>
            <select id="mod-pres-prod" required value={presProdId} onChange={(e) => setPresProdId(e.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm">
              {productos.map((p) => (<option key={p.id} value={p.id}>{p.nombre}</option>))}
            </select>
          </div>
          <div>
            <label htmlFor="mod-pres-marca" className="block text-xs font-semibold text-slate-700">Marca</label>
            <input id="mod-pres-marca" value={presMarca} onChange={(e) => setPresMarca(e.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm" />
          </div>
          <div>
            <label htmlFor="mod-pres-cant" className="block text-xs font-semibold text-slate-700">Cantidad</label>
            <input id="mod-pres-cant" required value={presValor} onChange={(e) => setPresValor(e.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="mod-pres-uni" className="block text-xs font-semibold text-slate-700">Unidad</label>
              <select id="mod-pres-uni" value={presUnidad} onChange={(e) => setPresUnidad(e.target.value as (typeof UNIDADES_ENTRADA)[number])} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-2 text-sm">
                {UNIDADES_ENTRADA.map((u) => (<option key={u} value={u}>{u}</option>))}
              </select>
            </div>
            <div>
              <label htmlFor="mod-pres-mult" className="block text-xs font-semibold text-slate-700">Mult.</label>
              <input id="mod-pres-mult" type="number" min={1} value={presMult} onChange={(e) => setPresMult(Number(e.target.value))} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-2 text-sm" />
            </div>
          </div>
        </div>
        <button type="submit" disabled={!presProdId} className="min-h-11 rounded-full bg-bosque-800 px-5 text-sm font-semibold text-white hover:bg-bosque-900 disabled:opacity-50">
          Crear presentación
        </button>
      </form>

      <FormularioTiendaMod token={token} />
    </div>
  );
}

