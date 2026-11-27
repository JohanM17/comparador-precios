"use client";

import React from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  type ScatterShapeProps,
  type TooltipPayload,
} from "recharts";
import type { PuntoHistorial } from "@/lib/api/clienteApi";
import { formatearFechaBogota, formatearPesos } from "@/lib/formato";
import {
  RELLENO_PUNTO_HUECO,
  esEstadoDudoso,
  estiloOrigen,
  etiquetaEjePrecio,
  etiquetaEstado,
  etiquetaUnidad,
  formatearMarcaEje,
} from "@/lib/historialPrecios";

export interface GraficaHistorialRechartsProps {
  readonly puntos: readonly PuntoHistorial[];
  readonly unidad: string;
}

interface PuntoGrafica {
  readonly x: number;
  readonly y: number;
  readonly id: string;
  readonly observado_en: string;
  readonly origen: string;
  readonly estado: string;
  readonly es_demo: boolean;
}

interface ContenidoTooltipProps {
  readonly unidad: string;
  readonly active?: boolean;
  readonly payload?: TooltipPayload;
}

function convertirPunto(punto: PuntoHistorial): PuntoGrafica {
  return {
    x: Date.parse(punto.observado_en),
    y: punto.precio_por_unidad.valor_cop,
    id: punto.id,
    observado_en: punto.observado_en,
    origen: punto.origen,
    estado: punto.estado,
    es_demo: punto.es_demo,
  };
}

function renderizarPunto(props: ScatterShapeProps): React.ReactElement | null {
  const { cx, cy, payload } = props;
  if (typeof cx !== "number" || typeof cy !== "number") {
    return null;
  }

  const punto = payload as PuntoGrafica | null | undefined;
  if (!punto) {
    return null;
  }

  const estilo = estiloOrigen(punto.origen);
  const dudoso = esEstadoDudoso(punto.estado);
  const radio = dudoso ? 7 : 6;

  /*
   * El color va en `style` y no en los atributos `fill`/`stroke`: los
   * atributos de presentacion de SVG no resuelven `var()`, y los tokens del
   * sistema estan declarados como variables CSS.
   */
  const pintura: React.CSSProperties = {
    fill: dudoso ? RELLENO_PUNTO_HUECO : estilo.color,
    stroke: estilo.color,
    strokeWidth: dudoso ? 2.5 : 1.5,
    strokeDasharray: dudoso ? "3 2" : undefined,
  };

  switch (estilo.forma) {
    case "cuadrado":
      return (
        <rect
          x={cx - radio}
          y={cy - radio}
          width={radio * 2}
          height={radio * 2}
          rx={1.5}
          style={pintura}
        />
      );
    case "triangulo":
      return (
        <polygon
          points={`${cx},${cy - radio} ${cx + radio},${cy + radio} ${cx - radio},${cy + radio}`}
          style={pintura}
        />
      );
    default:
      return <circle cx={cx} cy={cy} r={radio} style={pintura} />;
  }
}

function ContenidoTooltip({
  unidad,
  active,
  payload,
}: ContenidoTooltipProps): React.ReactElement | null {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const punto = payload[0]?.payload as PuntoGrafica | undefined;
  if (!punto) {
    return null;
  }

  const estilo = estiloOrigen(punto.origen);

  return (
    <div className="max-w-xs border border-slate-300 bg-superficie px-3.5 py-2.5 text-xs">
      <p className="rotulo">{formatearFechaBogota(punto.observado_en)}</p>
      <p className="cifras mt-1.5 text-[17px] font-medium tracking-[-0.02em] text-slate-900">
        {formatearPesos(punto.y)}{" "}
        <span className="text-[12px] font-normal tracking-normal text-slate-500">
          por {etiquetaUnidad(unidad)}
        </span>
      </p>
      <dl className="mt-2 space-y-0.5 text-[12px] text-slate-600">
        <div className="flex gap-1.5">
          <dt className="text-slate-500">Origen</dt>
          <dd>{estilo.etiqueta}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-slate-500">Estado</dt>
          <dd>{etiquetaEstado(punto.estado)}</dd>
        </div>
        {punto.es_demo && (
          <div className="flex gap-1.5">
            <dt className="text-slate-500">Demo</dt>
            <dd>Sí</dd>
          </div>
        )}
      </dl>
    </div>
  );
}

/**
 * Grafica de dispersion del historial. Es el unico modulo que importa recharts
 * y se carga de forma dinamica desde `GraficaHistorialPrecios`.
 */
export default function GraficaHistorialRecharts({
  puntos,
  unidad,
}: GraficaHistorialRechartsProps): React.JSX.Element {
  const datos = puntos.map(convertirPunto);

  if (datos.length === 0) {
    return (
      <p
        role="status"
        className="border-y border-dashed border-slate-300 px-4 py-8 text-center text-[13.5px] text-slate-500"
      >
        No hay puntos para graficar.
      </p>
    );
  }

  return (
    <div className="grafica-historial h-72 w-full sm:h-80">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart
          margin={{ top: 12, right: 20, bottom: 8, left: 8 }}
          accessibilityLayer={false}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="x"
            domain={["dataMin - 43200000", "dataMax + 43200000"]}
            tickFormatter={formatearMarcaEje}
            tick={{ fontSize: 11 }}
            tickMargin={8}
            minTickGap={24}
            height={40}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={["auto", "auto"]}
            tickFormatter={(valor: number) => formatearPesos(valor)}
            tick={{ fontSize: 11 }}
            tickMargin={6}
            width={82}
            label={{
              value: etiquetaEjePrecio(unidad),
              angle: -90,
              position: "insideLeft",
              offset: 6,
              style: { fontSize: 11, textAnchor: "middle" },
            }}
          />
          <Tooltip
            content={<ContenidoTooltip unidad={unidad} />}
            cursor={{ strokeDasharray: "3 3" }}
          />
          <Scatter data={datos} shape={renderizarPunto} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
