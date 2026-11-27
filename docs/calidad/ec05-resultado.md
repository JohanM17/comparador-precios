# EC-05 — Resultado medido del módulo comercial

**Tarea:** `T-69` del plan de construcción. **Entregable 10, parte 2.**
**Fecha de registro:** 26 de noviembre de 2026.
**Contrasta con:** [`ec05-estimado.md`](ec05-estimado.md), confirmado en Git antes de `T-61`.

> EC-05 mide si la arquitectura puede evolucionar sin rediseñarse. El documento previo declaró,
> antes de escribir una línea, qué contaría como rediseño estructural. Este contrasta aquella
> predicción con lo que ocurrió. Cuando el resultado no coincide, se dice; la guía valora que una
> decisión inadecuada se identifique, no que nunca ocurra.

---

## 1. Contra qué se midió

La línea base es `origin/develop` en el commit `898bfe8`, es decir el núcleo del corte 2 **más**
la ampliación `A2 + B1` ya integrada. No es la base contra la que se escribió la estimación: el
módulo comercial se construyó en paralelo a la ampliación y se incorporó después, sobre ella.

Eso endurece la prueba en vez de ablandarla. El módulo no solo tuvo que entrar sin rediseñar el
núcleo, sino también sin chocar con un historial de precios y una capa de observabilidad que no
existían cuando se hizo la predicción.

---

## 2. Los cinco indicadores

| # | Qué contaría como rediseño estructural | Predicción | Resultado |
| :--- | :--- | :--- | :--- |
| 1 | Modificar o eliminar una columna existente del núcleo | 0 | **0** |
| 2 | Cambiar la firma del protocolo `PoliticaPrecioReferencia` | 0 | **0** |
| 3 | Modificar un módulo de `backend/app/dominio/` existente | 0 | **1, aditivo** |
| 4 | Que `precios` tenga que importar `comercial` | 0 | **0** |
| 5 | Romper el contrato de un endpoint ya publicado en `/v1` | 0 | **0** |

### 2.1 Columnas del núcleo — cero

`0006_modulo_comercial.sql` no contiene `drop`, `alter column`, `rename`, `delete` ni `truncate`.
Sobre tablas existentes hace una sola cosa: añadir tres columnas anulables a `precio_vigente`
(`precio_oficial_cop`, `diferencia_pct`, `requiere_revalidacion`). Todo lo demás es tabla nueva.

### 2.2 Firma del puerto — cero

El protocolo `PoliticaPrecioReferencia` llegó sin tocar. `SoloUsuarios`, la implementación de
Etapa 1, conserva su comportamiento y sigue siendo la que se usa por omisión. Lo que se añadió es
una segunda implementación, `OficialConContraste`, que el servicio recibe por constructor.

Comparando la superficie pública del archivo antes y después, no desapareció ni se renombró nada:
solo aparecen la clase nueva y los lectores privados que ambas implementaciones comparten.

### 2.3 Dominio existente — uno, y hay que decirlo

**Aquí la predicción no se cumple al pie de la letra.** El indicador 3, como está redactado, dice
«modificar **cualquier** módulo de `backend/app/dominio/` existente». `parametros.py` cambió.

El cambio es de **24 líneas añadidas y cero eliminadas**: cuatro campos nuevos de disputa que se
leen de dos claves compuestas que ya estaban sembradas en `config_parametro` desde la migración
`0002`. Ningún campo existente cambió de nombre, de tipo ni de valor por omisión, y ninguna
llamada existente se rompió.

Los siete módulos que la tabla de impacto nombró uno por uno —`sello.py`, `vigencia.py`,
`orden.py`, `unidades.py`, `anomalia.py`, `riesgo.py` y `reputacion.py`— no se tocaron. La tabla
de impacto, además, ya había estimado una hora para `parametros.py`.

La lectura honesta es que **la predicción de la tabla se cumplió y el enunciado del indicador
estaba mal calibrado**: tratar un archivo de configuración tipada igual que una regla de negocio
convierte en «rediseño estructural» algo que es leer un parámetro más. Se deja escrito así, con
el indicador original a la vista, en vez de reescribirlo para que cuadre.

### 2.4 Dirección de dependencias — cero

`lint-imports` sobre 124 archivos y 567 dependencias: **3 contratos, 3 cumplidos, 0 rotos**,
incluido «Precios nunca importa el modulo comercial (EC-06)».

La comparación sí necesita las promociones que publica un comercio, y resolverlo importando el
módulo comercial habría sido lo directo. En su lugar se añadió el puerto `PuertoPromociones`, con
el mismo patrón que el núcleo ya usaba para la política de precio: `precios` depende de una
abstracción propia y nunca del módulo comercial. Esa frontera es lo que sostiene EC-06, y por eso
se defendió aunque costara un archivo más.

### 2.5 Contrato de `/v1` — cero

Regenerando `docs/api/openapi.json` contra la línea base:

| Medida | Resultado |
| :--- | :--- |
| Rutas antes / después | 38 → 45 |
| Rutas eliminadas | **0** |
| Rutas existentes con contenido distinto | **0** |
| Esquemas eliminados | **0** |
| Esquemas existentes modificados | **0** |
| Esquemas nuevos | 12 |

