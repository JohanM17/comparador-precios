# Entregable 7 — Protocolo Experimental y Validación de Usabilidad `EC-01` ($\le 15\text{ s}$)

- **Proyecto:** Plataforma Colaborativa de Comparación de Precios de la Canasta Familiar
- **Escenario Evaluado:** `EC-01` — Captura rápida de precio frente a góndola desde dispositivo móvil
- **Pantalla y Modo de Instrumentación:** `S4` (`/reportar?medicion=1`), implementada en `frontend/src/components/FormularioReportar.tsx`
- **Umbral de Aceptación:** Al menos el **80 %** de los intentos válidos ($\ge 24$ de $30$ ejecuciones) completados en **$\le 15\,000\text{ ms}$ ($\le 15\text{ s}$)** bajo conexión móvil limitada (`3G/4G` lenta) o modo sin conexión (`IndexedDB`).
- **Estado de Evidencia:**
  - ✅ **Instrumentación técnica, flujo `F4`, teclado y accesibilidad WCAG 2.2 AA:** Verificados en código y mediante Playwright + `axe-core` (`10 passed` en `frontend/tests/e2e/accesibilidad.spec.ts`).
  - ⏳ **Ejecución presencial con 10 participantes reales (30 intentos):** Protocolo, cronómetro `?medicion=1` y matriz de registro estructurados y listos para captura de campo sin datos simulados fabricados.

---

## 1. Instrumentación Empírica en `S4` (`?medicion=1`)

La pantalla `/reportar` incluye soporte nativo para el parámetro de consulta `?medicion=1`:

1. Al montar `FormularioReportar` (`useSearchParams().get("medicion") === "1"`), se captura `inicioMsRef.current = performance.now()` y se renderiza el cronómetro de alta precisión (`<output data-testid="cronometro-ec01">`) actualizado cada `50 ms`.
2. Al confirmarse el guardado —ya sea en línea tras completar el Flujo `F4` (`sincronizarColaReportes`) o localmente sin red al encolar en `IndexedDB` (`encolarReporteOffline`)— se congela `msFinal = Math.round(performance.now() - inicioMsRef.current)`.
3. El banner de confirmación muestra el tiempo exacto en milisegundos y segundos, junto con la evaluación automática frente al umbral (`"Umbral EC-01 cumplido (<= 15 s)."` o `"Superó 15 s; revisar pasos."`).

---

## 2. Protocolo Experimental Bajo Red Móvil Limitada

### 2.1 Condiciones de Entorno y Perfil de Red

- **Dispositivo / Emulación:** Teléfono móvil real (viewport táctil de `360x800` a `412x915`) o Chrome DevTools en modo dispositivo móvil (`Touch` habilitado).
- **Perfil de red simulada (`3G/4G` lenta):**
  - **Intento 1 y 2 (red lenta):** DevTools -> *Network* -> perfil **`Slow 4G`** (~`400 Kbps` bajada, `150 ms` RTT) o **`Slow 3G`** (~`400 Kbps`, `2000 ms` RTT) para validar que las búsquedas debounced (`200 ms`) y la subida WebP no bloqueen la percepción de respuesta.
  - **Intento 3 (resiliencia offline Flujo `F4`):** Activar modo avión / `Offline` antes de pulsar **`Guardar precio`**, confirmar registro inmediato en `IndexedDB` (`comparador_precios_offline` -> almacén `cola_reportes`), y luego restaurar la red verificando la sincronización automática Subpaso A (`POST /v1/fotos/url-subida` + `PUT` WebP) $\rightarrow$ Subpaso B (`POST /v1/reportes` con la misma `Idempotency-Key` UUIDv4) $\rightarrow$ Subpaso C (eliminación de cola al recibir `201` o `200`).
- **Precondiciones del participante:** Sesión activa en `/ingresar` con consentimiento Ley 1581 vigente y catálogo/tiendas cargados previamente o buscables por nombre.

### 2.2 Guion Estandarizado por Intento

1. El observador entrega al participante un producto real de la canasta familiar con su etiqueta de precio visible (ej. Arroz blanco 500 g — `$ 2.600`).
2. El participante abre `/reportar?medicion=1` (momento cero del cronómetro `performance.now()`).
3. El participante ejecuta los **3 controles** en orden:
   - **Paso 1 (`SelectorTienda`):** Confirma la tienda preseleccionada (si visitó hace `< 2 h`) o busca/selecciona el establecimiento objetivo.
   - **Paso 2 (`SelectorPresentacion`):** Toca una de las **5 presentaciones recientes** o escribe las primeras letras del producto.
   - **Paso 3 (`CampoPrecio`):** Ingresa los dígitos en el teclado numérico (`inputMode="numeric"`) viendo el formateo automático de miles en vivo.
   - *(Opcional en al menos 1 intento)*: Adjunta fotografía para validar compresión cliente `<canvas>` a `image/webp` ($\le 1280\text{ px}$, $\le 300\text{ KB}$, sin metadatos EXIF).
4. Pulsa **`Guardar precio`** y se registra el valor final mostrado en `cronometro-ec01`.

---

## 3. Matriz de Registro de Campo (10 Participantes × 3 Intentos = 30 Ejecuciones)

> **Nota metodológica:** Las celdas permanecen listas para registro en campo (`Pendiente campo`) con el fin de preservar la integridad científica del informe y evitar datos sintéticos presentados como usuarios reales.

