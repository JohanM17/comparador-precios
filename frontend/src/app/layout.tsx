import type { Metadata, Viewport } from "next";
import React from "react";
import { Instrument_Serif, Schibsted_Grotesk } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/AppShell";

/**
 * Una sola familia sostiene toda la interfaz. La cursiva con gracias aparece en
 * dos o tres sitios contados y es el unico contraste tipografico del diseno.
 */
const fuenteCuerpo = Schibsted_Grotesk({
  subsets: ["latin"],
  variable: "--font-cuerpo",
  display: "swap",
});

const fuenteCursiva = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-cursiva",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Quimbaya — Precios de la canasta en Armenia y Quindío",
    template: "%s | Quimbaya",
  },
  description:
    "Plataforma colaborativa y transparente para la comparacion de precios de la canasta basica familiar en Colombia.",
  applicationName: "Quimbaya",
  keywords: [
    "comparador de precios",
    "canasta familiar",
    "mercado",
    "colombia",
    "ahorro",
    "precios justos",
  ],
  authors: [{ name: "Comunidad Abierta" }],
  manifest: "/manifest.webmanifest",
  icons: {
    /* La pestana muestra el simbolo a 16 px: ahi va la variante de dos barras. */
    icon: [{ url: "/icons/favicon.svg", type: "image/svg+xml" }],
    apple: "/icons/icon-192.svg",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f6f3" },
    { media: "(prefers-color-scheme: dark)", color: "#141511" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

/**
 * Fija el tema antes del primer pintado para evitar el parpadeo claro a oscuro.
 * La lectura de localStorage y la consulta del sistema van en try/catch
 * separados: si el almacenamiento esta bloqueado, igual se respeta al sistema.
 */
const SCRIPT_TEMA = `(function(){var t=null;try{t=localStorage.getItem("tema")}catch(e){}var o=false;if(t){o=t==="oscuro"}else{try{o=window.matchMedia("(prefers-color-scheme: dark)").matches}catch(e){}}if(o){document.documentElement.classList.add("dark")}})();`;

interface RootLayoutProps {
  readonly children: React.ReactNode;
}

export default function RootLayout({
  children,
}: RootLayoutProps): React.JSX.Element {
  return (
    <html
      lang="es-CO"
      suppressHydrationWarning
      className={`h-full ${fuenteCuerpo.variable} ${fuenteCursiva.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
      </head>
      <body className="h-full bg-slate-50 font-sans text-slate-900 antialiased selection:bg-emerald-100 selection:text-slate-900">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
