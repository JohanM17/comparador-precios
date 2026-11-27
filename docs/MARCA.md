# Marca — Quimbaya

## 1. El nombre

**Quimbaya.** Es el pueblo orfebre que habitó este valle y es, además, un municipio del Quindío:
el nombre suena de la casa, no prestado. Los quimbaya trabajaron el oro con una precisión que
nadie más alcanzó en el continente, y la precisión es justo lo que este producto vende —
comparar por unidad base, no por empaque.

El nombre del producto es **Quimbaya**. El nombre académico del proyecto sigue siendo
*Comparador de Precios de la Canasta Familiar*, y es el que aparece en la documentación de la
asignatura. Son dos cosas distintas y conviven sin problema: una es la marca, la otra el título
del trabajo.

El descriptor, cuando hace falta aclarar qué es, es **«Precios de la canasta · Armenia,
Quindío»**. Va en el logotipo apilado y en los metadatos, no en el encabezado: allí la propia
pantalla lo explica.

## 2. El símbolo

Un **sello romboidal lleno hasta cierto nivel**.

El rombo es geometría quimbaya: los pectorales de oro lo repiten una y otra vez. No copia
ninguna pieza de museo —se descartó el poporo justamente por eso, y porque es un objeto
ceremonial que no tiene nada que ver con mercar— sino que usa su lenguaje.

El nivel es lo importante: **lo lleno es un dato, no un adorno**. Es la única parte verde, y
mide algo, igual que en el resto de la interfaz, donde el esmeralda significa ahorro y nada
más. Un rombo vacío sería una joya genérica; lleno hasta un punto es una medida.

Proporciones: semidiagonal horizontal 150, vertical 196 sobre un lienzo de 512. Más alto que
ancho a propósito — un rombo de diagonales iguales se lee como diamante genérico; el lozange
alto se lee como joya.

## 3. Los archivos

| Archivo | Para qué |
|---|---|
| `icons/icon-192.svg`, `icons/icon-512.svg` | Icono de la PWA (`purpose: any`). |
| `icons/icon-maskable-512.svg` | Icono enmascarable, al 82 % para que ningún recorte del sistema lo muerda. |
| `icons/favicon.svg` | Pestaña del navegador. **Sello macizo**, sin contorno. |
| `marca/simbolo-app.svg` | Símbolo sobre campo jade, suelto. |
| `marca/simbolo-tinta.svg` / `simbolo-papel.svg` | Símbolo en línea: tinta para fondos claros, papel para fondos oscuros. |
| `marca/logotipo-tinta.svg` | Logotipo horizontal para fondo claro. |
| `marca/logotipo-papel.svg` | Logotipo horizontal para fondo oscuro. |
| `marca/logotipo-jade.svg` | Logotipo horizontal sobre campo jade, con su margen. |
| `marca/logotipo-apilado.svg` | Logotipo vertical con descriptor. |
| `marca/png/*.png` | Los mismos, rasterizados y con fondo transparente, para PowerPoint, Word y cualquier cosa que no coma SVG. |

Los cuatro logotipos **traen las fuentes incrustadas**, recortadas a los caracteres que usan
(unos 6 KB en total). Sin eso, un SVG dentro de un `<img>` se dibujaría con la tipografía del
sistema, porque ahí el navegador no carga fuentes externas — y la cursiva de «Quimbaya» es
medio logotipo.

## 4. El favicon es distinto a propósito

A 16 px, un contorno de un píxel con su relleno adentro se empasta y el rombo se vuelve una
mancha. `favicon.svg` es el **sello macizo**: pierde el contorno y gana la silueta, que a ese
tamaño es lo único legible. El componente `Marca` hace lo mismo con `variante="compacta"`.

El encabezado, en cambio, usa la versión **con contorno** aunque mida solo 26 px. La razón es
otra: ahí el símbolo va en tinta, y un nivel en `emerald-600` sobre un rombo macizo de tinta
casi no se distingue — se perdería lo único que la marca mide.

## 5. En la aplicación

`frontend/src/components/Marca.tsx` dibuja el símbolo con la misma geometría. Toma el color del
contorno de `currentColor` y deja el nivel en `emerald-600`, que ya cambia solo entre claro y
oscuro gracias a los tokens de `tailwind.config.js`. No hay que pasarle colores.

```tsx
<Marca className="h-[26px] w-[26px] shrink-0" />
```

Sin `titulo` el símbolo se marca como decorativo (`aria-hidden`), que es lo correcto cuando el
nombre aparece escrito al lado — como en el encabezado. Con `titulo` pasa a ser `role="img"` con
su etiqueta, para cuando va solo.

## 6. La tipografía del nombre

**«Quimbaya» va siempre en Instrument Serif cursiva.** Es la misma cursiva que el sistema ya
usaba como único contraste tipográfico, en dos o tres sitios contados; que el nombre sea
precisamente esa letra ata la marca al diseño en vez de añadirle una voz nueva. En grotesca el
nombre funciona, pero se vuelve cualquier producto.

El descriptor va en Schibsted Grotesk 600, en versales y con tracking, como los rótulos de la
interfaz.

## 7. Colores

Los de la paleta, sin inventar ninguno (`frontend/tailwind.config.js`).

| Uso | Token | Claro | Oscuro |
|---|---|---|---|
| Campo del icono | jade-800 | `#093b30` | `#093b30` |
| Contorno sobre el campo | papel | `#f7f6f3` | `#f7f6f3` |
| Contorno en registro editorial | tinta / papel | `#191a17` | `#f2f1ea` |
| Nivel | emerald-600 | `#0e5c4a` | `#6fd1ad` |

El campo jade del icono es una excepción deliberada a la regla 2 de `tailwind.config.js` («el
esmeralda solo significa ahorro»). Esa regla gobierna la **interfaz**, donde el color es
información; un icono de aplicación es identidad y necesita un campo propio para distinguirse en
una pantalla de inicio. Dentro del símbolo la regla se respeta: lo único verde es el nivel, y el
nivel mide.

## 8. Qué no hacer

- No escribir «Quimbaya» en otra tipografía ni en redonda.
- No llenar el rombo del todo ni dejarlo vacío: el nivel es el dato.
- No poner el símbolo sobre un fondo que no sea papel, tinta o jade-800.
- No estirar el logotipo: las proporciones están fijas en el `viewBox`.
- No usar el poporo, la nariguera ni ninguna pieza de museo como marca.

## 9. Cómo se regenera

La geometría es la misma en los SVG y en `Marca.tsx`; si se toca, hay que rehacer los dos. Lo
que manda es el lienzo de 512 y estos valores:

```
rombo       M256 60 L406 256 L256 452 L106 256 Z     (a = 150, b = 196)
nivel       44 % del alto, medido desde abajo
trazo       30 en el registro de aplicación, 22 en el editorial
nivel con contorno   M146.16 275.57 H365.84 L256 419.09 Z
nivel macizo         M124 279.52 H388 L256 452 Z
```

El rombo interior se obtiene metiendo el contorno hacia dentro una distancia igual a medio trazo
más 9; la distancia del centro de un rombo a su lado es `a·b/hipotenusa`, y de ahí salen las dos
semidiagonales interiores.

## 10. Lo que esto no es

No es una identidad cerrada. No hay tipografía de marca propia, ni versiones para impresión a
una tinta, ni reglas de co-branding con la universidad. Hay un símbolo coherente con el sistema
visual que ya existía, un nombre con razón de ser y los archivos para usarlo sin improvisar.
