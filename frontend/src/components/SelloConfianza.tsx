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
}

interface ConfiguracionSello {
  readonly clases: string;
  readonly Icono: LucideIcon;
  readonly etiquetaFija?: string;
  readonly respaldo: string;
}

const CONFIG_SELLOS: Readonly<Record<string, ConfiguracionSello>> = {
  confiable: {
    clases: "bg-emerald-100 text-emerald-900 ring-emerald-300",
    Icono: CheckCircle2,
    etiquetaFija: "Confiable",
    respaldo: "Confiable",
  },
  oficial: {
    clases: "bg-sky-100 text-sky-950 ring-sky-300",
    Icono: BadgeCheck,
    etiquetaFija: "Precio oficial",
    respaldo: "Precio oficial",
  },
  pocos_datos: {
    clases: "bg-oro-100 text-amber-950 ring-oro-300",
    Icono: HelpCircle,
    etiquetaFija: "Pocos datos: ayúdanos a confirmarlo",
    respaldo: "Pocos datos: ayúdanos a confirmarlo",
  },
  en_disputa: {
    clases: "bg-orange-100 text-orange-950 ring-orange-300",
    Icono: Scale,
    etiquetaFija: "En disputa: comercio vs. usuarios",
    respaldo: "En disputa: comercio vs. usuarios",
  },
  desactualizado: {
    clases: "bg-slate-100 text-slate-700 ring-slate-300",
    Icono: Clock,
    respaldo: "Precio desactualizado",
  },
  dudoso: {
    clases: "bg-cereza-50 text-cereza-700 ring-cereza-100",
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
}: SelloConfianzaProps): React.JSX.Element {
  const config = CONFIG_SELLOS[sello] ?? CONFIG_SELLOS.dudoso;
  const { clases, Icono, etiquetaFija, respaldo } = config;
  const texto = etiquetaFija ?? (motivoSello || respaldo);

  return (
    <output
      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${clases}`}
    >
      <Icono className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
      <span>{texto}</span>
    </output>
  );
}
