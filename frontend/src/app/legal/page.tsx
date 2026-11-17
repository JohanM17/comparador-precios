import React from "react";
import Link from "next/link";
import { ArrowLeft, Calculator, Database, FileText, Scale } from "lucide-react";
import PoliticaLey1581Resumen from "@/components/PoliticaLey1581Resumen";
import SelloConfianza from "@/components/SelloConfianza";

interface ExplicacionSello {
  readonly sello: "confiable" | "pocos_datos" | "en_disputa" | "desactualizado" | "dudoso" | "oficial";
  readonly motivo: string | null;
  readonly explicacion: string;
}

const SELLOS_CIUDADANOS: readonly ExplicacionSello[] = [
  {
    sello: "confiable",
    motivo: null,
    explicacion:
      "Respaldado por al menos 3 reportes vigentes de 2 o más cuentas distintas con baja dispersión entre precios.",
  },
  {
    sello: "pocos_datos",
    motivo: "Pocos datos: ayúdanos a confirmarlo",
    explicacion:
      "Cuenta con reportes recientes aceptados, pero aún no completa los 3 reportes y 2 fuentes independientes.",
  },
  {
    sello: "en_disputa",
    motivo: null,
    explicacion:
      "Existe diferencia superior al 10 % entre el precio oficial del comercio verificado y reportes recientes de la comunidad.",
  },
  {
    sello: "desactualizado",
    motivo: "Sin actualizar hace más de 7 días",
    explicacion:
      "El último reporte válido tiene entre 8 y 30 días de antigüedad y aparece en el bloque secundario.",
  },
  {
    sello: "dudoso",
    motivo: "En revisión: reportes sin confirmar",
    explicacion:
      "Reportes marcados por anomalía estadística, alta dispersión o riesgo de contexto; esperan verificación.",
  },
  {
    sello: "oficial",
    motivo: null,
    explicacion:
      "Precio publicado directamente por un establecimiento verificado (Etapa 2), sujeto a contraste ciudadano.",
  },
];

/**
 * Pantalla S7 (/legal): Transparencia metodologica, Ley 1581, Ley 527 y creditos ODbL.
 */
