import React from "react";
import Link from "next/link";
import { Camera, Clock, MapPin, Scale } from "lucide-react";
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
  /** Posicion mostrada tal como la entrega el servidor (no se reordena en el cliente). */
  readonly posicion?: number;
  /** Resalta la primera fila del bloque vigente cuando el servidor ordena por precio unitario. */
  readonly destacada?: boolean;
}

/**
 * Fila individual de comparacion de precio en una tienda y presentacion.
 * El precio por unidad base ocupa la columna derecha con jerarquia tipografica fuerte.
 */
export default function FilaPrecio({
  item,
  productoId,
  posicion,
  destacada = false,
}: FilaPrecioProps): React.JSX.Element {
  const { establecimiento, presentacion, precio_por_unidad } = item;
  const fechaBogota = formatearFechaBogota(item.ultimo_reporte_en);
  const antiguedad = formatearAntiguedadRelativa(item.ultimo_reporte_en);
  const distancia =
    establecimiento.distancia_m !== undefined && establecimiento.distancia_m !== null
      ? formatearDistancia(establecimiento.distancia_m)
      : null;
  const secundaria = item.es_bloque_secundario;

  let claseContenedor = "border-slate-300 bg-superficie";
  if (destacada) {
    claseContenedor = "border-bosque-800 bg-bosque-900 text-white shadow-xl shadow-black/25";
  } else if (secundaria) {
    claseContenedor = "border-slate-300 bg-slate-100";
  }

  return (
    <article
      data-producto-id={productoId}
      className={`relative rounded-2xl border p-5 transition-shadow sm:p-6 ${claseContenedor}`}
    >
      {destacada && (
        <span className="absolute -top-3 left-5 rounded-full bg-miel-300 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.14em] text-bosque-950">
          Más barato por {precio_por_unidad.por}
        </span>
      )}

      <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
        <div className="flex min-w-0 flex-1 gap-4">
          {posicion !== undefined && (
            <span
              aria-hidden="true"
              className={`cifras hidden pt-0.5 font-display text-3xl font-bold leading-none sm:block ${
                destacada ? "text-miel-300" : "text-slate-300"
              }`}
            >
              {posicion}
            </span>
          )}

          <div className="min-w-0 flex-1 space-y-2.5">
            <div>
              <Link
                href={`/tienda/${establecimiento.id}`}
                className={`font-display text-xl font-semibold tracking-tight underline decoration-2 underline-offset-4 focus:outline-none focus-visible:ring-2 ${
                  destacada
                    ? "decoration-miel-300/50 hover:decoration-miel-300 focus-visible:ring-miel-300"
                    : "text-slate-900 decoration-slate-300 hover:decoration-cereza-600 focus-visible:ring-emerald-700"
                }`}
              >
                {establecimiento.nombre}
              </Link>
              <p className={`mt-0.5 text-sm ${destacada ? "text-bosque-100" : "text-slate-600"}`}>
                {formatearTipoEstablecimiento(establecimiento.tipo)}
                {" · "}
                {[establecimiento.barrio, establecimiento.direccion].filter(Boolean).join(" · ") ||
                  "Dirección registrada en Armenia"}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <SelloConfianza sello={item.sello} motivoSello={item.motivo_sello ?? null} />
              {distancia && (
                <span
                  className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${
                    destacada
                      ? "bg-white/10 text-white ring-white/25"
                      : "bg-superficie text-slate-700 ring-slate-300"
                  }`}
                >
                  <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                  {distancia}
                </span>
              )}
            </div>

            <div
              className={`flex flex-wrap items-center gap-x-4 gap-y-1 text-xs ${
                destacada ? "text-bosque-100" : "text-slate-600"
              }`}
            >
              <span className={`font-semibold ${destacada ? "text-white" : "text-slate-800"}`}>
                {presentacion.etiqueta}
                {presentacion.marca ? ` (${presentacion.marca})` : ""}
              </span>
              <time
                dateTime={item.ultimo_reporte_en}
                title={fechaBogota}
                className="inline-flex items-center gap-1 underline decoration-dotted underline-offset-2"
              >
                <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                {antiguedad}
              </time>
              <span>
                {item.n_reportes_validos}{" "}
                {item.n_reportes_validos === 1 ? "reporte" : "reportes"} · {item.n_fuentes}{" "}
                {item.n_fuentes === 1 ? "fuente" : "fuentes"}
              </span>
              {item.con_foto_prueba && (
                <span
                  className={`inline-flex items-center gap-1 font-medium ${
                    destacada ? "text-miel-300" : "text-emerald-800"
                  }`}
                >
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
        </div>

        <div
          className={`flex flex-row items-center justify-between gap-4 border-t pt-4 md:min-w-[220px] md:flex-col md:items-end md:border-t-0 md:pt-0 ${
            destacada ? "border-white/15" : "border-slate-200"
          }`}
        >
          <div className="md:text-right">
            <p
              className={`cifras font-display text-4xl font-bold leading-none tracking-tight sm:text-5xl ${
                destacada ? "text-miel-300" : secundaria ? "text-slate-600" : "text-emerald-800"
              }`}
            >
              {formatearPesos(precio_por_unidad.valor_cop)}
              <span
                className={`ml-1 text-base font-medium ${
                  destacada ? "text-bosque-100" : "text-slate-600"
                }`}
              >
                / {precio_por_unidad.por}
              </span>
            </p>
            <p
              className={`mt-1.5 text-xs font-medium ${
                destacada ? "text-bosque-100" : "text-slate-600"
              }`}
            >
              Empaque: {formatearPesos(item.precio_cop)} COP IVA incl.
            </p>
          </div>

          <Link
            href={`/reportar?tienda=${establecimiento.id}&presentacion=${presentacion.id}`}
            className={`inline-flex min-h-11 items-center justify-center rounded-full px-5 py-2 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${
              destacada
                ? "bg-white text-bosque-900 hover:bg-miel-100 focus-visible:ring-white focus-visible:ring-offset-bosque-900"
                : "border border-slate-400 bg-superficie text-slate-900 hover:border-emerald-800 hover:bg-emerald-50 focus-visible:ring-emerald-700"
            }`}
          >
            Confirmar / Actualizar
          </Link>
        </div>
      </div>
    </article>
  );
}
