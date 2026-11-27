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
    <details open className="border-t border-slate-200">
      <summary className="rotulo cursor-pointer py-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-600">
        Tabla de datos del historial ({totalPuntos} {totalPuntos === 1 ? "punto" : "puntos"})
      </summary>
      <div
        role="region"
        aria-label="Tabla del historial de precios"
        tabIndex={0}
        className="overflow-x-auto border-t border-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-600"
      >
        <table className="w-full min-w-[36rem] border-collapse text-left text-[13.5px]">
          <caption className="max-w-[72ch] py-3 text-left text-[12.5px] leading-relaxed text-slate-500">
            Puntos del historial de {datos.producto.nombre} en {datos.establecimiento.nombre}, del{" "}
            {rango}. Precio por {unidad}.
          </caption>
          <thead>
            <tr className="border-y border-slate-200">
              <th scope="col" className="rotulo py-2.5 pr-4 text-left">
                Fecha
              </th>
              <th scope="col" className="rotulo py-2.5 pr-4 text-left">
                Precio por unidad
              </th>
              <th scope="col" className="rotulo py-2.5 pr-4 text-left">
                Origen
              </th>
              <th scope="col" className="rotulo py-2.5 pr-4 text-left">
                Estado
              </th>
              <th scope="col" className="rotulo py-2.5 text-left">
                Demo
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {datos.puntos.map((punto) => {
              const origen = estiloOrigen(punto.origen);
              const dudoso = esEstadoDudoso(punto.estado);

              return (
                <tr key={punto.id} className="align-top">
                  <td className="cifras whitespace-nowrap py-2.5 pr-4 text-slate-600">
                    <time dateTime={punto.observado_en}>
                      {formatearFechaHistorial(punto.observado_en)}
                    </time>
                  </td>
                  <td className="cifras whitespace-nowrap py-2.5 pr-4 font-medium text-slate-900">
                    {formatearPesos(punto.precio_por_unidad.valor_cop)}{" "}
                    <span className="text-[12px] font-normal text-slate-500">por {unidad}</span>
                  </td>
                  <td className="py-2.5 pr-4 text-slate-600">{origen.etiqueta}</td>
                  <td className="py-2.5 pr-4">
                    <span className={dudoso ? "text-oro-700" : "text-slate-600"}>
                      {etiquetaEstado(punto.estado)}
                    </span>
                  </td>
                  <td className="py-2.5 text-slate-600">{punto.es_demo ? "Sí" : "No"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}
