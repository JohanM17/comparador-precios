"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";
import {
  clienteApi,
  type Categoria,
  type ProductoResumen,
} from "@/lib/api/clienteApi";
import { extraerInfoError, type InfoErrorVisible } from "@/lib/formato";
import AvisoDatosDemo from "@/components/AvisoDatosDemo";
import Cargando from "@/components/Cargando";
import EstadoError from "@/components/EstadoError";
import EstadoVacio from "@/components/EstadoVacio";
import GrillaProductos from "@/components/GrillaProductos";

/**
 * Vitrina interactiva de inicio (S1) conectada con GET /v1/categorias y GET /v1/productos.
 */
export default function VitrinaInicio(): React.JSX.Element {
  const searchParams = useSearchParams();
  const qInicial = searchParams.get("q") ?? "";

  const [terminoInput, setTerminoInput] = useState(qInicial);
  const [terminoActivo, setTerminoActivo] = useState(qInicial);
  const [categoriaId, setCategoriaId] = useState<number | null>(null);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [productos, setProductos] = useState<ProductoResumen[]>([]);
  const [siguienteCursor, setSiguienteCursor] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [cargandoMas, setCargandoMas] = useState(false);
  const [error, setError] = useState<InfoErrorVisible | null>(null);

  useEffect(() => {
    setTerminoInput(qInicial);
    setTerminoActivo(qInicial);
  }, [qInicial]);

  useEffect(() => {
    let activo = true;
    clienteApi
      .listarCategorias()
      .then((lista) => {
        if (activo) {
          setCategorias(lista);
        }
      })
      .catch(() => {
        // Las categorias son auxiliares; la vitrina puede continuar sin bloquear la carga
      });
    return () => {
      activo = false;
    };
  }, []);

  const cargarProductos = useCallback(
    async (cursor: string | null, acumular: boolean) => {
      if (acumular) {
        setCargandoMas(true);
      } else {
        setCargando(true);
        setError(null);
      }
      try {
        const res = await clienteApi.buscarProductos({
          q: terminoActivo.trim() || null,
          categoria_id: categoriaId,
          limite: 24,
          cursor,
        });
        setProductos((previos) => (acumular ? [...previos, ...res.datos] : res.datos));
        setSiguienteCursor(res.siguiente_cursor ?? null);
      } catch (err) {
        setError(extraerInfoError(err, "No fue posible cargar el catalogo de productos."));
      } finally {
        setCargando(false);
        setCargandoMas(false);
      }
    },
    [terminoActivo, categoriaId]
  );

  useEffect(() => {
    void cargarProductos(null, false);
  }, [cargarProductos]);

  const categoriasPorId = useMemo(() => {
    const mapa: Record<number, string> = {};
    for (const cat of categorias) {
      mapa[cat.id] = cat.nombre;
    }
    return mapa;
  }, [categorias]);

  const manejarBusqueda = (evento: React.FormEvent<HTMLFormElement>): void => {
    evento.preventDefault();
    setTerminoActivo(terminoInput);
  };

  const limpiarBusqueda = (): void => {
    setTerminoInput("");
    setTerminoActivo("");
  };

  return (
    <div>
      <AvisoDatosDemo visible={false} />

      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Compara precios reales de la canasta familiar en Armenia
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-700 sm:text-base">
            Precios normalizados por unidad de medida (kg, litro o unidad), sin pautas ni
            favoritismos comerciales.
          </p>

          <form onSubmit={manejarBusqueda} role="search" className="mt-5 flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <label htmlFor="buscador-vitrina" className="sr-only">
                Buscar producto por nombre, marca o cantidad
              </label>
              <Search
                className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
                aria-hidden="true"
              />
              <input
                id="buscador-vitrina"
                type="search"
                value={terminoInput}
                onChange={(e) => setTerminoInput(e.target.value)}
                placeholder="Ej. arroz 1/2 kilo, leche, aceite..."
                className="min-h-11 w-full rounded-xl border border-slate-300 bg-slate-50 py-2.5 pl-10 pr-10 text-sm text-slate-900 placeholder-slate-500 focus:border-emerald-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
              />
              {terminoInput && (
                <button
                  type="button"
                  onClick={limpiarBusqueda}
                  aria-label="Limpiar búsqueda"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-lg p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-700"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
            </div>
            <button
              type="submit"
              className="inline-flex min-h-11 items-center justify-center rounded-xl bg-emerald-700 px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-700 focus:ring-offset-2"
            >
              Buscar
            </button>
          </form>

          <nav aria-label="Categorías de productos" className="mt-5 flex gap-2 overflow-x-auto pb-1">
            <button
              type="button"
              onClick={() => setCategoriaId(null)}
              aria-pressed={categoriaId === null}
              className={`min-h-10 flex-shrink-0 rounded-full border px-4 py-1.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-700 ${
                categoriaId === null
                  ? "border-emerald-700 bg-emerald-700 text-white"
                  : "border-slate-300 bg-white text-slate-800 hover:bg-slate-100"
              }`}
            >
              Todas las categorías
            </button>
            {categorias.map((cat) => {
              const seleccionada = categoriaId === cat.id;
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => setCategoriaId(cat.id)}
                  aria-pressed={seleccionada}
                  className={`min-h-10 flex-shrink-0 rounded-full border px-4 py-1.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-700 ${
                    seleccionada
                      ? "border-emerald-700 bg-emerald-700 text-white"
                      : "border-slate-300 bg-white text-slate-800 hover:bg-slate-100"
                  }`}
                >
                  {cat.nombre}
                </button>
              );
            })}
          </nav>
        </section>

        <section aria-label="Catálogo de productos" className="mt-6">
          {cargando && <Cargando filas={6} etiqueta="Cargando productos de la canasta..." />}

          {!cargando && error && (
            <EstadoError
              detalle={error.detalle}
              codigo={error.codigo}
              requestId={error.requestId}
              onReintentar={() => void cargarProductos(null, false)}
            />
          )}

          {!cargando && !error && productos.length === 0 && (
            <EstadoVacio
              titulo="No encontramos productos con ese filtro"
              descripcion="Intenta buscar con otro nombre o selecciona todas las categorías."
              accionTexto="Reportar un precio"
              accionHref="/reportar"
            />
          )}

          {!cargando && !error && productos.length > 0 && (
            <GrillaProductos
              productos={productos}
              categoriasPorId={categoriasPorId}
              siguienteCursor={siguienteCursor}
              cargandoMas={cargandoMas}
              onCargarMas={() => {
                if (siguienteCursor) {
                  void cargarProductos(siguienteCursor, true);
                }
              }}
            />
          )}
        </section>
      </div>
    </div>
  );
}

