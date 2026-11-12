import type { Metadata, Viewport } from "next";
import React from "react";
import "./globals.css";
import AppShell from "@/components/AppShell";

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
  manifest: "/manifest.json",
  icons: {
    icon: "/favicon.ico",
  },
};

export const viewport: Viewport = {
  themeColor: "#047857",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

interface RootLayoutProps {
  readonly children: React.ReactNode;
}

export default function RootLayout({
  children,
}: RootLayoutProps): React.JSX.Element {
  return (
    <html lang="es-CO" className="h-full">
      <body className="h-full bg-slate-50 font-sans text-slate-900 antialiased selection:bg-emerald-100 selection:text-emerald-900">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
