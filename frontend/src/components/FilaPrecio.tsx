import React from "react";
import Link from "next/link";
import { Camera, Clock, Scale } from "lucide-react";
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
 * Renglon de comparacion de precio en una tienda y presentacion.
 *
 * No es una tarjeta: es una fila separada por una linea de un pixel. El precio
 * por unidad base cierra a la derecha y es lo unico grande. Cuando la fila es la
 * mas barata se tine de esmeralda, que en este diseno significa ahorro y nada mas.
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

  const colorNombre = destacada
    ? "text-emerald-600"
    : secundaria
      ? "text-slate-600"
      : "text-slate-900";
  const colorCifra = destacada
    ? "text-emerald-600"
    : secundaria
      ? "text-slate-500"
      : "text-slate-900";

  return (
    <article
      data-producto-id={productoId}
      className="grid grid-cols-[auto_1fr_auto] items-baseline gap-x-4 gap-y-1.5 border-t border-slate-200 py-5"
    >
      <span
        aria-hidden="true"
        className={`cifras w-6 text-[13px] font-medium ${
          destacada ? "text-emerald-600" : "text-slate-400"
        }`}
      >
        {posicion !== undefined ? String(posicion).padStart(2, "0") : "—"}
      </span>

      <div className="min-w-0">
        <Link
          href={`/tienda/${establecimiento.id}`}
          className={`text-[18px] font-medium tracking-tight underline decoration-slate-300 underline-offset-4 transition-colors hover:decoration-current focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${colorNombre}`}
        >
          {establecimiento.nombre}
        </Link>
        {destacada && (
          <span className="ml-2.5 whitespace-nowrap text-[12px] font-medium text-emerald-600">
            el más barato por {precio_por_unidad.por}
          </span>
        )}

        <p className="mt-0.5 text-[13.5px] text-slate-500">
          {formatearTipoEstablecimiento(establecimiento.tipo)}
          {" · "}
          {[establecimiento.barrio, establecimiento.direccion].filter(Boolean).join(" · ") ||
            "Dirección registrada en Armenia"}
          {distancia ? ` · ${distancia}` : ""}
        </p>
      </div>

      <div className="text-right">
        <p className={`cifras text-[25px] font-medium leading-none tracking-tight ${colorCifra}`}>
          {formatearPesos(precio_por_unidad.valor_cop)}
          <span className="ml-1 text-[14px] font-normal text-slate-500">
            /{precio_por_unidad.por}
          </span>
        </p>
        <p className="mt-1 text-[12.5px] text-slate-500">
          {formatearPesos(item.precio_cop)} el empaque
        </p>
      </div>

      <div className="col-start-2 col-end-4 mt-1 flex flex-wrap items-center gap-x-3 gap-y-2">
        <SelloConfianza sello={item.sello} motivoSello={item.motivo_sello ?? null} />
        <span className="text-[12.5px] text-slate-500">
          {presentacion.etiqueta}
          {presentacion.marca ? ` (${presentacion.marca})` : ""}
        </span>
        <time
          dateTime={item.ultimo_reporte_en}
          title={fechaBogota}
          className="inline-flex items-center gap-1 text-[12.5px] text-slate-500"
        >
          <Clock className="h-3.5 w-3.5" aria-hidden="true" />
          {antiguedad}
        </time>
        <span className="text-[12.5px] text-slate-500">
          {item.n_reportes_validos} {item.n_reportes_validos === 1 ? "reporte" : "reportes"} ·{" "}
          {item.n_fuentes} {item.n_fuentes === 1 ? "fuente" : "fuentes"}
        </span>
        {item.con_foto_prueba && (
          <span className="inline-flex items-center gap-1 text-[12.5px] text-slate-500">
            <Camera className="h-3.5 w-3.5" aria-hidden="true" />
            Con foto de prueba
          </span>
        )}
        <Link
          href={`/reportar?tienda=${establecimiento.id}&presentacion=${presentacion.id}`}
          className="ml-auto inline-flex min-h-11 items-center text-[13px] font-medium text-slate-900 underline decoration-slate-300 underline-offset-4 transition-colors hover:decoration-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
        >
          Confirmar / Actualizar
        </Link>
      </div>

      {item.sello === "en_disputa" && (
        <div className="col-start-2 col-end-4 mt-1 border-l-2 border-cereza-600 pl-3.5 text-[13px] text-slate-600">
          <p className="inline-flex items-center gap-1.5 font-medium text-cereza-600">
            <Scale className="h-4 w-4" aria-hidden="true" />
            Contraste de precios en disputa
          </p>
          <p className="mt-0.5">
            La comunidad reporta <strong className="font-medium text-slate-900">
              {formatearPesos(item.precio_cop)}
            </strong>
            {item.precio_oficial_cop !== null && item.precio_oficial_cop !== undefined
              ? ` frente al precio oficial del comercio de ${formatearPesos(item.precio_oficial_cop)}.`
              : " frente al precio oficial publicado por el comercio."}
          </p>
        </div>
      )}
    </article>
  );
}
