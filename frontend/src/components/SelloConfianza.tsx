import React from "react";
import {
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
  Clock,
  HelpCircle,
  Scale,
  type LucideIcon,
} from "lucide-react";
import type { SelloPrecio } from "@/lib/api/clienteApi";

export interface SelloConfianzaProps {
  readonly sello: SelloPrecio | string;
  readonly motivoSello: string | null;
  /**
   * Aviso D-02 para un precio oficial vencido. Se muestra como texto secundario
   * junto al sello para no alargar ni cambiar la insignia normal.
   */
  readonly avisoRevalidacion?: string | null;
}

interface ConfiguracionSello {
  readonly clases: string;
  readonly Icono: LucideIcon;
  readonly etiquetaFija?: string;
  readonly respaldo: string;
}

/*
 * Los sellos son anillos de un pixel sin relleno. No usan el verde esmeralda:
 * ese color esta reservado para el ahorro, y gastarlo aqui le quitaria el
 * significado. La confianza se distingue por icono y texto, nunca solo por color.
 */
const CONFIG_SELLOS: Readonly<Record<string, ConfiguracionSello>> = {
  confiable: {
    clases: "text-slate-700 ring-slate-300",
    Icono: CheckCircle2,
    etiquetaFija: "Confiable",
    respaldo: "Confiable",
  },
  oficial: {
    clases: "text-blue-600 ring-blue-200",
    Icono: BadgeCheck,
    etiquetaFija: "Precio oficial",
    respaldo: "Precio oficial",
  },
  pocos_datos: {
    clases: "text-oro-700 ring-oro-300",
    Icono: HelpCircle,
    etiquetaFija: "Pocos datos: ayúdanos a confirmarlo",
    respaldo: "Pocos datos: ayúdanos a confirmarlo",
  },
  en_disputa: {
    clases: "text-cereza-600 ring-cereza-200",
    Icono: Scale,
    etiquetaFija: "En disputa: comercio vs. usuarios",
    respaldo: "En disputa: comercio vs. usuarios",
  },
  desactualizado: {
    clases: "text-slate-500 ring-slate-300",
    Icono: Clock,
    respaldo: "Precio desactualizado",
  },
  dudoso: {
    clases: "text-cereza-600 ring-cereza-200",
    Icono: AlertTriangle,
    respaldo: "En revisión",
  },
};

/**
 * Insignia accesible de confiabilidad (WCAG 2.2 AA: icono + texto + anillo, nunca solo color).
 */
export default function SelloConfianza({
  sello,
  motivoSello,
  avisoRevalidacion,
}: SelloConfianzaProps): React.JSX.Element {
  const config = CONFIG_SELLOS[sello] ?? CONFIG_SELLOS.dudoso;
  const { clases, Icono, etiquetaFija, respaldo } = config;
  const texto = etiquetaFija ?? (motivoSello || respaldo);

  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      <output
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-medium ring-1 ring-inset ${clases}`}
      >
        <Icono className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
        <span>{texto}</span>
      </output>
      {avisoRevalidacion && (
        <span
          data-prueba="aviso-revalidacion"
          className="inline-flex items-center gap-1 text-[12.5px] font-medium text-oro-700"
        >
          <Clock className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
          {avisoRevalidacion}
        </span>
      )}
    </span>
  );
}
