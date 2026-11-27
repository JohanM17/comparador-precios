"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, RefreshCw } from "lucide-react";
import { clienteApi, type PrecioVigenteResumen } from "@/lib/api/clienteApi";
import {
  clienteComercio,
  type EstablecimientoComercio,
  type PrecioOficialEntrada,
} from "@/lib/api/clienteComercio";
import { extraerInfoError, formatearPesos, type InfoErrorVisible } from "@/lib/formato";
import EstadoError from "@/components/EstadoError";

export interface PestanaPreciosRapidoProps {
  readonly token: string;
  readonly tiendas: readonly EstablecimientoComercio[];
}

interface FilaPrecioRapido {
  readonly presentacionId: string;
  readonly productoNombre: string;
  readonly presentacionEtiqueta: string;
  readonly precioComunidad: number;
  readonly precioOficialCop: number | null;
  readonly sello: string;
}

interface RechazoVisible {
  readonly id: string;
  readonly productoNombre: string;
  readonly motivo: string;
}

function esPrecioOficial(fila: FilaPrecioRapido): boolean {
  return (
    (fila.sello === "oficial" || fila.sello === "en_disputa") &&
    fila.precioOficialCop !== null
  );
}

/** Valor que el comercio confirma al publicar: el oficial si existe, si no el comunitario. */
function precioPrecargado(fila: FilaPrecioRapido): number {
  return esPrecioOficial(fila) && fila.precioOficialCop !== null
    ? fila.precioOficialCop
    : fila.precioComunidad;
}

function soloDigitos(texto: string): string {
  return texto.replace(/\D/g, "").slice(0, 7);
}

/**
 * Pestaña «Precios» de S6, en modo rápido (`D-06`).
 *
 * La pantalla está construida alrededor de una sola medida: que publicar
 * veinte precios tome menos de un minuto. Por eso todo está en una lista
 * plana, sin modales ni confirmaciones intermedias, la tecla Enter baja al
 * siguiente campo y solo se envía lo que de verdad cambió.
 *
 * El campo precargado no es siempre comunitario: si el comercio ya publicó un
 * precio oficial, ese es el valor que debe confirmar. Cuando no existe, se
 * precarga el precio de la comunidad y la fila lo advierte, para no invitar a
 * confirmar como propio un dato ajeno.
 */
