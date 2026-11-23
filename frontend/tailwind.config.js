const plugin = require("tailwindcss/plugin");

const PASOS = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"];

/*
 * Sistema "papel y esmeralda".
 *
 * Reglas que sostienen el diseno y que conviene no romper al agregar pantallas:
 *
 * 1. El fondo es papel calido y la tinta es casi negra. No hay tarjetas con sombra:
 *    la separacion se hace con lineas de un pixel (slate-200 / slate-300).
 * 2. El verde esmeralda (emerald-600 en claro) significa UNA sola cosa: ahorro.
 *    Se reserva para el establecimiento mas barato, su cifra y el monto ahorrado.
 *    Usarlo de adorno le quita el significado.
 * 3. El ladrillo (cereza-600) solo advierte: datos en disputa, productos sin precio,
 *    errores. Nunca decora.
 * 4. slate-500 es el tono mas claro admitido para texto sobre papel (4.6:1).
 *    Cualquier cosa mas clara incumple WCAG 2.2 AA y la prueba de axe lo detecta.
 */

/** Neutros de papel y tinta. */
const NEUTRO_CLARO = {
  50: "#f7f6f3", 100: "#efeee9", 200: "#e4e3dc", 300: "#d2d1c8", 400: "#a9aba2",
  500: "#6e7268", 600: "#575a52", 700: "#41443d", 800: "#2b2d27", 900: "#191a17", 950: "#0e0f0d",
};
const NEUTRO_OSCURO = {
  50: "#141511", 100: "#1c1d18", 200: "#24261f", 300: "#33352c", 400: "#74776c",
  500: "#8d8f85", 600: "#a8aa9f", 700: "#c4c6ba", 800: "#dcdcd3", 900: "#f2f1ea", 950: "#fbfaf5",
};

/** Esmeralda: el color del ahorro. */
const JADE_CLARO = {
  50: "#e8f0ec", 100: "#d2e3db", 200: "#a7c8bb", 300: "#6fa893", 400: "#3b8470",
  500: "#1c6e58", 600: "#0e5c4a", 700: "#0b4b3d", 800: "#093b30", 900: "#072e26", 950: "#041b16",
};
const JADE_OSCURO = {
  50: "#041b16", 100: "#072e26", 200: "#0b4b3d", 300: "#16795f", 400: "#2fa07e",
  500: "#4fbf96", 600: "#6fd1ad", 700: "#92dfc3", 800: "#b8ecd8", 900: "#dcf6ec", 950: "#f0fbf7",
};

/** Ladrillo: solo advertencias. */
const LADRILLO_CLARO = {
  50: "#fbeeea", 100: "#f6dcd4", 200: "#ecb8a9", 300: "#dd8e78", 400: "#c4624a",
  500: "#ad4b32", 600: "#9e3c26", 700: "#83301e", 800: "#682619", 900: "#4f1d14", 950: "#2b0f0a",
};
const LADRILLO_OSCURO = {
  50: "#2b0f0a", 100: "#4f1d14", 200: "#682619", 300: "#9e3c26", 400: "#c4624a",
  500: "#dd8e78", 600: "#e8a894", 700: "#f0c3b4", 800: "#f6dcd4", 900: "#fbeeea", 950: "#fef8f6",
};

/** Ocre apagado: datos insuficientes o por revalidar. */
const OCRE_CLARO = {
  50: "#faf4e6", 100: "#f2e6c8", 200: "#e5cf98", 300: "#d4b469", 400: "#bf9842",
  500: "#a67f2d", 600: "#876526", 700: "#684d1f", 800: "#4d3918", 900: "#352711", 950: "#1c1409",
};
const OCRE_OSCURO = {
  50: "#1c1409", 100: "#352711", 200: "#4d3918", 300: "#876526", 400: "#bf9842",
  500: "#d4b469", 600: "#e5cf98", 700: "#eedfb6", 800: "#f2e6c8", 900: "#faf4e6", 950: "#fdfaf2",
};

