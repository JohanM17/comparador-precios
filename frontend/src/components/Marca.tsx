import React from "react";

/*
 * Simbolo de Quimbaya.
 *
 * Un sello romboidal lleno hasta cierto nivel. El rombo es geometria quimbaya
 * —los pectorales de oro lo repiten— y el nivel es un dato, no un adorno: lo
 * lleno es lo que te ahorras. Por eso el verde aqui mide algo, igual que en el
 * resto de la interfaz, donde el esmeralda solo significa ahorro.
 *
 * La geometria es la misma de los archivos de `public/marca/` y de
 * `public/icons/`. Si cambia aqui hay que regenerarlos; `docs/MARCA.md`
 * explica como y por que.
 */
const ROMBO = "M256 60L406 256L256 452L106 256Z";

/** Nivel medido sobre el rombo interior, para la version con contorno. */
const NIVEL_CONTORNO = "M146.16 275.57H365.84L256 419.09Z";

/** Nivel medido sobre el rombo exterior, para la version maciza. */
const NIVEL_MACIZO = "M124 279.52H388L256 452Z";

export interface MarcaProps {
  /** Clases de tamano y color; el nivel sale solo del tema. */
  readonly className?: string;
  /**
   * `compacta` es el sello macizo, sin contorno. Por debajo de unos 32 px un
   * contorno de un pixel con su relleno adentro se empasta: ahi conviene el
   * volumen.
   */
  readonly variante?: "completa" | "compacta";
  /**
   * Texto alternativo. Sin el, el simbolo se marca como decorativo, que es lo
   * correcto cuando el nombre aparece escrito al lado.
   */
  readonly titulo?: string;
}

/**
 * Simbolo de marca. Hereda el color del texto (`currentColor`) salvo el nivel,
 * que usa `emerald-600` y por lo tanto cambia solo entre claro y oscuro.
 */
export default function Marca({
  className,
  variante = "completa",
  titulo,
}: MarcaProps): React.JSX.Element {
  const macizo = variante === "compacta";

  return (
    <svg
      viewBox="0 0 512 512"
      className={className}
      role={titulo ? "img" : undefined}
      aria-label={titulo}
      aria-hidden={titulo ? undefined : true}
      focusable="false"
    >
      <path
        d={ROMBO}
        fill={macizo ? "currentColor" : "none"}
        stroke={macizo ? undefined : "currentColor"}
        strokeWidth={macizo ? undefined : 22}
        strokeLinejoin={macizo ? undefined : "round"}
      />
      <path
        d={macizo ? NIVEL_MACIZO : NIVEL_CONTORNO}
        className="fill-emerald-600"
      />
    </svg>
  );
}
