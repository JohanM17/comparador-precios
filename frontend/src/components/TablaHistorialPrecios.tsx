import React from "react";
import type { DatosHistorial } from "@/lib/api/clienteApi";
import { formatearPesos } from "@/lib/formato";
import {
  esEstadoDudoso,
  estiloOrigen,
  etiquetaEstado,
  etiquetaUnidad,
  formatearFechaHistorial,
} from "@/lib/historialPrecios";

export interface TablaHistorialPreciosProps {
  readonly datos: DatosHistorial;
}

/**
 * Tabla HTML alternativa a la grafica, con los mismos puntos entregados por la API.
 * No reordena ni calcula precios: solo formatea los datos para lectura accesible.
 */
export default function TablaHistorialPrecios({
  datos,
}: TablaHistorialPreciosProps): React.JSX.Element {
  const unidad = etiquetaUnidad(datos.producto.unidad_visualizacion);
  const totalPuntos = datos.puntos.length;
  const rango = `${formatearFechaHistorial(datos.desde)} al ${formatearFechaHistorial(datos.hasta)}`;

  return (
    <details open className="rounded-xl border border-slate-200 bg-slate-50/60">
      <summary className="cursor-pointer rounded-xl px-4 py-3 text-sm font-semibold text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-700">
        Tabla de datos del historial ({totalPuntos} {totalPuntos === 1 ? "punto" : "puntos"})
      </summary>
      <div
        role="region"
        aria-label="Tabla del historial de precios"
        tabIndex={0}
        className="overflow-x-auto rounded-b-xl border-t border-slate-200 bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-700"
      >
        <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
          <caption className="border-b border-slate-100 px-4 py-3 text-left text-xs text-slate-600">
            Puntos del historial de {datos.producto.nombre} en {datos.establecimiento.nombre}, del{" "}
            {rango}. Precio por {unidad}.
          </caption>
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
            <tr>
              <th scope="col" className="px-4 py-2.5 font-semibold">
                Fecha
              </th>
              <th scope="col" className="px-4 py-2.5 font-semibold">
                Precio por unidad
              </th>
              <th scope="col" className="px-4 py-2.5 font-semibold">
                Origen
              </th>
              <th scope="col" className="px-4 py-2.5 font-semibold">
                Estado
              </th>
              <th scope="col" className="px-4 py-2.5 font-semibold">
                Demo
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {datos.puntos.map((punto) => {
              const origen = estiloOrigen(punto.origen);
              const dudoso = esEstadoDudoso(punto.estado);

              return (
                <tr key={punto.id} className="align-top">
                  <td className="whitespace-nowrap px-4 py-2.5 text-slate-700">
                    <time dateTime={punto.observado_en}>
                      {formatearFechaHistorial(punto.observado_en)}
                    </time>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 font-medium text-slate-900">
                    {formatearPesos(punto.precio_por_unidad.valor_cop)}{" "}
                    <span className="text-xs font-normal text-slate-500">por {unidad}</span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-700">{origen.etiqueta}</td>
                  <td className="px-4 py-2.5">
                    <span className={dudoso ? "font-semibold text-amber-900" : "text-slate-700"}>
                      {etiquetaEstado(punto.estado)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-700">{punto.es_demo ? "Sí" : "No"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}