/** Azul sobrio: solo para el dato oficial publicado por un comercio. */
const AZUL_CLARO = {
  50: "#eaeff6", 100: "#d6e0ee", 200: "#aec1dc", 300: "#7e9cc4", 400: "#4e74a6",
  500: "#2f5a8c", 600: "#24477a", 700: "#1d3a63", 800: "#172e4e", 900: "#11233b", 950: "#091422",
};
const AZUL_OSCURO = {
  50: "#091422", 100: "#11233b", 200: "#1d3a63", 300: "#2f5a8c", 400: "#4e74a6",
  500: "#7e9cc4", 600: "#9db5d5", 700: "#bccce3", 800: "#d6e0ee", 900: "#eaeff6", 950: "#f6f9fc",
};

/*
 * Los nombres de paleta se conservan para no reescribir 42 archivos de golpe.
 * slate = papel y tinta, emerald = esmeralda, cereza = ladrillo, oro = ocre,
 * amber y orange = ocre, blue y sky = azul oficial, rose = ladrillo.
 */
const PALETAS = {
  slate: [NEUTRO_CLARO, NEUTRO_OSCURO],
  emerald: [JADE_CLARO, JADE_OSCURO],
  cereza: [LADRILLO_CLARO, LADRILLO_OSCURO],
  rose: [LADRILLO_CLARO, LADRILLO_OSCURO],
  oro: [OCRE_CLARO, OCRE_OSCURO],
  amber: [OCRE_CLARO, OCRE_OSCURO],
  orange: [OCRE_CLARO, OCRE_OSCURO],
  blue: [AZUL_CLARO, AZUL_OSCURO],
  sky: [AZUL_CLARO, AZUL_OSCURO],
};

function hexARgb(hex) {
  const n = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(n.slice(i, i + 2), 16)).join(" ");
}

const coloresTailwind = {};
const varsClaro = { "--c-superficie": hexARgb("#ffffff") };
const varsOscuro = { "--c-superficie": hexARgb("#1c1d18") };

for (const [nombre, [claro, oscuro]] of Object.entries(PALETAS)) {
  coloresTailwind[nombre] = {};
  for (const paso of PASOS) {
    const clave = `--c-${nombre}-${paso}`;
    varsClaro[clave] = hexARgb(claro[paso]);
    varsOscuro[clave] = hexARgb(oscuro[paso]);
    coloresTailwind[nombre][paso] = `rgb(var(${clave}) / <alpha-value>)`;
  }
}

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-cuerpo)", "system-ui", "sans-serif"],
        display: ["var(--font-cuerpo)", "system-ui", "sans-serif"],
        cursiva: ["var(--font-cursiva)", "Georgia", "serif"],
      },
      colors: {
        ...coloresTailwind,
        /** Fondo de paneles: blanco sobre papel, tinta elevada en modo oscuro. */
        superficie: "rgb(var(--c-superficie) / <alpha-value>)",
        /*
         * Superficies de tinta: iguales en ambos modos. Se usan en las franjas
         * oscuras de encabezado de las pantallas de formulario.
         */
        bosque: {
          50: "#f7f6f3", 100: "#d2d1c8", 200: "#a9aba2", 300: "#74776c", 400: "#575a52",
          500: "#41443d", 600: "#33352c", 700: "#2b2d27", 800: "#212320", 900: "#191a17", 950: "#0e0f0d",
        },
        /** Esmeralda legible sobre tinta. */
        miel: { 100: "#d2e3db", 300: "#6fd1ad" },
        /** Accion principal: pildora de tinta, no un color de alarma. */
        brasa: { 400: "#575a52", 600: "#2b2d27", 700: "#191a17" },
      },
      letterSpacing: {
        rotulo: "0.16em",
      },
    },
  },
  plugins: [
    plugin(({ addBase }) => {
      addBase({
        ":root": { ...varsClaro, colorScheme: "light" },
        ".dark": { ...varsOscuro, colorScheme: "dark" },
      });
    }),
  ],
};
