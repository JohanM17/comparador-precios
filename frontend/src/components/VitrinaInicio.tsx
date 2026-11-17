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

      <section className="curvas-nivel bg-bosque-900 text-white">
        <div className="mx-auto max-w-7xl px-4 pb-10 pt-10 sm:px-6 sm:pb-14 sm:pt-14 lg:px-8">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-miel-300">
            Armenia, Quindío · Canasta familiar
          </p>
          <h1 className="mt-3 max-w-3xl font-display text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
            ¿Dónde está más barato el mercado de hoy?
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-bosque-100 sm:text-lg">
            Precios reales que reporta tu comunidad, comparados por kilo, litro o unidad. Sin pautas
            ni favoritismos comerciales.
          </p>

          <form onSubmit={manejarBusqueda} role="search" className="mt-7 flex max-w-2xl flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <label htmlFor="buscador-vitrina" className="sr-only">
                Buscar producto por nombre, marca o cantidad
              </label>
              <Search
                className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500"
                aria-hidden="true"
              />
              <input
                id="buscador-vitrina"
                type="search"
                value={terminoInput}
                onChange={(e) => setTerminoInput(e.target.value)}
                placeholder="Ej. arroz 1/2 kilo, leche, aceite..."
                className="min-h-12 w-full rounded-full border-2 border-transparent bg-superficie py-3 pl-11 pr-11 text-base text-slate-900 placeholder-slate-500 shadow-lg shadow-black/30 focus:border-miel-300 focus:outline-none"
              />
              {terminoInput && (
                <button
                  type="button"
                  onClick={limpiarBusqueda}
                  aria-label="Limpiar búsqueda"
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
            </div>
            <button
              type="submit"
              className="inline-flex min-h-12 items-center justify-center rounded-full bg-miel-300 px-8 py-3 text-base font-bold text-bosque-950 transition-colors hover:bg-miel-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-bosque-900"
            >
              Buscar
            </button>
          </form>

          <nav aria-label="Categorías de productos" className="mt-6 flex gap-2 overflow-x-auto pb-1">
            <button
              type="button"
              onClick={() => setCategoriaId(null)}
              aria-pressed={categoriaId === null}
              className={`min-h-10 flex-shrink-0 rounded-full border px-4 py-1.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-miel-300 ${
                categoriaId === null
                  ? "border-white bg-white text-bosque-900"
                  : "border-white/30 bg-transparent text-white hover:border-white hover:bg-white/10"
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
                  className={`min-h-10 flex-shrink-0 rounded-full border px-4 py-1.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-miel-300 ${
                    seleccionada
                      ? "border-white bg-white text-bosque-900"
                      : "border-white/30 bg-transparent text-white hover:border-white hover:bg-white/10"
                  }`}
                >
                  {cat.nombre}
                </button>
              );
            })}
          </nav>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section aria-label="Catálogo de productos">
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

