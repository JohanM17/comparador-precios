"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Megaphone } from "lucide-react";
import { clienteApi, type ProductoResumen } from "@/lib/api/clienteApi";
import {
  clienteComercio,
  type EstablecimientoComercio,
  type PromocionRespuesta,
} from "@/lib/api/clienteComercio";
import { extraerInfoError, formatearFechaBogota, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";

export interface PestanaPromocionesProps {
  readonly token: string;
  readonly tiendas: readonly EstablecimientoComercio[];
}

type TipoPromocion = "porcentaje" | "precio_especial" | "pague_x_lleve_y";

const TIPOS: readonly { readonly valor: TipoPromocion; readonly etiqueta: string }[] = [
  { valor: "porcentaje", etiqueta: "Porcentaje de descuento" },
  { valor: "precio_especial", etiqueta: "Precio promocional" },
  { valor: "pague_x_lleve_y", etiqueta: "Pague X y lleve Y" },
];

function hoyIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Pestaña «Promociones» de S6.
 *
 * Una promoción es contenido comercial: aparece en su propio bloque de la
 * ficha de producto y no entra en el orden de la comparación (`EC-06`). La
 * pantalla lo dice antes de que el comercio escriba nada, para que nadie
 * publique esperando subir posiciones.
 *
 * Las condiciones y la vigencia son obligatorias porque las exige el
 * artículo 33 de la Ley 1480, no porque queden bonitas.
 */
export default function PestanaPromociones({
  token,
  tiendas,
}: PestanaPromocionesProps): React.JSX.Element {
  const primeraTienda = tiendas[0];
  const [tiendaId, setTiendaId] = useState<string>(primeraTienda ? primeraTienda.id : "");
  const [promociones, setPromociones] = useState<readonly PromocionRespuesta[]>([]);
  const [productos, setProductos] = useState<readonly ProductoResumen[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<InfoErrorVisible | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  const [productoId, setProductoId] = useState("");
  const [titulo, setTitulo] = useState("");
  const [tipo, setTipo] = useState<TipoPromocion>("porcentaje");
  const [porcentaje, setPorcentaje] = useState("10");
  const [precioEspecial, setPrecioEspecial] = useState("");
  const [pagueX, setPagueX] = useState("2");
  const [lleveY, setLleveY] = useState("3");
  const [condiciones, setCondiciones] = useState("");
  const [desde, setDesde] = useState(hoyIso());
  const [hasta, setHasta] = useState("");
  const [hastaRevocar, setHastaRevocar] = useState(false);
  const [enviando, setEnviando] = useState(false);

  const cargar = useCallback(async (): Promise<void> => {
    if (!tiendaId) {
      return;
    }
    setCargando(true);
    setError(null);
    try {
      const [lista, cat] = await Promise.all([
        clienteComercio.listarPromociones(token, tiendaId),
        clienteApi.buscarProductos({ limite: 50 }),
      ]);
      setPromociones(lista);
      setProductos(cat.datos);
      if (cat.datos.length > 0 && cat.datos[0] && !productoId) {
        setProductoId(cat.datos[0].id);
      }
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible cargar las promociones."));
    } finally {
      setCargando(false);
    }
  }, [token, tiendaId, productoId]);

  useEffect(() => {
    void cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, tiendaId]);

  const crear = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setError(null);
    setExito(null);
    setEnviando(true);
    try {
      await clienteComercio.crearPromocion(token, tiendaId, {
        producto_id: productoId,
        presentacion_id: null,
        titulo: titulo.trim(),
        tipo,
        porcentaje_descuento: tipo === "porcentaje" ? Number(porcentaje) : null,
        precio_especial_cop: tipo === "precio_especial" ? Number(precioEspecial) : null,
        pague_x: tipo === "pague_x_lleve_y" ? Number(pagueX) : null,
        lleve_y: tipo === "pague_x_lleve_y" ? Number(lleveY) : null,
        condiciones: condiciones.trim(),
        vigente_desde: new Date(`${desde}T00:00:00`).toISOString(),
        vigente_hasta: hastaRevocar || !hasta ? null : new Date(`${hasta}T23:59:59`).toISOString(),
        hasta_revocar: hastaRevocar,
      });
      setExito("Promoción publicada. Aparece en su bloque aparte y no cambia el orden.");
      setTitulo("");
      setCondiciones("");
      await cargar();
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible publicar la promoción."));
    } finally {
      setEnviando(false);
    }
  };

  const revocar = async (promocionId: string): Promise<void> => {
    setError(null);
    setExito(null);
    try {
      await clienteComercio.revocarPromocion(token, tiendaId, promocionId);
      setExito("Promoción revocada. Deja de mostrarse, pero queda su registro.");
      await cargar();
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible revocar la promoción."));
    }
  };

  if (tiendas.length === 0) {
    return (
      <p className="text-[13.5px] text-slate-500">
        Necesitas un establecimiento verificado para publicar promociones.
      </p>
    );
  }

  return (
    <div className="space-y-10">
      <section aria-labelledby="titulo-promos">
        <h2 id="titulo-promos" className="rotulo mb-1.5">
          Promociones
        </h2>
        <p className="max-w-[62ch] text-[13.5px] leading-relaxed text-slate-500">
          Una promoción se muestra en su propio bloque, marcada como contenido comercial, y{" "}
          <strong>no altera el orden de la comparación</strong>. Las condiciones y la vigencia son
          obligatorias: las exige el artículo 33 de la Ley 1480.
        </p>
      </section>

      {tiendas.length > 1 && (
        <div className="sm:max-w-md">
          <label htmlFor="tienda-promos" className="block text-[12.5px] font-medium text-slate-500">
            Establecimiento
          </label>
          <select
            id="tienda-promos"
            value={tiendaId}
            onChange={(ev) => setTiendaId(ev.target.value)}
            className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
          >
            {tiendas.map((t) => (
              <option key={t.id} value={t.id}>
                {t.nombre}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <EstadoError detalle={error.detalle} codigo={error.codigo} requestId={error.requestId} />
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

      <section aria-labelledby="titulo-promos-vigentes">
        <h3 id="titulo-promos-vigentes" className="rotulo mb-3">
          Publicadas
        </h3>
        {cargando && <p className="rotulo">Cargando…</p>}
        {!cargando && promociones.length === 0 && (
          <p className="text-[13.5px] text-slate-500">Todavía no has publicado ninguna.</p>
        )}
        {!cargando && promociones.length > 0 && (
          <ul className="border-t border-slate-200">
            {promociones.map((promo) => (
              <li
                key={promo.id}
                className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-b border-slate-200 py-4"
              >
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-[15px] font-medium tracking-[-0.015em] text-slate-900">
                    <Megaphone className="h-3.5 w-3.5 flex-shrink-0 text-slate-500" aria-hidden="true" />
                    {promo.titulo}
                  </p>
                  <p className="mt-1 max-w-[58ch] text-[12.5px] leading-relaxed text-slate-600">
                    {promo.condiciones}
                  </p>
                  <p className="cifras mt-1 text-[12.5px] text-slate-500">
                    Desde {formatearFechaBogota(promo.vigente_desde)}
                    {promo.hasta_revocar
                      ? " · hasta revocar"
                      : promo.vigente_hasta
                        ? ` · hasta ${formatearFechaBogota(promo.vigente_hasta)}`
                        : ""}
                    {!promo.vigente && " · fuera de vigencia"}
                  </p>
                </div>
                {promo.activa && (
                  <button
                    type="button"
                    onClick={() => void revocar(promo.id)}
                    className="min-h-11 flex-none text-[13.5px] text-cereza-600 underline decoration-cereza-300 underline-offset-4 transition-colors hover:decoration-cereza-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
                  >
                    Revocar
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="titulo-promo-nueva">
        <h3 id="titulo-promo-nueva" className="rotulo mb-5">
          Publicar una promoción
        </h3>
        <form onSubmit={(ev) => void crear(ev)} className="space-y-5 sm:max-w-xl">
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label htmlFor="promo-producto" className="block text-[12.5px] font-medium text-slate-500">
                Producto
              </label>
              <select
                id="promo-producto"
                required
                value={productoId}
                onChange={(ev) => setProductoId(ev.target.value)}
                className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
              >
                {productos.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="promo-tipo" className="block text-[12.5px] font-medium text-slate-500">
                Tipo
              </label>
              <select
                id="promo-tipo"
                value={tipo}
                onChange={(ev) => setTipo(ev.target.value as TipoPromocion)}
                className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
              >
                {TIPOS.map((t) => (
                  <option key={t.valor} value={t.valor}>
                    {t.etiqueta}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="promo-titulo" className="block text-[12.5px] font-medium text-slate-500">
              Título
            </label>
            <input
              id="promo-titulo"
              required
              minLength={5}
              maxLength={120}
              value={titulo}
              onChange={(ev) => setTitulo(ev.target.value)}
              className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
            />
          </div>

          {tipo === "porcentaje" && (
            <div className="sm:max-w-[12rem]">
              <label htmlFor="promo-porcentaje" className="block text-[12.5px] font-medium text-slate-500">
                Descuento (%)
              </label>
              <input
                id="promo-porcentaje"
                type="number"
                min={1}
                max={90}
                required
                value={porcentaje}
                onChange={(ev) => setPorcentaje(ev.target.value)}
                className="cifras mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
              />
            </div>
          )}

          {tipo === "precio_especial" && (
            <div className="sm:max-w-[14rem]">
              <label htmlFor="promo-precio" className="block text-[12.5px] font-medium text-slate-500">
                Precio promocional (COP)
              </label>
              <input
                id="promo-precio"
                type="number"
                min={1}
                required
                value={precioEspecial}
                onChange={(ev) => setPrecioEspecial(ev.target.value)}
                className="cifras mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
              />
            </div>
          )}

          {tipo === "pague_x_lleve_y" && (
            <div className="grid gap-5 sm:max-w-[20rem] sm:grid-cols-2">
              <div>
                <label htmlFor="promo-pague" className="block text-[12.5px] font-medium text-slate-500">
                  Pague
                </label>
                <input
                  id="promo-pague"
                  type="number"
                  min={1}
                  required
                  value={pagueX}
                  onChange={(ev) => setPagueX(ev.target.value)}
                  className="cifras mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
                />
              </div>
              <div>
                <label htmlFor="promo-lleve" className="block text-[12.5px] font-medium text-slate-500">
                  Lleve
                </label>
                <input
                  id="promo-lleve"
                  type="number"
                  min={2}
                  required
                  value={lleveY}
                  onChange={(ev) => setLleveY(ev.target.value)}
                  className="cifras mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
                />
              </div>
            </div>
          )}

          <div>
            <label htmlFor="promo-condiciones" className="block text-[12.5px] font-medium text-slate-500">
              Condiciones
            </label>
            <textarea
              id="promo-condiciones"
              required
              minLength={10}
              maxLength={500}
              rows={2}
              value={condiciones}
              onChange={(ev) => setCondiciones(ev.target.value)}
              placeholder="Válido solo los viernes, máximo 3 unidades por persona…"
              className="mt-1 w-full resize-y border-0 border-b border-slate-300 bg-transparent px-0 py-2 text-[15px] text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-0"
            />
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label htmlFor="promo-desde" className="block text-[12.5px] font-medium text-slate-500">
                Vigente desde
              </label>
              <input
                id="promo-desde"
                type="date"
                required
                value={desde}
                onChange={(ev) => setDesde(ev.target.value)}
                className="cifras mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
              />
            </div>
            <div>
              <label htmlFor="promo-hasta" className="block text-[12.5px] font-medium text-slate-500">
                Hasta
              </label>
              <input
                id="promo-hasta"
                type="date"
                disabled={hastaRevocar}
                value={hasta}
                onChange={(ev) => setHasta(ev.target.value)}
                className="cifras mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0 disabled:opacity-50"
              />
            </div>
          </div>

          <label className="flex items-center gap-2.5 text-[13.5px] text-slate-700">
            <input
              type="checkbox"
              checked={hastaRevocar}
              onChange={(ev) => setHastaRevocar(ev.target.checked)}
              className="h-4 w-4 rounded border-slate-400 text-emerald-600 focus:ring-emerald-600"
            />
            Válida hasta que yo la revoque
          </label>

          <button
            type="submit"
            disabled={enviando}
            className="inline-flex min-h-11 items-center justify-center rounded-full bg-brasa-600 px-5 text-[13.5px] font-medium text-slate-50 transition-colors hover:bg-brasa-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:opacity-50"
          >
            {enviando ? "Publicando…" : "Publicar promoción"}
          </button>
        </form>
      </section>
    </div>
  );
}
