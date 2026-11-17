const plugin = require("tailwindcss/plugin");
const colores = require("tailwindcss/colors");

const PASOS = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"];
const ESPEJO = { 50: "950", 100: "900", 200: "800", 300: "700", 400: "600", 500: "500", 600: "400", 700: "300", 800: "200", 900: "100", 950: "50" };

/** Paletas que cambian entre modo claro y oscuro (variables CSS). */
const paletasClaro = {
  // Neutros con tinte de follaje
  slate: {
    50: "#f3f5f1", 100: "#e7ece5", 200: "#d4dcd1", 300: "#b8c4b6", 400: "#8c9e8c",
    500: "#58695c", 600: "#4d5f52", 700: "#38483c", 800: "#25322a", 900: "#141d17", 950: "#0b110d",
  },
  // Verde de cafetal para textos, bordes y fondos suaves
  emerald: {
    50: "#eef6f0", 100: "#d8eadd", 200: "#b3d6bd", 300: "#82b894", 400: "#519670",
    500: "#2f7a56", 600: "#206247", 700: "#174e39", 800: "#103d2d", 900: "#0a2b20", 950: "#061a13",
  },
  // Cereza de cafe
  cereza: {
    50: "#fff1ef", 100: "#ffddd8", 200: "#ffbfb6", 300: "#f99a8e", 400: "#f0675a",
    500: "#dc4234", 600: "#c2312a", 700: "#9f2520", 800: "#7e1f1b", 900: "#661d1a", 950: "#380b0a",
  },
  // Mazorca madura (avisos de pocos datos)
  oro: {
    50: "#fdf8e6", 100: "#fbecc2", 200: "#f7dc92", 300: "#f2cd68", 400: "#e8b83f",
    500: "#e0a526", 600: "#b9811b", 700: "#8f6016", 800: "#6b4713", 900: "#4d3310", 950: "#2a1b08",
  },
  amber: colores.amber,
  orange: colores.orange,
  sky: colores.sky,
  blue: colores.blue,
  rose: colores.rose,
};

/** Ajuste fino del modo oscuro: los neutros no son un espejo exacto para cuidar el contraste. */
const paletasOscuroManual = {
  slate: {
    50: "#0c120e", 100: "#151d17", 200: "#1f2a22", 300: "#2f3d33", 400: "#7f9285",
    500: "#9db0a2", 600: "#b3c3b7", 700: "#c9d5cc", 800: "#dfe7e1", 900: "#eef3ef", 950: "#f7faf8",
  },
};

function hexARgb(hex) {
  const n = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(n.slice(i, i + 2), 16)).join(" ");
}

const coloresTailwind = {};
const varsClaro = {
  "--c-superficie": "255 255 255",
};
const varsOscuro = {
  "--c-superficie": "24 34 28",
};

for (const [nombre, paleta] of Object.entries(paletasClaro)) {
  coloresTailwind[nombre] = {};
  for (const paso of PASOS) {
    const clave = `--c-${nombre}-${paso}`;
    varsClaro[clave] = hexARgb(paleta[paso]);
    const oscuro = paletasOscuroManual[nombre]
      ? paletasOscuroManual[nombre][paso]
      : paleta[ESPEJO[paso]];
    varsOscuro[clave] = hexARgb(oscuro);
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
        display: ["var(--font-titulo)", "system-ui", "sans-serif"],
      },
      colors: {
        ...coloresTailwind,
        // Fondo de tarjetas y paneles: blanco en claro, verde casi negro en oscuro.
        superficie: "rgb(var(--c-superficie) / <alpha-value>)",
        // Superficies de marca: iguales en ambos modos (cabecera, portada, pie, botones).
        bosque: {
          50: "#eef6f0", 100: "#d8eadd", 200: "#b3d6bd", 300: "#82b894", 400: "#519670",
          500: "#2f7a56", 600: "#206247", 700: "#174e39", 800: "#103d2d", 900: "#0a2b20", 950: "#061a13",
        },
        miel: { 100: "#fbecc2", 300: "#f2cd68" },
        brasa: { 400: "#f0675a", 600: "#c2312a", 700: "#9f2520" },
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
