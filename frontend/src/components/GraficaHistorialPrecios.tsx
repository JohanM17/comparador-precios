"use client";

import React from "react";
import dynamic from "next/dynamic";
import { Info, LineChart } from "lucide-react";
import type { DatosHistorial } from "@/lib/api/clienteApi";
import {
  ORIGENES_HISTORIAL,
  etiquetaUnidad,
  formatearFechaHistorial,
  type EstiloOrigenHistorial,
} from "@/lib/historialPrecios";
import AvisoDatosDemo from "@/components/AvisoDatosDemo";
import Cargando from "@/components/Cargando";
import EstadoError from "@/components/EstadoError";
import EstadoVacio from "@/components/EstadoVacio";
import TablaHistorialPrecios from "@/components/TablaHistorialPrecios";

const GraficaHistorialRecharts = dynamic(
  () => import("@/components/GraficaHistorialRecharts"),
  {
    ssr: false,
    loading: () => (
      <div
        role="status"
        className="flex h-72 w-full items-center justify-center rounded-lg bg-slate-100 sm:h-80"
      >
        <span className="text-sm text-slate-500">Cargando gráfica...</span>
      </div>
    ),
  },
);

export interface GraficaHistorialPreciosProps {
  readonly datos: DatosHistorial | null;
  readonly cargando?: boolean;
  readonly error?: string | null;
  readonly onReintentar?: () => void;
}

interface LimiteErrorGraficaProps {
  readonly children: React.ReactNode;
  readonly mensaje: string;
}

interface EstadoLimiteGrafica {
  readonly fallo: boolean;
}

/**
 * Aisla fallos de carga o dibujo de la grafica para que la tabla accesible
 * siga disponible aunque recharts no llegue a renderizar.
 */
class LimiteErrorGrafica extends React.Component<LimiteErrorGraficaProps, EstadoLimiteGrafica> {
  public state: EstadoLimiteGrafica = { fallo: false };

  public static getDerivedStateFromError(): EstadoLimiteGrafica {
    return { fallo: true };
  }

  public render(): React.ReactNode {
    if (this.state.fallo) {
      return (
        <p
          role="status"
          className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-600"
        >
          {this.props.mensaje}
        </p>
      );
    }
    return this.props.children;
  }
}

interface MarcadorLeyendaProps {
  readonly estilo: EstiloOrigenHistorial;
}

function MarcadorLeyenda({ estilo }: MarcadorLeyendaProps): React.JSX.Element {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      aria-hidden="true"
      focusable="false"
      className="flex-shrink-0"
    >
      {estilo.forma === "cuadrado" ? (
        <rect x="2" y="2" width="10" height="10" rx="1.5" fill={estilo.color} />
      ) : estilo.forma === "triangulo" ? (
        <polygon points="7,1.5 12.5,12 1.5,12" fill={estilo.color} />
      ) : (
        <circle cx="7" cy="7" r="5" fill={estilo.color} />
      )}
    </svg>
  );
}

/**
 * Contenedor presentacional del historial de precios.
 *
 * Recibe los datos ya cargados por la ficha de producto, muestra los estados de
 * carga/error/vacio y delega la grafica a un modulo cargado dinamicamente. La
 * tabla HTML es la fuente accesible y se renderiza aunque la grafica falle.
 */
export default function GraficaHistorialPrecios({
  datos,
  cargando = false,
  error = null,
  onReintentar,
}: GraficaHistorialPreciosProps): React.JSX.Element {
  const tituloId = React.useId();

  if (cargando) {
    return <Cargando filas={5} etiqueta="Cargando historial de precios..." />;
  }

  if (error) {
    return <EstadoError detalle={error} onReintentar={onReintentar} />;
  }

  if (!datos || datos.puntos.length === 0) {
    return (
      <EstadoVacio
        titulo="Sin historial de precios"
        descripcion="Aún no hay precios en los últimos 90 días para este establecimiento."
        icono={<LineChart className="h-7 w-7 stroke-[1.5]" aria-hidden="true" />}
      />
    );
  }

  const unidad = etiquetaUnidad(datos.producto.unidad_visualizacion);
  const rango = `${formatearFechaHistorial(datos.desde)} – ${formatearFechaHistorial(datos.hasta)}`;
  const totalPuntos = datos.total;
  const etiquetaGrafica =
    `Historial de precios de ${datos.producto.nombre} en ${datos.establecimiento.nombre}, ` +
    `del ${rango}. ${datos.puntos.length} ${datos.puntos.length === 1 ? "punto" : "puntos"} ` +
    `de precio por ${unidad}. La tabla siguiente contiene los mismos datos.`;

  return (
    <section
      aria-labelledby={tituloId}
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <AvisoDatosDemo visible={datos.datos_de_demostracion} />

      <div className="p-5 sm:p-6">
        <header>
          <h2 id={tituloId} className="text-lg font-semibold text-slate-900 sm:text-xl">
            Historial de precios: {datos.producto.nombre}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {datos.establecimiento.nombre} · {datos.establecimiento.municipio}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Del {rango} · {totalPuntos} {totalPuntos === 1 ? "punto" : "puntos"} · Precio por{" "}
            {unidad}
          </p>
        </header>

        <div className="mt-5">
          <LimiteErrorGrafica mensaje="No fue posible cargar la gráfica. La tabla de abajo contiene todos los datos.">
            <div role="img" aria-label={etiquetaGrafica} className="w-full">
              <GraficaHistorialRecharts
                puntos={datos.puntos}
                unidad={datos.producto.unidad_visualizacion}
              />
            </div>
          </LimiteErrorGrafica>

          <div className="mt-3 space-y-2">
            <ul
              aria-label="Origen de los puntos del historial"
              className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-700"
            >
              {ORIGENES_HISTORIAL.map((estilo) => (
                <li key={estilo.origen} className="inline-flex items-center gap-1.5">
                  <MarcadorLeyenda estilo={estilo} />
                  <span>{estilo.etiqueta}</span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-slate-500">
              Los puntos en revisión (dudosos) se dibujan huecos y con borde discontinuo. El color y
              la forma indican el origen; el precio se muestra por {unidad}.
            </p>
          </div>
        </div>

        {datos.truncado && (
          <p
            role="note"
            className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900"
          >
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
            <span>
              Se muestran los puntos más recientes. La ventana consultada contiene más
              observaciones de las que se presentan aquí.
            </span>
          </p>
        )}

        <div className="mt-5">
          <TablaHistorialPrecios datos={datos} />
        </div>
      </div>
    </section>
  );
}
