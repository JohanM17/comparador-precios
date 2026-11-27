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

  const claseChip = (activa: boolean): string =>
    `min-h-10 flex-shrink-0 rounded-full border px-4 py-1.5 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 ${
      activa
        ? "border-slate-900 bg-slate-900 font-medium text-slate-50"
        : "border-slate-300 text-slate-600 hover:border-slate-900 hover:text-slate-900"
    }`;

  return (
    <div className="mx-auto max-w-5xl px-5 sm:px-6">
      <AvisoDatosDemo visible={false} />

      <section className="pb-12 pt-12 sm:pt-16">
        <p className="rotulo">Armenia, Quindío · canasta familiar</p>
        <h1 className="mt-4 max-w-[17ch] text-[clamp(2.1rem,6.4vw,3.9rem)] font-medium leading-[1.02] tracking-[-0.035em] text-slate-900">
          ¿Dónde está{" "}
          <span className="font-cursiva text-[1.08em] font-normal italic tracking-[-0.01em]">
            más barato
          </span>{" "}
          el mercado de hoy?
        </h1>
        <p className="mt-5 max-w-[46ch] text-[17px] leading-relaxed text-slate-600">
          Precios que reporta tu comunidad, comparados por kilo, litro o unidad para que dos
          presentaciones distintas se puedan medir de verdad. Sin pauta y sin favoritismos.
        </p>

        <form
          onSubmit={manejarBusqueda}
          role="search"
          className="mt-9 flex max-w-xl items-end gap-3 border-b border-slate-300 pb-2 focus-within:border-slate-900"
        >
          <div className="relative flex-1">
            <label htmlFor="buscador-vitrina" className="sr-only">
              Buscar producto por nombre, marca o cantidad
            </label>
            <Search
              className="pointer-events-none absolute left-0 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-slate-500"
              aria-hidden="true"
            />
            <input
              id="buscador-vitrina"
              type="search"
              value={terminoInput}
              onChange={(e) => setTerminoInput(e.target.value)}
              placeholder="Ej. arroz 1/2 kilo, leche, aceite…"
              className="min-h-11 w-full border-0 bg-transparent py-2 pl-7 pr-8 text-[17px] text-slate-900 placeholder-slate-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
            />
            {terminoInput && (
              <button
                type="button"
                onClick={limpiarBusqueda}
                aria-label="Limpiar búsqueda"
                className="absolute right-0 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-500 transition-colors hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </div>
          <button
            type="submit"
            className="min-h-11 flex-none px-1 pb-1 text-[15px] font-medium text-slate-900 underline decoration-slate-300 underline-offset-[6px] transition-colors hover:decoration-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
          >
            Buscar
          </button>
        </form>

        <nav
          aria-label="Categorías de productos"
          className="mt-7 flex gap-2 overflow-x-auto pb-1"
        >
          <button
            type="button"
            onClick={() => setCategoriaId(null)}
            aria-pressed={categoriaId === null}
            className={claseChip(categoriaId === null)}
          >
            Todas
          </button>
          {categorias.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setCategoriaId(cat.id)}
              aria-pressed={categoriaId === cat.id}
              className={claseChip(categoriaId === cat.id)}
            >
              {cat.nombre}
            </button>
          ))}
        </nav>
      </section>

      <div className="pb-4">
        <section aria-label="Catálogo de productos">
          <h2 className="rotulo mb-4">Catálogo</h2>

          {cargando && <Cargando filas={6} etiqueta="Cargando productos de la canasta…" />}

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

