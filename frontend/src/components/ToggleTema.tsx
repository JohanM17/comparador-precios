"use client";

import React, { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

const CLAVE_TEMA = "tema";

/**
 * Alterna entre modo claro y oscuro. El estado vive en la clase `dark` de <html>
 * (la fija un script en el <head> antes de pintar, sin parpadeo) y la eleccion
 * explicita se recuerda en localStorage. Sin eleccion, se sigue al sistema.
 */
export default function ToggleTema(): React.JSX.Element {
  const [oscuro, setOscuro] = useState(false);

  useEffect(() => {
    const raiz = document.documentElement;
    const sincronizar = (): void => {
      setOscuro(raiz.classList.contains("dark"));
    };
    sincronizar();

    const consulta = window.matchMedia("(prefers-color-scheme: dark)");
    const alCambiarSistema = (ev: MediaQueryListEvent): void => {
      let eleccion: string | null = null;
      try {
        eleccion = localStorage.getItem(CLAVE_TEMA);
      } catch {
        // Sin almacenamiento disponible se mantiene la preferencia del sistema.
      }
      if (eleccion === null) {
        raiz.classList.toggle("dark", ev.matches);
        setOscuro(ev.matches);
      }
    };
    consulta.addEventListener("change", alCambiarSistema);
    return () => consulta.removeEventListener("change", alCambiarSistema);
  }, []);

  const alternar = (): void => {
    const raiz = document.documentElement;
    const siguiente = !raiz.classList.contains("dark");
    raiz.classList.toggle("dark", siguiente);
    setOscuro(siguiente);
    try {
      localStorage.setItem(CLAVE_TEMA, siguiente ? "oscuro" : "claro");
    } catch {
      // Sin almacenamiento disponible: el cambio aplica solo a esta visita.
    }
  };

  return (
    <button
      type="button"
      onClick={alternar}
      aria-pressed={oscuro}
      aria-label={oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
      title={oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
      className="inline-flex h-10 w-10 items-center justify-center rounded-full text-slate-500 transition-colors hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
    >
      <Sun className="hidden h-[18px] w-[18px] dark:block" aria-hidden="true" />
      <Moon className="h-[18px] w-[18px] dark:hidden" aria-hidden="true" />
    </button>
  );
}