| Participante | Perfil / Familiaridad Móvil | Red (Intento 1 / 2 / 3) | Intento 1 (ms) | Intento 2 (ms) | Intento 3 (ms) | Foto WebP ($\le 300\text{ KB}$) | Sinc. Offline F4 | Cumple $\le 15\,000\text{ ms}$ ($\ge 2/3$) | Observaciones de Fricción |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `P01` | Consumidor frecuente | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |
| `P02` | Consumidor frecuente | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |
| `P03` | Adulto mayor / uso básico | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |
| `P04` | Estudiante universitario | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |
| `P05` | Comprador semanal | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |
| `P06` | Tendera / auxiliar | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |
| `P07` | Consumidor ocasional | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |
| `P08` | Usuario baja conectividad | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |
| `P09` | Consumidor frecuente | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |
| `P10` | Adulto uso medio | Slow 4G / Slow 3G / Offline | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | _Pendiente_ | |

---

## 4. Análisis Estadístico del Umbral (`EC-01`)

Al concluir las $N = 30$ ejecuciones de la matriz anterior, la evaluación del escenario se calcula con las siguientes métricas:

1. **Tasa de éxito temporal ($p$):**
   $$p = \frac{k}{30} \times 100\,\%$$
   donde $k$ es el número de intentos válidos con `msFinal <= 15000` y envío sin error de validación no recuperable (`HTTP 422`).
   - **Criterio de aceptación:** $k \ge 24$ ($p \ge 80.0\,\%$).
2. **Medidas de tendencia y dispersión sobre $\{t_1, \dots, t_{30}\}$:**
   - **Mediana ($P_{50}$):** Tiempo típico esperado de captura tras el segundo intento.
   - **Percentil 80 ($P_{80}$):** Debe ubicarse en $\le 15\,000\text{ ms}$ para satisfacer directamente el umbral `EC-01`.
   - **Percentil 95 ($P_{95}$):** Permite identificar cuellos de botella en red `Slow 3G` o compresión de cámara en dispositivos de gama baja.
3. **Curva de aprendizaje (Intento 1 vs. Intento 3):**
   - Diferencia pareada $\Delta_i = t_{i,1} - t_{i,3}$ para cuantificar la ganancia real de la **preselección automática de tienda reciente (`< 2 h`)** y las **5 presentaciones recientes** fijadas en la parte superior de `SelectorPresentacion`.
4. **Verificación de latencia técnica de render e interacción en `S4`:**
   - Durante la auditoría automatizada Playwright (`accesibilidad.spec.ts`), la ruta `/reportar?medicion=1` renderizó el cronómetro `cronometro-ec01`, mantuvo navegabilidad secuencial por teclado (`Tab`) y formateó la entrada `"2600"` como `"2.600"` con `0` violaciones críticas o serias WCAG 2.2 AA (`10 passed` en la suite completa).

---

## 5. Decisiones de Diseño Ergonómico Aplicadas en `S4`

Cada componente de `S4` fue diseñado específicamente para reducir carga cognitiva, toques en pantalla y dependencia de red frente a una góndola de supermercado o tienda de barrio:

| Decisión Ergonómica | Archivo / Implementación | Impacto en Tiempo ($\le 15\text{ s}$) y Privacidad |
| :--- | :--- | :--- |
| **Reducción estricta a 3 controles esenciales** | `FormularioReportar.tsx` (`SelectorTienda`, `SelectorPresentacion`, `CampoPrecio`) | Elimina formularios multipágina y campos accesorios; la foto queda como botón opcional en un solo toque. |
| **Objetivos táctiles WCAG $\ge 44\text{ px}$ (`min-h-11` / `min-h-14`)** | `SelectorTienda.tsx`, `SelectorPresentacion.tsx`, `CampoPrecio.tsx` | Minimiza errores de pulsación con una mano sosteniendo productos o bolsa de compras. |
| **Preselección de tienda reciente (`< 2 h`)** | `cacheSelectores.ts` (`sessionStorage`, TTL `2 h`) | Evita repetir la búsqueda del establecimiento cuando el usuario reporta varios productos en la misma visita a tienda. |
| **GPS volátil estrictamente en memoria** | `SelectorTienda.tsx` (`navigator.geolocation` -> parámetros de consulta) | Ordena por cercanía sin persistir `lat`/`lng` del usuario en almacenamiento local ni base de datos (Ley 1581). |
| **Top 5 presentaciones recientes + caché local** | `SelectorPresentacion.tsx`, `cacheSelectores.ts` | Reduce el flujo de selección de producto a un único toque en los ítems más consultados/reportados, incluso sin red. |
| **Teclado numérico nativo y miles en vivo** | `CampoPrecio.tsx` (`inputMode="numeric"`, `Intl.NumberFormat("es-CO")`) | Despliega teclado numérico directo en iOS/Android y previene errores de ceros al mostrar `$ 2.600` y recordar IVA incluido. |
| **Compresión WebP cliente sin EXIF** | `comprimirFoto.ts` (`<canvas>`, `<= 1280 px`, `<= 300 KB`) | Ahorra hasta >90 % del ancho de banda móvil en `3G/4G` lenta y elimina metadatos EXIF GPS/cámara antes de salir del teléfono. |
| **Persistencia offline instantánea (`IndexedDB`) e idempotencia `F4`** | `colaReportes.ts` (`comparador_precios_offline/cola_reportes`, `Idempotency-Key` UUIDv4) | Garantiza confirmación visual en `< 100 ms` sin señal y sincronización ordenada (Subpasos A, B y C) al reconectar sin duplicar registros. |