Las siete rutas nuevas viven todas bajo `/v1/comercio` y `/v1/moderacion/comercios`. Ningún
cliente del contrato anterior necesita cambiar.

Los campos `precio_oficial_cop` y `promociones` de la comparación **no son nuevos**: el núcleo ya
los publicaba vacíos, por la decisión `D-14`. Mantenerlos con su tipo original, aunque un modelo
tipado para las promociones habría quedado más limpio, fue deliberado: cambiarlos habría roto
este indicador por una mejora cosmética.

---

## 3. Verificación ejecutada

| Comprobación | Resultado |
| :--- | :--- |
| `ruff check` | limpio |
| `mypy --strict backend/app` | sin problemas en 93 archivos |
| `lint-imports` | 3 contratos cumplidos, 0 rotos |
| `pytest backend/tests/unitarias` | **288 pruebas, todas en verde** |
| Sincronización del contrato OpenAPI | regenerado; sin rutas ni esquemas perdidos |
| `tsc --noEmit` y `next lint` | limpios |
| `scripts/migrar.py` sobre Supabase | `0006` aplicada; una sola migración pendiente |
| API en vivo contra la base migrada | comparación, historial y catálogo en `200`; las tres rutas comerciales en `401` sin credencial |

De esas 288 pruebas, 36 son del módulo comercial y se escribieron antes que el código que
verifican: 12 de la regla de contraste `D-01`, 16 de la validación de promociones de la Ley 1480,
4 de coherencia entre los parámetros nombrados en el SQL y las claves del diccionario, y 4 del
puerto de promociones.

---

## 4. Esfuerzo real

| Bloque | Estado |
| :--- | :--- |
| Horas reales por componente | **Pendiente.** Las registra el equipo. |

Las celdas de esfuerzo real de `ec05-estimado.md` siguen vacías a propósito. Rellenarlas con una
inferencia destruiría justamente lo que el entregable 6 quiere contrastar. El criterio es el mismo
que aplicó la ampliación `A2 + B1` en `specs/002-ampliacion-corte3/impacto.md`.

**Desviación conocida que debe registrarse al llenarlas:** la estimación no contempló incorporar
el módulo sobre la ampliación `A2 + B1`. Esa reincorporación costó resolver tres conflictos
—el puerto de precio, el contrato OpenAPI y el cliente tipado del frontend—, renumerar la
migración de `0004` a `0006` y llevar al lector extraído el filtro `es_demo = false` que `A2`
había añadido a la consulta de candidatos.

---

## 5. La migración sobre la base compartida

`0006_modulo_comercial.sql` se aplicó el 26 de noviembre de 2026 con `scripts/migrar.py`, que la
ejecuta en una transacción y la registra. Antes se ensayó en una transacción revertida para
comprobar que el SQL era válido contra el esquema real.

| Comprobación posterior | Resultado |
| :--- | :--- |
| `_migraciones_historial` | `0001`, `0002`, `0003`, `0005`, `0006`, en ese orden |
| Filas de `producto` / `establecimiento` / `reporte_precio` / `precio_vigente` | 134 / 43 / 1797 / 624, idénticas a antes |
| Índice `idx_reporte_historial_serie` de A2 | intacto |
| Tablas nuevas | las tres, con *row level security* activa (`ADR-012`) |
| Columnas nuevas en `precio_vigente` | `precio_oficial_cop` y `diferencia_pct` anulables; `requiere_revalidacion` con valor por omisión `false` |

El orden del historial es la razón del renumerado. Con el nombre original se habría leído
`0001, 0002, 0003, 0005, 0004`, y el orden de los archivos habría dejado de significar el orden
de aplicación.

---

## 6. Lo que este documento no afirma

- **Solo se verificaron las lecturas.** La comparación, el historial y el catálogo responden
  contra la base migrada, y las rutas comerciales rechazan correctamente a quien no se
  identifica. La **escritura** en las columnas y tablas nuevas no se ha ejercitado contra la base.
- **No hay pruebas de integración ejecutadas** sobre el esquema comercial. La suite de
  `backend/tests/integracion` no aísla sus escrituras en transacciones revertidas, así que
  correrla contra la base compartida dejaría datos. Para eso quedó
  [`infra/pruebas/`](../../infra/pruebas/README.md): una base desechable en contenedor, con los
  roles `anon` y `authenticated` que Supabase trae y Postgres no. Ejecutar la suite contra ella
  es `T-68` y todavía está pendiente.
- **La política por omisión no cambió.** `ServicioPrecios`, `servicio_casos` y el trabajo de
  reconstrucción siguen usando `SoloUsuarios`. `OficialConContraste` solo es la implementación
  por omisión dentro del servicio comercial, que es donde corresponde.
- **EC-05 mide modificabilidad, no corrección funcional.** Que el módulo entre sin rediseñar el
  núcleo no dice que sus reglas sean las correctas; eso lo dicen las pruebas de dominio y, cuando
  existan, las de integración.