export default function PestanaPreciosRapido({
  token,
  tiendas,
}: PestanaPreciosRapidoProps): React.JSX.Element {
  const primeraTienda = tiendas[0];
  const [tiendaId, setTiendaId] = useState<string>(primeraTienda ? primeraTienda.id : "");
  const [filas, setFilas] = useState<readonly FilaPrecioRapido[]>([]);
  const [valores, setValores] = useState<Record<string, string>>({});
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<InfoErrorVisible | null>(null);
  const [exito, setExito] = useState<string | null>(null);
  const [rechazados, setRechazados] = useState<readonly RechazoVisible[]>([]);
  const [publicadasEnSesion, setPublicadasEnSesion] = useState<readonly string[]>([]);

  const campos = useRef<(HTMLInputElement | null)[]>([]);

  const cargarPresentaciones = useCallback(
    async (conservarValores = false): Promise<void> => {
      if (!tiendaId) {
        setFilas([]);
        setValores({});
        if (!conservarValores) {
          setRechazados([]);
        }
        return;
      }
      setCargando(true);
      setError(null);
      if (!conservarValores) {
        setRechazados([]);
      }
      try {
        const detalle = await clienteApi.obtenerEstablecimiento(tiendaId);
        const nuevas = (detalle.precios_vigentes ?? []).map(
          (p: PrecioVigenteResumen): FilaPrecioRapido => ({
            presentacionId: p.presentacion_id,
            productoNombre: p.producto_nombre,
            presentacionEtiqueta: p.presentacion_etiqueta,
            precioComunidad: p.precio_cop,
            precioOficialCop: p.precio_oficial_cop ?? null,
            sello: p.sello,
          })
        );
        setFilas(nuevas);
        setValores((previos) => {
          const inicial: Record<string, string> = {};
          for (const fila of nuevas) {
            inicial[fila.presentacionId] = String(precioPrecargado(fila));
          }
          if (!conservarValores) {
            return inicial;
          }
          /*
           * Al recargar después de publicar se conserva lo que el comercio ya
           * había tecleado. Las filas rechazadas siguen mostrando su valor y su
           * motivo; perderlos obligaría a repetir el trabajo.
           */
          const siguiente = { ...inicial };
          for (const fila of nuevas) {
            if (Object.prototype.hasOwnProperty.call(previos, fila.presentacionId)) {
              siguiente[fila.presentacionId] =
                previos[fila.presentacionId] ?? inicial[fila.presentacionId];
            }
          }
          return siguiente;
        });
      } catch (err) {
        setError(extraerInfoError(err, "No fue posible cargar las presentaciones de la tienda."));
      } finally {
        setCargando(false);
      }
    },
    [tiendaId]
  );

  useEffect(() => {
    void cargarPresentaciones();
  }, [cargarPresentaciones]);

  const tiendaActual = tiendas.find((tienda) => tienda.id === tiendaId);
  const hayFilasOficiales = filas.some(esPrecioOficial);
  const hayOficialesReales =
    (tiendaActual?.n_precios_oficiales ?? 0) > 0 || hayFilasOficiales;
  /*
   * En una tienda sin precios oficiales no hay nada que revalidar: intentarlo
   * responde 409. La primera vez se publican todas las filas comunitarias como
   * precios oficiales; después, el botón principal solo manda lo que cambió.
   * La comprobación sobre las filas cubre el caso de volver a la pestaña con el
   * contador de la tienda todavía desactualizado.
   */
  const primeraPublicacion =
    tiendaActual !== undefined &&
    !hayOficialesReales &&
    !publicadasEnSesion.includes(tiendaId);

  const filasConValor = filas
    .map((fila) => ({ fila, valor: valores[fila.presentacionId] ?? "" }))
    .filter(({ valor }) => valor !== "" && Number(valor) > 0);

  const filasOmitidas = filas.filter((fila) => {
    const valor = valores[fila.presentacionId] ?? "";
    return valor === "" || Number(valor) <= 0;
  });

  const cambiados: PrecioOficialEntrada[] = filasConValor
    .filter(({ fila, valor }) => Number(valor) !== precioPrecargado(fila))
    .map(({ fila, valor }) => ({
      presentacion_id: fila.presentacionId,
      precio_cop: Number(valor),
    }));

  const preciosAEnviar: PrecioOficialEntrada[] = primeraPublicacion
    ? filasConValor.map(({ fila, valor }) => ({
        presentacion_id: fila.presentacionId,
        precio_cop: Number(valor),
      }))
    : cambiados;

  const alTeclear = (ev: React.KeyboardEvent<HTMLInputElement>, indice: number): void => {
    if (ev.key !== "Enter") {
      return;
    }
    // Enter no envía: baja al siguiente campo, que es lo que hace rápido el modo rápido.
    ev.preventDefault();
    const siguiente = campos.current[indice + 1];
    if (siguiente) {
      siguiente.focus();
      siguiente.select();
    }
  };

  const publicar = async (): Promise<void> => {
    if (preciosAEnviar.length === 0) {
      return;
    }
    const omitidas = filasOmitidas.length;
    setError(null);
    setExito(null);
    setGuardando(true);
    try {
      const res = await clienteComercio.publicarPrecios(token, tiendaId, preciosAEnviar);
      const motivos: RechazoVisible[] = res.rechazados.map((rechazo) => ({
        id: rechazo.presentacion_id,
        productoNombre:
          filas.find((fila) => fila.presentacionId === rechazo.presentacion_id)?.productoNombre ??
          "Presentación sin nombre",
        motivo: rechazo.motivo,
      }));
      setRechazados(motivos);
      if (res.actualizados > 0) {
        setPublicadasEnSesion((previas) =>
          previas.includes(tiendaId) ? previas : [...previas, tiendaId]
        );
      }
      const resumen =
        motivos.length === 0
          ? `${res.actualizados} ${res.actualizados === 1 ? "precio publicado" : "precios publicados"}.`
          : `${res.actualizados} publicados, ${motivos.length} no entraron.`;
      const faltantes =
        omitidas > 0
          ? ` ${omitidas} ${omitidas === 1 ? "fila quedó" : "filas quedaron"} sin precio y no se ${
              omitidas === 1 ? "envió" : "enviaron"
            }.`
          : motivos.length === 0
            ? " Ninguno quedó fuera."
            : "";
      setExito(resumen + faltantes);
      await cargarPresentaciones(true);
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible publicar los precios."));
    } finally {
      setGuardando(false);
    }
  };

  const revalidar = async (): Promise<void> => {
    setError(null);
    setExito(null);
    try {
      const res = await clienteComercio.revalidar(token, tiendaId);
      setExito(
        `${res.revalidados} ${res.revalidados === 1 ? "precio confirmado" : "precios confirmados"} sin cambios.`
      );
    } catch (err) {
      setError(extraerInfoError(err, "No fue posible confirmar los precios."));
    }
  };

  if (tiendas.length === 0) {
    return (
      <p className="text-[13.5px] text-slate-500">
        Necesitas un establecimiento verificado para publicar precios. Puedes reclamar el tuyo en
        la pestaña «Mi comercio».
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <section aria-labelledby="titulo-modo-rapido">
        <h2 id="titulo-modo-rapido" className="rotulo mb-1.5">
          Modo rápido
        </h2>
        <p className="max-w-[62ch] text-[13.5px] leading-relaxed text-slate-500">
          Cada campo trae tu precio oficial cuando ya lo publicaste. Si todavía no existe, trae el
          último precio que reportó la comunidad y la fila te lo advierte. Corrige solo los que
          estén mal y presiona Enter para bajar al siguiente.
        </p>
        {primeraPublicacion && (
          <p className="mt-3 max-w-[62ch] text-[13.5px] leading-relaxed text-slate-600">
            Esta tienda aún no tiene precios oficiales. Revisa los valores y publícalos todos con
            el botón de abajo; desde la próxima vez podrás usar «Todo sigue igual».
          </p>
        )}
      </section>

      {tiendas.length > 1 && (
        <div className="sm:max-w-md">
          <label htmlFor="tienda-precios" className="block text-[12.5px] font-medium text-slate-500">
            Establecimiento
          </label>
          <select
            id="tienda-precios"
            value={tiendaId}
            onChange={(ev) => setTiendaId(ev.target.value)}
            className="mt-1 min-h-11 w-full border-0 border-b border-slate-300 bg-transparent px-0 text-[15px] text-slate-900 focus:border-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
          >
            {tiendas.map((t) => (
              <option key={t.id} value={t.id}>
                {t.barrio ? `${t.nombre} · ${t.barrio}` : t.nombre}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <EstadoError
          detalle={error.detalle}
          codigo={error.codigo}
          requestId={error.requestId}
          onReintentar={() => void cargarPresentaciones()}
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

      {rechazados.length > 0 && (
        <div role="alert" className="border-l-2 border-cereza-600 pl-3">
          <p className="rotulo mb-1.5">
            {rechazados.length} {rechazados.length === 1 ? "no entró" : "no entraron"}
          </p>
          <ul className="space-y-1 text-[13px] text-slate-700">
            {rechazados.map((r) => (
              <li key={r.id}>
                <strong className="font-medium">{r.productoNombre}</strong>: {r.motivo}
              </li>
            ))}
          </ul>
        </div>
      )}

      {cargando && <p className="rotulo">Cargando presentaciones…</p>}

      {!cargando && filas.length === 0 && (
        <p className="text-[13.5px] text-slate-500">
          Esta tienda todavía no tiene presentaciones con precio reportado.
        </p>
      )}

      {!cargando && filas.length > 0 && (
        <>
          <ul className="border-t border-slate-200" data-prueba="lista-precios-rapido">
            {filas.map((fila, indice) => {
              const valor = valores[fila.presentacionId] ?? "";
              const cambio = valor !== "" && Number(valor) !== precioPrecargado(fila);
              const oficial = fila.precioOficialCop;
              const conOficial = esPrecioOficial(fila) && oficial !== null;
              return (
                <li
                  key={fila.presentacionId}
                  className="grid grid-cols-[1fr_auto] items-center gap-x-6 border-b border-slate-200 py-3"
                >
                  <label htmlFor={`precio-${fila.presentacionId}`} className="min-w-0">
                    <span className="block truncate text-[14.5px] text-slate-900">
                      {fila.productoNombre}
                    </span>
                    <span className="block truncate text-[12.5px] text-slate-500">
                      {fila.presentacionEtiqueta} ·{" "}
                      {conOficial && oficial !== null
                        ? fila.sello === "en_disputa"
                          ? `oficial en disputa ${formatearPesos(oficial)} · comunidad ${formatearPesos(fila.precioComunidad)}`
                          : `tu precio oficial ${formatearPesos(oficial)}`
                        : `comunidad ${formatearPesos(fila.precioComunidad)} · precio de la comunidad, no el tuyo`}
                    </span>
                  </label>
                  <div className="flex items-center gap-1.5">
                    <span aria-hidden="true" className="text-[13px] text-slate-500">
                      $
                    </span>
                    <input
                      id={`precio-${fila.presentacionId}`}
                      ref={(el) => {
                        campos.current[indice] = el;
                      }}
                      type="text"
                      inputMode="numeric"
                      autoComplete="off"
                      value={valor}
                      onFocus={(ev) => ev.target.select()}
                      onChange={(ev) =>
                        setValores((previos) => ({
                          ...previos,
                          [fila.presentacionId]: soloDigitos(ev.target.value),
                        }))
                      }
                      onKeyDown={(ev) => alTeclear(ev, indice)}
                      className={`cifras min-h-11 w-28 border-0 border-b bg-transparent px-0 text-right text-[15px] tabular-nums focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${
                        cambio
                          ? "border-emerald-600 text-emerald-700"
                          : "border-slate-300 text-slate-900 focus:border-slate-900"
                      }`}
                    />
                  </div>
                </li>
              );
            })}
          </ul>

          {filasOmitidas.length > 0 && (
            <p
              data-prueba="filas-sin-precio"
              className="max-w-[62ch] text-[12.5px] leading-relaxed text-cereza-600"
            >
              {filasOmitidas.length}{" "}
              {filasOmitidas.length === 1
                ? "fila quedó sin precio y no se enviará"
                : "filas quedaron sin precio y no se enviarán"}
              . Complétalas si quieres publicarlas.
            </p>
          )}

          <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
            <button
              type="button"
              onClick={() => void publicar()}
              disabled={guardando || preciosAEnviar.length === 0}
              className="inline-flex min-h-11 items-center justify-center rounded-full bg-brasa-600 px-5 text-[13.5px] font-medium text-white transition-colors hover:bg-brasa-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:opacity-50"
              data-prueba="publicar-precios"
            >
              {guardando
                ? "Publicando…"
                : primeraPublicacion
                  ? "Publicar precios comunitarios"
                  : cambiados.length === 0
                    ? "Sin cambios por publicar"
                    : `Publicar ${cambiados.length} ${cambiados.length === 1 ? "precio" : "precios"}`}
            </button>

            {hayOficialesReales && (
              <button
                type="button"
                onClick={() => void revalidar()}
                className="inline-flex min-h-11 items-center gap-2 text-[13.5px] text-slate-600 underline decoration-slate-300 underline-offset-4 transition-colors hover:text-slate-900 hover:decoration-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Todo sigue igual
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
