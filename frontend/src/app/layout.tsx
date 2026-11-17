import type { Metadata, Viewport } from "next";
import React from "react";
import { Bricolage_Grotesque, DM_Sans } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/AppShell";

const fuenteTitulo = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-titulo",
  display: "swap",
});

const fuenteCuerpo = DM_Sans({
  subsets: ["latin"],
  variable: "--font-cuerpo",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Comparador de Precios de la Canasta Familiar",
    template: "%s | Comparador de Precios",
  },
  description:
    "Plataforma colaborativa y transparente para la comparacion de precios de la canasta basica familiar en Colombia.",
  applicationName: "Comparador de Precios",
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
    icon: "/icons/icon-192.svg",
    apple: "/icons/icon-192.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#0a2b20",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

/** Fija el tema antes del primer pintado para evitar el parpadeo claro a oscuro. */
const SCRIPT_TEMA = `try{var t=localStorage.getItem("tema");var o=t?t==="oscuro":window.matchMedia("(prefers-color-scheme: dark)").matches;if(o)document.documentElement.classList.add("dark")}catch(e){}`;

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
      className={`h-full ${fuenteTitulo.variable} ${fuenteCuerpo.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
      </head>
      <body className="h-full bg-slate-50 font-sans text-slate-900 antialiased selection:bg-cereza-100 selection:text-slate-900">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
