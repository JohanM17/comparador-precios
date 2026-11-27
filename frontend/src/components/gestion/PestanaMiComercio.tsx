"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2, RefreshCw, Store } from "lucide-react";
import { clienteApi, type EstablecimientoDetalle } from "@/lib/api/clienteApi";
import {
  clienteComercio,
  type EstablecimientoComercio,
} from "@/lib/api/clienteComercio";
import { extraerInfoError, formatearFechaBogota, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";

export interface PestanaMiComercioProps {
  readonly token: string;
  /** Un reportante todavía no tiene tiendas: solo ve el formulario de reclamo. */
  readonly esComercio: boolean;
  readonly onTiendasCargadas?: (tiendas: readonly EstablecimientoComercio[]) => void;
}

/**
 * Pestaña «Mi comercio» de S6.
 *
 * Reúne las dos caras del mismo asunto: reclamar la titularidad de una tienda
 * y, una vez verificada, verla con el estado de sus precios oficiales. El
 * reclamo lo puede hacer cualquier cuenta; la decisión es siempre de un
 * moderador humano (`D-09`), y aquí se dice sin adornos.
 */
export default function PestanaMiComercio({
  token,
  esComercio,
  onTiendasCargadas,
}: PestanaMiComercioProps): React.JSX.Element {
  const [tiendas, setTiendas] = useState<readonly EstablecimientoComercio[]>([]);
  const [cargando, setCargando] = useState(esComercio);
  const [error, setError] = useState<InfoErrorVisible | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  const [candidatas, setCandidatas] = useState<readonly EstablecimientoDetalle[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const [reclamoId, setReclamoId] = useState("");
  const [telefono, setTelefono] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [enviando, setEnviando] = useState(false);

  const cargarTiendas = useCallback(async (): Promise<void> => {
    if (!esComercio) {
      setCargando(false);
      return;
    }
    setCargando(true);
    setError(null);
    try {
      const lista = await clienteComercio.listarEstablecimientos(token);
      setTiendas(lista);
      onTiendasCargadas?.(lista);
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible cargar tus establecimientos."));
    } finally {
      setCargando(false);
    }
  }, [token, esComercio, onTiendasCargadas]);

  useEffect(() => {
    void cargarTiendas();
  }, [cargarTiendas]);

  const buscarCandidatas = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setError(null);
    try {
      const res = await clienteApi.solicitar<{ readonly datos: EstablecimientoDetalle[] }>(
        `/v1/establecimientos?q=${encodeURIComponent(busqueda.trim())}&limite=10`
      );
      setCandidatas(res.datos);
      if (res.datos.length > 0 && res.datos[0]) {
        setReclamoId(res.datos[0].id);
      }
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible buscar establecimientos."));
    }
  };

  const enviarReclamo = async (ev: React.FormEvent<HTMLFormElement>): Promise<void> => {
    ev.preventDefault();
    setError(null);
    setExito(null);
    setEnviando(true);
    try {
      await clienteComercio.reclamarTitularidad(token, {
        establecimiento_id: reclamoId,
        telefono_contacto: telefono.trim(),
        mensaje: mensaje.trim(),
      });
      setExito(
        "Reclamo enviado. Un moderador lo revisará y te contactará al teléfono que dejaste. " +
          "Hasta entonces nada cambia en la comparación."
      );
      setTelefono("");
      setMensaje("");
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible enviar el reclamo."));
    } finally {
      setEnviando(false);
    }
  };

  const revalidar = async (establecimientoId: string): Promise<void> => {
    setError(null);
    setExito(null);
    try {
      const res = await clienteComercio.revalidar(token, establecimientoId);
      setExito(
        `${res.revalidados} ${res.revalidados === 1 ? "precio confirmado" : "precios confirmados"} ` +
          `el ${formatearFechaBogota(res.revalidado_en)}.`
      );
      await cargarTiendas();
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible confirmar los precios."));
    }
  };

  return (
    <div className="space-y-10">
      {error && (
        <EstadoError
          detalle={error.detalle}
          codigo={error.codigo}
          requestId={error.requestId}
          onReintentar={() => void cargarTiendas()}
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

      {esComercio && (
        <section aria-labelledby="titulo-mis-tiendas">
          <h2 id="titulo-mis-tiendas" className="rotulo mb-1.5">
            Mis establecimientos
          </h2>
          <p className="mb-5 max-w-[58ch] text-[13.5px] leading-relaxed text-slate-500">
            Publicar tus precios no mejora tu posición en la comparación. El orden lo deciden el
            precio por unidad y la distancia, nada más.
          </p>

          {cargando && <p className="rotulo">Cargando establecimientos…</p>}

          {!cargando && tiendas.length === 0 && (
            <p className="text-[13.5px] text-slate-500">
              Todavía no tienes establecimientos verificados.
            </p>
          )}

          {!cargando && tiendas.length > 0 && (
            <ul className="border-t border-slate-200">
              {tiendas.map((tienda) => (
                <li
                  key={tienda.id}
                  className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-b border-slate-200 py-4"
                >
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-[15px] font-medium tracking-[-0.015em] text-slate-900">
                      <Store className="h-4 w-4 flex-shrink-0 text-slate-500" aria-hidden="true" />
                      {tienda.nombre}
                    </p>
                    <p className="mt-1 text-[13px] text-slate-600">
                      {[tienda.barrio, tienda.direccion].filter(Boolean).join(" · ") || "Sin dirección registrada"}
                    </p>
                    <p className="cifras mt-1 text-[12.5px] text-slate-500">
                      {tienda.n_precios_oficiales}{" "}
                      {tienda.n_precios_oficiales === 1 ? "precio oficial" : "precios oficiales"}
                      {tienda.n_por_revalidar > 0 && (
                        <span className="text-cereza-600">
                          {" "}
                          · {tienda.n_por_revalidar} por confirmar
                        </span>
                      )}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void revalidar(tienda.id)}
                    className="inline-flex min-h-11 flex-none items-center gap-2 text-[13.5px] text-slate-600 underline decoration-slate-300 underline-offset-4 transition-colors hover:text-slate-900 hover:decoration-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                    Todo sigue igual
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section aria-labelledby="titulo-reclamar">
        <h2 id="titulo-reclamar" className="rotulo mb-1.5">
          Reclamar un establecimiento
        </h2>
        <p className="mb-6 max-w-[58ch] text-[13.5px] leading-relaxed text-slate-500">
          Si eres el dueño o encargado de una tienda que ya aparece aquí, puedes pedir que te la
          asignen. Un moderador lo verifica a mano; no es automático.
        </p>

        <form onSubmit={(ev) => void buscarCandidatas(ev)} className="mb-6 sm:max-w-md">
          <label htmlFor="buscar-establecimiento" className="block text-[12.5px] font-medium text-slate-500">
            Buscar por nombre
          </label>
          <div className="flex items-end gap-4">
            <input
              id="buscar-establecimiento"
              type="search"
              value={busqueda}
              onChange={(ev) => setBusqueda(ev.target.value)}
              placeholder="Supermercado, tienda de barrio…"
              className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-0"
            />
            <button
              type="submit"
              className="min-h-11 flex-none text-[13.5px] text-slate-600 underline decoration-slate-300 underline-offset-4 transition-colors hover:text-slate-900 hover:decoration-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
            >
              Buscar
            </button>
          </div>
        </form>

        <form onSubmit={(ev) => void enviarReclamo(ev)} className="space-y-5 sm:max-w-md">
          <div>
            <label htmlFor="reclamo-establecimiento" className="block text-[12.5px] font-medium text-slate-500">
              Establecimiento
            </label>
            <select
              id="reclamo-establecimiento"
              required
              value={reclamoId}
              onChange={(ev) => setReclamoId(ev.target.value)}
              className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
            >
              <option value="">Busca y elige tu tienda</option>
              {candidatas.map((est) => (
                <option key={est.id} value={est.id}>
                  {est.barrio ? `${est.nombre} · ${est.barrio}` : est.nombre}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="reclamo-telefono" className="block text-[12.5px] font-medium text-slate-500">
              Teléfono de contacto
            </label>
            <input
              id="reclamo-telefono"
              type="tel"
              required
              minLength={7}
              maxLength={30}
              value={telefono}
              onChange={(ev) => setTelefono(ev.target.value)}
              className="cifras mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus:ring-0"
            />
            <p className="mt-1.5 text-[12.5px] text-slate-500">
              Solo lo ve el moderador que revise tu reclamo.
            </p>
          </div>

          <div>
            <label htmlFor="reclamo-mensaje" className="block text-[12.5px] font-medium text-slate-500">
              Cómo pueden verificarte
            </label>
            <textarea
              id="reclamo-mensaje"
              required
              minLength={5}
              maxLength={500}
              rows={3}
              value={mensaje}
              onChange={(ev) => setMensaje(ev.target.value)}
              placeholder="Horario en que estás en el local, nombre del negocio en la fachada, etc."
              className="mt-1 w-full resize-y border-0 border-b border-slate-300 bg-transparent px-0 py-2 text-[15px] text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-0"
            />
          </div>

          <button
            type="submit"
            disabled={enviando || !reclamoId}
            className="inline-flex min-h-11 items-center justify-center rounded-full bg-brasa-600 px-5 text-[13.5px] font-medium text-slate-50 transition-colors hover:bg-brasa-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:opacity-50"
          >
            {enviando ? "Enviando…" : "Enviar reclamo"}
          </button>
        </form>
      </section>
    </div>
  );
}
