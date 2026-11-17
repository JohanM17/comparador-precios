"use client";

import React, { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { clienteApi, type PoliticaTratamiento } from "@/lib/api/clienteApi";

const POLITICA_RESPALDO: PoliticaTratamiento = {
  version: "1.0",
  texto_completo:
    "En cumplimiento de la Ley Estatutaria 1581 de 2012 y el Decreto 1074 de 2015, la Plataforma de Precios de Armenia informa que los datos suministrados se usarán con fines de transparencia comunitaria y calidad de precios. Las coordenadas GPS se procesan solo en memoria y no se guardan en BD. El titular podrá conocer, actualizar, rectificar y suprimir sus datos.",
  finalidades: [
    "Registro de reportes colaborativos de precios en Armenia.",
    "Cálculo de reputación bayesiana comunitaria.",
    "Auditoría inmutable de integridad del catálogo.",
    "Prevención de anomalías y fraudes coordinados.",
  ],
  contacto_legal_email: "privacidad@comparador-armenia.local",
  derechos_arco: [
    "Conocer los datos personales almacenados.",
    "Actualizar y rectificar el alias público.",
    "Revocar la autorización concedida.",
    "Suprimir la cuenta con anonimización irreversible de reportes.",
  ],
};

/**
 * Muestra la politica vigente Ley 1581 consultada desde la API con respaldo local.
 */
export default function PoliticaLey1581Resumen(): React.JSX.Element {
  const [politica, setPolitica] = useState<PoliticaTratamiento>(POLITICA_RESPALDO);

  useEffect(() => {
    let activo = true;
    clienteApi
      .obtenerPoliticaTratamiento()
      .then((res) => {
        if (activo) {
          setPolitica(res);
        }
      })
      .catch(() => {
        // Conserva la version local de respaldo si no hay conexion
      });
    return () => {
      activo = false;
    };
  }, []);

  return (
    <section
      aria-labelledby="titulo-ley1581"
      className="rounded-2xl border border-slate-300 bg-superficie p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-emerald-700" aria-hidden="true" />
          <h2 id="titulo-ley1581" className="text-lg font-bold text-slate-900">
            Política de Tratamiento de Datos Personales (Ley 1581 de 2012)
          </h2>
        </div>
        <span className="rounded-full bg-emerald-50 px-3 py-0.5 text-xs font-semibold text-emerald-900">
          Versión {politica.version}
        </span>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-slate-700">{politica.texto_completo}</p>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl bg-slate-50 p-4">
          <h3 className="text-xs font-bold uppercase tracking-wide text-slate-800">Finalidades</h3>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-slate-700">
            {politica.finalidades.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl bg-slate-50 p-4">
          <h3 className="text-xs font-bold uppercase tracking-wide text-slate-800">
            Derechos ARCO del titular
          </h3>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-slate-700">
            {politica.derechos_arco.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      <p className="mt-4 text-xs text-slate-600">
        <strong>Privacidad por diseño:</strong> Las coordenadas GPS jamás se guardan ni registran en
        logs; la huella de red utiliza HMAC rotativo purgado cada 30 días y toda foto elimina sus
        metadatos EXIF. Canal de contacto legal:{" "}
        <a
          href={`mailto:${politica.contacto_legal_email}`}
          className="font-semibold text-emerald-800 underline underline-offset-2"
        >
          {politica.contacto_legal_email}
        </a>
        .
      </p>
    </section>
  );
}