export default function PaginaLegal(): React.JSX.Element {
  return (
    <div>
      <div className="curvas-nivel bg-bosque-900 text-white">
        <div className="mx-auto max-w-4xl px-4 pb-10 pt-8 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="inline-flex min-h-10 items-center gap-1.5 text-sm font-semibold text-miel-300 hover:text-miel-100"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Volver al inicio
          </Link>
          <h1 className="mt-4 max-w-2xl text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl">
            Transparencia, Privacidad y Licencias
          </h1>
          <p className="mt-4 max-w-xl text-base text-bosque-100">
            Reglas públicas de funcionamiento, protección de datos y cálculo neutral de precios.
          </p>
        </div>
      </div>
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">

      <PoliticaLey1581Resumen />

      <section
        aria-labelledby="titulo-ley527"
        className="rounded-2xl border border-slate-300 bg-superficie p-6"
      >
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-emerald-700" aria-hidden="true" />
          <h2 id="titulo-ley527" className="text-lg font-bold text-slate-900">
            Términos de Uso y Evidencia Digital (Ley 527 de 1999)
          </h2>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-slate-700">
          Los reportes ciudadanos enviados con clave de idempotencia constituyen mensajes de datos
          registrados de forma inmutable (solo inserción) para preservar la trazabilidad histórica.
          Las fotografías de etiquetas o tirillas son opcionales, se comprimen sin metadatos EXIF y
          se usan únicamente para auditar calidad de precios. Cualquier usuario sancionado puede
          radicar apelación desde su panel de gestión.
        </p>
      </section>

      <section
        aria-labelledby="titulo-sellos"
        className="rounded-2xl border border-slate-300 bg-superficie p-6"
      >
        <h2 id="titulo-sellos" className="text-lg font-bold text-slate-900">
          Los 5 sellos de confianza ciudadana (y estado comercial oficial)
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Cada fila combina color, ícono y texto accesible para indicar la solidez del precio.
        </p>
        <ul className="mt-4 space-y-3">
          {SELLOS_CIUDADANOS.map((item) => (
            <li
              key={item.sello}
              className="flex flex-col gap-2 rounded-xl border border-slate-100 bg-slate-50 p-3.5 sm:flex-row sm:items-center"
            >
              <div className="sm:w-72 sm:flex-shrink-0">
                <SelloConfianza sello={item.sello} motivoSello={item.motivo} />
              </div>
              <p className="text-xs leading-relaxed text-slate-700">{item.explicacion}</p>
            </li>
          ))}
        </ul>
      </section>

      <section
        aria-labelledby="titulo-formulas"
        className="rounded-2xl border border-slate-300 bg-superficie p-6"
      >
        <div className="flex items-center gap-2">
          <Calculator className="h-5 w-5 text-emerald-700" aria-hidden="true" />
          <h2 id="titulo-formulas" className="text-lg font-bold text-slate-900">
            Fórmula de Unidad Base, Vigencia y Anomalías
          </h2>
        </div>
        <div className="mt-3 space-y-2 text-sm leading-relaxed text-slate-700">
          <p>
            <strong>Unidad base:</strong> Toda presentación se convierte a gramos (<code>g</code>),
            mililitros (<code>ml</code>) o unidades (<code>unidad</code>). En Colombia una libra
            métrica equivale exactamente a <code>500 g</code>. El precio normalizado se calcula como{" "}
            <code>precio_por_base = precio_cop / cantidad_base</code> y se visualiza por{" "}
            <code>kg</code>, <code>l</code> o <code>unidad</code>.
          </p>
          <p>
            <strong>Vigencia y mediana ponderada:</strong> Los reportes aceptados conservan peso
            completo las primeras 48 horas y decaen exponencialmente con vida media de 72 horas
            (con multiplicador 1.2 si incluyen foto de prueba), ponderados por la reputación
            bayesiana del reportante.
          </p>
          <p>
            <strong>Detección de anomalías:</strong> Se compara cada reporte en 3 niveles jerárquicos
            (presentación+tienda, presentación en el municipio, producto por unidad base) usando{" "}
            <em>z-score</em> modificado (umbral 3.5) o desviación porcentual del 30 %.
          </p>
        </div>
      </section>

      <section
        id="neutralidad"
        aria-labelledby="titulo-neutralidad"
        className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-6"
      >
        <div className="flex items-center gap-2">
          <Scale className="h-5 w-5 text-emerald-800" aria-hidden="true" />
          <h2 id="titulo-neutralidad" className="text-lg font-bold text-slate-900">
            Neutralidad Comercial Absoluta
          </h2>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-slate-800">
          Ningún comercio puede pagar para mejorar su posición en el comparador. Los resultados
          vigentes confiables (Bloque 1) se ordenan estrictamente de menor a mayor según el criterio
          elegido por el consumidor; los precios desactualizados o en revisión aparecen siempre en el
          Bloque 2 inferior. Las promociones viajan en un bloque independiente conforme a la Ley
          1480 de 2011 y nunca modifican el ranking.
        </p>
      </section>

      <section
        aria-labelledby="titulo-odbl"
        className="rounded-2xl border border-slate-300 bg-superficie p-6"
      >
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-emerald-700" aria-hidden="true" />
          <h2 id="titulo-odbl" className="text-lg font-bold text-slate-900">
            Créditos y Licencias Abiertas (ODbL)
          </h2>
        </div>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-700">
          <li>
            <strong>OpenStreetMap:</strong> Datos geográficos y ubicación de establecimientos en
            Armenia y Quindío &copy; Colaboradores de OpenStreetMap, disponibles bajo la{" "}
            <em>Open Database License (ODbL 1.0)</em>.
          </li>
          <li>
            <strong>Open Food Facts:</strong> Referencias de productos por código de barras
            provenientes de Open Food Facts, disponibles bajo licencia <em>ODbL 1.0</em>.
          </li>
        </ul>
      </section>
    </div>
    </div>
  );
}

