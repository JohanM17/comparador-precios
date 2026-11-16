import React from "react";
import Link from "next/link";
import { Camera, Clock, MapPin, Scale, Store } from "lucide-react";
import type { ItemComparacion } from "@/lib/api/clienteApi";
import {
  formatearAntiguedadRelativa,
  formatearDistancia,
  formatearFechaBogota,
  formatearPesos,
  formatearTipoEstablecimiento,
} from "@/lib/formato";
import SelloConfianza from "@/components/SelloConfianza";

export interface FilaPrecioProps {
  readonly item: ItemComparacion;
  readonly productoId: string;
}

/**
 * Fila individual de comparacion de precio en una tienda y presentacion.
 */
export default function FilaPrecio({
  item,
  productoId,
}: FilaPrecioProps): React.JSX.Element {
  const { establecimiento, presentacion, precio_por_unidad } = item;
  const fechaBogota = formatearFechaBogota(item.ultimo_reporte_en);
  const antiguedad = formatearAntiguedadRelativa(item.ultimo_reporte_en);
  const distancia =
    establecimiento.distancia_m !== undefined && establecimiento.distancia_m !== null
      ? formatearDistancia(establecimiento.distancia_m)
      : null;

  return (
    <article
      data-producto-id={productoId}
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <SelloConfianza sello={item.sello} motivoSello={item.motivo_sello ?? null} />
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
              <Store className="h-3 w-3" aria-hidden="true" />
              {formatearTipoEstablecimiento(establecimiento.tipo)}
            </span>
            {distancia && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-900">
                <MapPin className="h-3 w-3" aria-hidden="true" />
                {distancia}
              </span>
            )}
          </div>

          <div>
            <Link
              href={`/tienda/${establecimiento.id}`}
              className="text-lg font-bold text-slate-900 underline decoration-slate-300 underline-offset-4 hover:text-emerald-800 hover:decoration-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700"
            >
              {establecimiento.nombre}
            </Link>
            <p className="mt-0.5 text-sm text-slate-600">
              {[establecimiento.barrio, establecimiento.direccion].filter(Boolean).join(" · ") ||
                "Dirección registrada en Armenia"}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
            <span className="font-semibold text-slate-800">
              {presentacion.etiqueta}
              {presentacion.marca ? ` (${presentacion.marca})` : ""}
            </span>
            <time
              dateTime={item.ultimo_reporte_en}
              title={fechaBogota}
              className="inline-flex items-center gap-1 underline decoration-dotted underline-offset-2"
            >
              <Clock className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
              {antiguedad}
            </time>
            <span>
              {item.n_reportes_validos}{" "}
              {item.n_reportes_validos === 1 ? "reporte" : "reportes"} · {item.n_fuentes}{" "}
              {item.n_fuentes === 1 ? "fuente" : "fuentes"}
            </span>
            {item.con_foto_prueba && (
              <span className="inline-flex items-center gap-1 font-medium text-emerald-800">
                <Camera className="h-3.5 w-3.5" aria-hidden="true" />
                Con foto de prueba
              </span>
            )}
          </div>

          {item.sello === "en_disputa" && (
            <div className="mt-2 rounded-lg border border-orange-300 bg-orange-50 p-3 text-xs text-orange-950">
              <p className="flex items-center gap-1.5 font-semibold">
                <Scale className="h-4 w-4 text-orange-800" aria-hidden="true" />
                Contraste de precios en disputa
              </p>
              <p className="mt-1">
                Comunidad reporta <strong>{formatearPesos(item.precio_cop)}</strong>
                {item.precio_oficial_cop !== null && item.precio_oficial_cop !== undefined
                  ? ` frente a precio oficial del comercio de ${formatearPesos(item.precio_oficial_cop)}.`
                  : " frente al precio oficial publicado por el comercio."}
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-row items-center justify-between gap-4 border-t border-slate-100 pt-3 md:flex-col md:items-end md:border-t-0 md:pt-0">
          <div className="md:text-right">
            <p className="text-2xl font-extrabold tracking-tight text-slate-900">
              {formatearPesos(precio_por_unidad.valor_cop)} / {precio_por_unidad.por}
            </p>
            <p className="mt-0.5 text-xs font-medium text-slate-600">
              Empaque: {formatearPesos(item.precio_cop)} COP IVA incl.
            </p>
          </div>

          <Link
            href={`/reportar?tienda=${establecimiento.id}&presentacion=${presentacion.id}`}
            className="inline-flex min-h-11 items-center justify-center rounded-xl bg-emerald-700 px-4 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-700 focus:ring-offset-2"
          >
            Confirmar / Actualizar
          </Link>
        </div>
      </div>
    </article>
  );
}

