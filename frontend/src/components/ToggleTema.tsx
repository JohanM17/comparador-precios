"use client";

import React, { useEffect } from "react";
import { Moon, Sun } from "lucide-react";

const CLAVE_TEMA = "tema";

/**
 * Alterna entre modo claro y oscuro. El estado vive en la clase `dark` de <html>
 * (la fija un script en el <head> antes de pintar, sin parpadeo) y la eleccion
 * explicita se recuerda en localStorage. Sin eleccion, se sigue al sistema.
 */
export default function ToggleTema(): React.JSX.Element {
  useEffect(() => {
    const consulta = window.matchMedia("(prefers-color-scheme: dark)");
    const alCambiarSistema = (ev: MediaQueryListEvent): void => {
      try {
        if (!localStorage.getItem(CLAVE_TEMA)) {
          document.documentElement.classList.toggle("dark", ev.matches);
        }
      } catch {
        document.documentElement.classList.toggle("dark", ev.matches);
      }
    };
    consulta.addEventListener("change", alCambiarSistema);
    return () => consulta.removeEventListener("change", alCambiarSistema);
  }, []);

  const alternar = (): void => {
    const raiz = document.documentElement;
    const oscuro = !raiz.classList.contains("dark");
    raiz.classList.toggle("dark", oscuro);
    try {
      localStorage.setItem(CLAVE_TEMA, oscuro ? "oscuro" : "claro");
    } catch {
      // Sin almacenamiento disponible: el cambio aplica solo a esta visita.
    }
  };

  return (
    <button
      type="button"
      onClick={alternar}
      aria-label="Cambiar entre modo claro y oscuro"
      title="Modo claro / oscuro"
      className="inline-flex h-10 w-10 items-center justify-center rounded-full text-bosque-100 transition-colors hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-miel-300"
    >
      <Sun className="hidden h-5 w-5 dark:block" aria-hidden="true" />
      <Moon className="h-5 w-5 dark:hidden" aria-hidden="true" />
    </button>
  );
}
