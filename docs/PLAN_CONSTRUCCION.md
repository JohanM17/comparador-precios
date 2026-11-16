# Plan de Construcción y Especificación Técnica Maestra (SDD)
**Plataforma Colaborativa de Comparación de Precios — Armenia y Quindío**
**Versión:** 2.0 · **Metodología:** Spec-Driven Development (GitHub Spec Kit + TDD)

---

## Cómo usar este documento

Este documento complementa a `PROYECTO.md` y constituye la especificación ejecutable para el desarrollo asistido por agentes de IA bajo **GitHub Spec Kit**. Ningún agente ni desarrollador puede inventar reglas, tablas, rutas ni componentes fuera de lo estipulado aquí.

### Etiquetas de estado en la especificación
| Etiqueta | Significado | Acción obligatoria para el agente de IA |
| :--- | :--- | :--- |
| **`DECIDIDO`** | Definido en firme en la guía académica o en `PROYECTO.md`. | Implementar exactamente como está especificado, sin alteraciones. |
| **`APROBADO`** | Decisión de diseño (`D-01` a `D-14`) aprobada por el equipo para cerrar preguntas abiertas. | Implementar la lógica en código y leer todos sus números desde la tabla `config_parametro`. |
| **`PROPUESTA`** | Valor numérico inicial calibrable (umbrales, pesos, tamaños de muestra). | Sembrar en `config_parametro` por migración; prohibido escribirlo como constante mágica en el código. |
| **`POR CONFIRMAR`** | Dato operativo externo pendiente de definición (registrado en `PA-01` a `PA-04`). | Usar la variable de entorno o *placeholder* indicado y mantener la entrada en `docs/PREGUNTAS_ABIERTAS.md`. |

---

## 0. Reglas Obligatorias de Ejecución para el Agente de IA

1. **Fuente única de verdad:** Este documento, `PROYECTO.md` y los artefactos de `specs/` son el contrato del sistema. Si encuentras un vacío o contradicción, no adivines: regístralo en `docs/PREGUNTAS_ABIERTAS.md` (con `ID`, `Contexto`, `Opciones` y `Recomendación`) y detén la tarea actual.
2. **Flujo SDD y una sola tarea a la vez:** Sigue el orden de la Sección 8 (`T-00` a `T-90`). No marques una tarea como `[x]` ni avances a la siguiente hasta ejecutar los comandos de verificación de su columna **«Hecho cuando…»** con todas las pruebas en verde.
3. **TDD estricto en el dominio (Innegociable):** Todo archivo dentro de `backend/app/dominio/` se construye en tres pasos: (1) prueba unitaria en `pytest` que falla (`test:`), (2) código mínimo puro que pasa la prueba (`feat:`), y (3) limpieza manteniendo pruebas en verde (`refactor:`).
4. **Protección del código existente:** Antes de modificar un archivo que ya funciona, explica en 3 a 5 líneas qué cambiarás y por qué. Nunca borres código ni pruebas que pasan sin autorización explícita.
5. **Idioma y convenciones de nombres:**
   * Comentarios, docstrings, documentación OpenAPI y textos visibles al usuario: **español de Colombia (`es-CO`)**.
   * Identificadores de negocio en Python y PostgreSQL (tablas, columnas, funciones, variables): **español en `snake_case` sin tildes ni letra `ñ`** (ej. `precio_cop`, `establecimiento`, `cantidad_base`, `sello_precio`, `ano`).
   * Identificadores en TypeScript/React: **español en `camelCase` para variables/props y `PascalCase` para componentes/tipos** (`TarjetaProducto`, `precioPorUnidad`).
   * Términos técnicos estándar en inglés (`cache`, `token`, `middleware`, `router`, `healthcheck`, `cursor`).
6. **Migraciones solo hacia adelante:** Todo cambio al esquema SQL se hace creando una nueva migración numerada en `supabase/migrations/`. Jamás edites una migración ya aplicada.
7. **Cero constantes mágicas de negocio:** Todos los umbrales, pesos, ventanas y límites viven en la tabla `config_parametro` (Sección 2.3), sembrados por migración y leídos con caché en memoria de 60 s.
8. **Seguridad por defecto:** Todo esquema de entrada usa Pydantic v2 con `model_config = ConfigDict(extra='forbid')`. Toda consulta SQL es parametrizada. El backend se conecta en operación normal con el rol de privilegios mínimos `app_backend` (nunca con `postgres`).
9. **Orden de prioridad ante conflictos:** (1) Ley colombiana y privacidad (Ley 1581 / Ley 1480) > (2) Escenarios de calidad (`EC-01` a `EC-06`) > (3) Este documento > (4) Preferencias de estilo.
10. **Datos de demostración declarados:** Todo registro sintético lleva `es_demo = true` y activa el banner visible en pantalla *«Datos de demostración»*.
11. **Tiempo y dinero:**
    * Fechas: siempre `timestamptz` en UTC en la base de datos y cadenas ISO 8601 en UTC (`YYYY-MM-DDTHH:MM:SSZ`) en la API. Solo se formatean a `America/Bogota` al pintarse en el navegador.
    * Dinero: siempre entero estricto en pesos colombianos (`precio_cop: int`). Prohibido usar `float` para dinero o cantidades; los cálculos por unidad usan `decimal.Decimal` en Python y `numeric` en PostgreSQL.
12. **Trazabilidad arquitectónica:** Toda decisión estructural nueva genera un archivo ADR en `docs/adr/NNNN-titulo.md`.
13. **Modo docente y guía manual (Regla obligatoria):** En cada tarea T-xx, actúa como un profesor experto en Ingeniería de Software: al terminar cada paso explica brevemente en lenguaje sencillo qué arquitectura o patrón aplicaste y por qué; y si la tarea requiere que el desarrollador configure algo en el navegador (Supabase, MCP, Upstash, GitHub o Vercel), detente y dale primero las instrucciones paso a paso.
14. **Entorno local sin Docker:** El entorno de desarrollo local y las pruebas de integración no utilizan Docker Desktop ni docker-compose en la PC. Se conectan directamente al proyecto de Supabase (vía MCP y variables en `.env`) y a Redis en Upstash (o mock en memoria para pruebas unitarias/carga local sin gastar cuota). El `Dockerfile` se mantiene únicamente para el despliegue en la nube en T-50.

---

## 1. Principios Arquitectónicos, Límites de Infraestructura y Preguntas Abiertas

### 1.1 Los 6 principios de diseño
1. **El backend decide, el frontend pinta:** FastAPI calcula precios por unidad base, vigencia, sellos de confianza, orden en dos bloques y separación de promociones. El frontend nunca calcula ni reordena.
2. **Modelo de lectura precalculado (`CQRS` ligero en la misma BD):** Las escrituras se insertan en el historial inmutable `reporte_precio` y actualizan en la misma transacción la fila correspondiente de `precio_vigente`. Las lecturas públicas consultan solo `precio_vigente` más caché.
3. **Evidencia inmutable:** Las tablas `reporte_precio` y `auditoria` son *append-only*, protegidas por triggers en PostgreSQL y revocación de permisos `DELETE` al rol `app_backend`.
4. **Neutralidad comercial garantizada por diseño y verificada con pruebas (`EC-06`):** El módulo `precios` tiene prohibido importar al módulo `comercial` (`import-linter`). Las promociones viajan en un arreglo separado `promociones` y jamás alteran el orden de `resultados`.
5. **Privacidad por diseño (Ley 1581):** Coordenadas GPS (`lat`, `lng`) procesadas solo en RAM y filtradas de los logs; dirección IP transformada con `HMAC-SHA256` rotativo diario (`huella_red`) con purga a los 30 días; fotos limpiadas de EXIF; anonimización completa al borrar cuenta.
6. **Núcleo preparado para medir `EC-05`:** El núcleo (Etapa 1) no incluye las tablas comerciales; deja únicamente tres ganchos: el puerto `PoliticaPrecioReferencia`, la columna nula `establecimiento.comercio_id` y el arreglo `"promociones": []` reservado en la comparación.

### 1.2 Salvaguardas de infraestructura para Presupuesto Costo Cero
* **Supabase Free ($0):** 500 MB en BD, 1 GB en Storage, 5 GB de salida y 50.000 usuarios activos/mes. El job diario `ping_bd` ejecuta una consulta real a PostgreSQL para evitar la pausa automática por inactividad de 7 días, y un workflow semanal ejecuta `pg_dump` cifrado.
* **Upstash Redis Free ($0):** 500.000 comandos/mes. Se protege mediante caché de dos niveles (L1 en memoria de 5 s + L2 en Redis de 60 s con 1 comando `HGET` por fallo de L1), límites de uso (*rate limiting*) en memoria del proceso y ejecución de pruebas unitarias o de carga `k6` localmente contra un mock en memoria (o instancia local) para no agotar la cuota de Upstash.
* **Vercel Hobby ($0) + Contenedor Docker en Railway / Contingencia ($0):** El backend se despliega con Docker estándar usando el crédito inicial de prueba de Railway ($5 USD) y puede migrarse sin cambios de código a Render Free o Fly.io (`ADR-017`).

### 1.3 Registro inicial de `docs/PREGUNTAS_ABIERTAS.md` (`POR CONFIRMAR`)
| ID | Contexto | Placeholder técnico actual | Estado |
| :--- | :--- | :--- | :--- |
| **PA-01** | Nombre del responsable y correo oficial para consultas/reclamos de Ley 1581 y cabecera `User-Agent` de Open Food Facts. | Variable `CONTACTO_LEGAL_EMAIL=por-confirmar-equipo@cue.edu.co` y texto `[POR CONFIRMAR: Correo oficial del equipo]`. | `POR CONFIRMAR` |
| **PA-02** | Esquema de firma de JWT activo en el proyecto de Supabase creado para producción (asimétrico `JWKS` ES256/RS256 vs. secreto legado `HS256`). | `seguridad.py` soporta ambos: usa `SUPABASE_JWKS_URL` si está definida; de lo contrario usa `SUPABASE_JWT_SECRET`. | `POR CONFIRMAR` |
| **PA-03** | Distribución operativa entre los 4 integrantes para el levantamiento de campo en 5 a 8 tiendas de Armenia (`supabase/seed/precios_semilla.csv`). | Estructura CSV y script `scripts/semilla.py` listos; carga de prueba con `es_demo = true` mientras se levanta el campo. | `POR CONFIRMAR` |
| **PA-04** | Proveedor definitivo de alojamiento del contenedor al agotar los $5 USD de prueba de Railway (Railway Hobby vs. Render Free / Fly.io). | Imagen Docker multi-etapa agnóstica lista para cualquiera de los tres proveedores (`ADR-017`). | `POR CONFIRMAR` |

---

## 2. Especificación Funcional, Decisiones (`D-01` a `D-14`) y Parámetros

### 2.1 Historias de Usuario y Escenarios de Aceptación (`Given / When / Then`)

* **US-1 (P1 — Consumidor): Consultar y comparar precios por unidad de medida**
  * *Descripción:* Como consumidor sin cuenta, quiero buscar un producto de la canasta familiar y comparar su precio entre establecimientos de Armenia ordenado por precio por unidad de medida (kg, litro o unidad), viendo qué tan confiable y reciente es cada dato.
  * *Prueba independiente:* Consultar un producto con presentaciones de distinto tamaño en varias tiendas y verificar el orden y cálculo por unidad.
  * *Escenarios:*
    1. **Given** que en el mismo producto `"Arroz blanco"` la Tienda A tiene presentación de `1 kg` a `$5.000` (`$5.000/kg`) y la Tienda B tiene presentación de `500 g` a `$2.800` (`$5.600/kg`) ambos vigentes, **When** el consumidor consulta la comparación con el orden por defecto (`precio_unitario`), **Then** la Tienda A aparece primero que la Tienda B.
    2. **Given** que un establecimiento tiene únicamente reportes de hace 10 días (entre 8 y 30 días), **When** el consumidor consulta la comparación, **Then** dicho establecimiento aparece en el bloque secundario al final con el sello `desactualizado`.

* **US-2 (P1 — Reportante): Registrar un precio rápidamente frente a la góndola (`EC-01`)**
  * *Descripción:* Como reportante autenticado que aceptó la política de tratamiento de datos, quiero registrar el precio de una presentación en un establecimiento en 15 segundos o menos usando solo 3 controles, incluso si la señal móvil se cae en el local.
  * *Prueba independiente:* Completar un reporte en pantalla `/reportar` con red activa y en modo avión verificando su sincronización idempotente.
  * *Escenarios:*
    1. **Given** un reportante con autorización de datos vigente en `/reportar`, **When** selecciona tienda, presentación, digita `2600` y pulsa «Guardar precio» con una `Idempotency-Key` única, **Then** el sistema responde `201 Created` y actualiza `precio_vigente` en menos de 60 segundos (`EC-02`).
    2. **Given** que el celular pierde conexión antes de enviar, **When** el reportante pulsa «Guardar precio» y luego recupera la señal reintentando dos veces con la misma `Idempotency-Key`, **Then** el backend crea un único registro en `reporte_precio` y devuelve `200 OK` en el reintento.

* **US-3 (P1 — Sistema / Moderador): Filtrar reportes anómalos o ataques coordinados (`EC-03`)**
  * *Descripción:* Como moderador de la plataforma, quiero que el sistema evalúe determinísticamente cada reporte nuevo, impida que precios anómalos o ráfagas coordinadas alteren el precio vigente sin revisión y me los presente en una bandeja priorizada.
  * *Escenarios:*
    1. **Given** una presentación con 6 reportes recientes cuya mediana es `$2.600`, **When** un usuario reporta `$900` (`|M| > 3.5`), **Then** el reporte se guarda con `estado = 'dudoso'`, no altera el `precio_vigente`, abre un `caso_moderacion` y al reportante se le responde `"Recibido, en revisión"`.
    2. **Given** 3 cuentas distintas que envían reportes hacia el mismo establecimiento desde la misma `huella_red` en menos de 30 minutos, **When** entra el tercer reporte, **Then** el sistema activa la señal `rafaga`, reevalúa hacia atrás los reportes de esa ventana pasándolos a `dudoso` y recalcula `precio_vigente`.

* **US-4 (P2 — Titular de datos): Ejercer derechos de Ley 1581 de 2012**
  * *Descripción:* Como usuario registrado, quiero conocer mis datos, actualizar mi alias o eliminar mi cuenta de forma que mis reportes históricos queden completamente anónimos.
  * *Escenario:* **Given** un usuario con reportes y fotos subidas, **When** ejecuta `DELETE /v1/mi-cuenta`, **Then** sus filas en `reporte_precio` pasan a `reportante_id = null` y `foto_prueba_path = null`, los archivos se borran del bucket, su alias se reemplaza por un identificador anónimo y su usuario se elimina de Supabase Auth.

* **US-5 (P2 — Moderador / Consumidor): Gestionar catálogo y sugerencias**
  * *Descripción:* Como reportante o propietario de negocio, quiero sugerir una presentación faltante o solicitar corregir datos erróneos de una tienda para que un moderador lo valide.
  * *Escenario:* **Given** una sugerencia de presentación `"Arroz Roa 1/2 kg"`, **When** el moderador la aprueba, **Then** `dominio.unidades` calcula `cantidad_base = 500.000` (`g`), crea la presentación activa y deja registro en `auditoria`.

* **US-6 (P2 — Comercio en Etapa 2): Publicar precios oficiales y promociones sin alterar la neutralidad (`EC-05`, `EC-06`)**
  * *Descripción:* Como comercio verificado, quiero actualizar mis precios oficiales en modo rápido, revalidarlos con el botón «Todo sigue igual» y publicar promociones con condiciones claras sin alterar el ranking orgánico.
  * *Escenarios:*
    1. **Given** un establecimiento con precio oficial de `$2.600`, **When** en 48 h se reciben 3 reportes aceptados de 2 cuentas distintas con mediana de `$3.000` (diferencia >= 10 %), **Then** el sello pasa a `en_disputa`, se ordena con `$3.000` y se muestran ambos precios en pantalla.
    2. **Given** una consulta de comparación de un producto, **When** un comercio publica una promoción activa sobre ese producto, **Then** el arreglo `resultados` mantiene exactamente el mismo orden y la oferta aparece únicamente dentro del arreglo separado `promociones` con `es_promocion = true`.

### 2.2 Requisitos Funcionales (`FR-001` a `FR-026`)
* **FR-001:** El sistema **MUST** almacenar cada producto con una única `unidad_base` (`g`, `ml` o `unidad`) y cada presentación con su `cantidad_base` precalculada e inmutable.
* **FR-002:** El sistema **MUST** convertir las unidades de entrada (`g`, `kg`, `lb` colombiana = 500 g, `ml`, `l`, `unidad`, `docena`) usando aritmética exacta `Decimal` y rechazar unidades incompatibles con `422 UNIDADES_INCOMPATIBLES`.
* **FR-003:** El sistema **MUST** buscar productos y presentaciones ignorando mayúsculas y tildes (`unaccent`) y tolerando errores tipográficos (`pg_trgm`) y expresiones fraccionarias (`1/2 kg`, `medio kilo`).
* **FR-004:** El sistema **MUST** exigir aceptación previa de la política de tratamiento de datos (`POST /v1/mi-cuenta/autorizacion`) antes de crear el perfil o permitir reportar precios (`403 AUTORIZACION_REQUERIDA`).
* **FR-005:** El sistema **MUST** leer el rol del usuario exclusivamente desde la tabla `perfil` y jamás desde el `user_metadata` del JWT.
* **FR-006:** El sistema **MUST** permitir al titular consultar sus datos (`GET /v1/mi-cuenta`), modificar su alias (`PATCH /v1/mi-cuenta`) y suprimir su cuenta (`DELETE /v1/mi-cuenta`).
* **FR-007:** Al suprimir una cuenta, el sistema **MUST** anonimizar sus filas en `reporte_precio` (`reportante_id = null`, `foto_prueba_path = null`), borrar las fotos del almacenamiento, reemplazar `perfil.alias` por `'eliminado_' || left(id::text, 8)`, cambiar `perfil.estado = 'eliminada'`, registrar `revocada_en = now()` en `autorizacion_datos` y borrar la credencial en Supabase Auth.
* **FR-008:** El sistema **MUST** exigir la cabecera `Idempotency-Key` (UUID) en `POST /v1/reportes` y devolver el resultado original (`200 OK`) sin duplicar filas cuando la llave se repite para el mismo usuario.
* **FR-009:** El sistema **MUST** validar que `precio_cop` sea un entero estricto dentro del rango `[precio.min_cop, precio.max_cop]` de `config_parametro` (`422 PRECIO_FUERA_DE_RANGO`).
* **FR-010:** El sistema **MUST** validar que `observado_en` no sea futuro (tolerancia de reloj de 60 s) ni más antiguo que `observado.max_antiguedad_horas` (`422 FECHA_INVALIDA`).
* **FR-011:** El sistema **MUST** eliminar todos los metadatos EXIF (incluyendo coordenadas GPS) de las fotografías de prueba antes de almacenarlas de forma definitiva.
* **FR-012:** El sistema **MUST** impedir a nivel de base de datos (mediante trigger y permisos SQL) el borrado de filas en `reporte_precio` y la modificación de cualquier columna de evidencia original.
* **FR-013:** El sistema **MUST** seleccionar el conjunto de referencia para anomalías evaluando en orden 3 niveles jerárquicos (`presentacion_tienda`, `presentacion`, `producto_unitario`) y usar el estado de respaldo `sin_referencia` cuando ningún nivel alcance `anomalia.n_min_referencia` reportes aceptados dentro de `anomalia.ventana_dias`.
* **FR-014:** El sistema **MUST** evaluar anomalías de precio mediante *z-score* modificado ($M = 0.6745 \cdot (x - m) / \text{MAD}$) cuando $n \ge \text{anomalia.n\_min\_z}$ y $\text{MAD} > 0$, y mediante desviación porcentual ($|x - m| / m$) cuando $n \in \{3, 4\}$ o $\text{MAD} = 0$.
* **FR-015:** El sistema **MUST** calcular la huella de red como `HMAC-SHA256(ip_cliente, clave_derivada_del_dia)` y anular `huella_red = null` en todo registro con antigüedad mayor a `huella.retencion_dias` (30 días).
* **FR-016:** Al detectar la señal `rafaga`, el sistema **MUST** reevaluar hacia atrás todos los reportes de esa `huella_red` hacia ese `establecimiento_id` dentro de `rafaga.ventana_min`, pasando los afectados a `dudoso` y recalculando `precio_vigente`.
* **FR-017:** El sistema **MUST** ocultar al reportante las señales internas de detección, respondiendo siempre `201 Created` con `estado_visible = 'recibido'` o `'en_revision'`.
* **FR-018:** El sistema **MUST** recalcular la fila de `precio_vigente` en la misma transacción en que cambia el estado de un reporte o precio oficial e invalidar de inmediato la llave `cmp:{producto_id}` en caché (`EC-02` <= 60 s).
* **FR-019:** El sistema **MUST** ordenar los resultados de comparación en dos bloques (`Bloque 1`: `confiable`, `pocos_datos`, `oficial`, `en_disputa`; `Bloque 2`: `dudoso`, `desactualizado`), ordenando cada bloque por el criterio elegido (`precio_unitario` por defecto).
* **FR-020:** El sistema **MUST** garantizar que las coordenadas `lat` y `lng` enviadas en consultas públicas solo se usen en memoria para calcular `distancia_m` y nunca se guarden en base de datos ni en logs.
* **FR-021:** El sistema **MUST** registrar una fila inmutable en `auditoria` por cada acción de moderación, sanción, verificación de comercio o cambio en `config_parametro`.
* **FR-022 (Etapa 2):** El sistema **MUST** exigir que un establecimiento tenga `estado_verificacion = 'verificado'` y pertenezca al `comercio_id` autenticado antes de permitirle publicar precios oficiales o promociones.
* **FR-023 (Etapa 2):** El sistema **MUST** contrastar el precio oficial con los reportes comunitarios (`D-01`) y cambiar el sello a `en_disputa` mostrando ambos valores cuando al menos `disputa.min_reportes` de `disputa.min_cuentas` en `disputa.ventana_horas` difieran en >= `disputa.diferencia_pct`.
* **FR-024 (Etapa 2):** El sistema **MUST** exigir en toda promoción las condiciones de tiempo, modo y lugar, `vigente_desde`, y exactamente uno entre `vigente_hasta` o `hasta_revocar = true` (Ley 1480 art. 33).
* **FR-025 (Etapa 2):** El sistema **MUST** devolver las promociones en un arreglo separado `promociones` con `es_promocion = true`, sin alterar en ningún caso el orden de `resultados` (`EC-06`).
* **FR-026 (Fase 2):** El sistema **MUST** exigir confirmación manual explícita del usuario en la interfaz antes de crear un reporte cuyos campos hayan sido autocompletados por lectura fotográfica de IA.

### 2.3 Tabla completa de Decisiones Cerradas (`D-01` a `D-14` — `APROBADO`)
| ID | Tema | Regla técnica aprobada |
| :--- | :--- | :--- |
| **D-01** | Comercio vs. Usuarios | Puerto `PoliticaPrecioReferencia`. Etapa 1: `SoloUsuarios`. Etapa 2: `OficialConContraste` (muestra oficial salvo contradicción de >= 3 reportes de >= 2 cuentas en 48 h con diferencia >= 10 %; en contradicción usa mediana de usuarios, sello `en_disputa` y expone ambos precios). |
| **D-02** | Vigencia de precios | Peso 100 % durante 48 h, vida media cada 72 h. Vigente de 1 a 7 días; de 8 a 30 días sello `desactualizado` en Bloque 2; > 30 días fuera de comparación. Precio oficial > 30 días sin cambios marca `requiere_revalidacion = true`. |
| **D-03** | Detección de falsos | Determinista en 5 pasos (rango duro, 3 niveles de referencia + respaldo `sin_referencia`, z-score modificado / desviación %, riesgo de contexto y decisión `aceptado`/`dudoso`). Sanciones solo por moderador humano. |
| **D-04** | Reconocer productos | Catálogo cerrado en 2 niveles (`producto` con `unidad_base` única + `presentacion` con `cantidad_base` en `Decimal`). Comparación por `precio_por_base`. |
| **D-05** | Primeros datos | Semilla idempotente por CSV (~150 productos, ~30 establecimientos de Armenia con coordenadas OpenStreetMap bajo crédito ODbL, precios semilla y datos demo con `es_demo = true`). |
| **D-06** | Comercio pequeño | Aparece sin perfil por reportes comunitarios; con perfil verificado dispone de «Modo rápido» (20-30 productos) y botón «Todo sigue igual». |
| **D-07** | Neutralidad promocional | Tabla `promocion` y bloque JSON `promociones` separados de `resultados`. Prohibición de importación `precios -> comercial` verificada con `import-linter`. |
| **D-08** | Instantáneo vs. Diferido | Instantáneo: leer `precio_vigente` + caché, evaluar reporte, actualizar fila de `precio_vigente` e invalidar caché. Diferido (jobs): reputación (1 h), reconstrucción nocturna, limpieza de huellas (diaria) y supervisor IA (diario). |
| **D-09** | Verificación de comercio | Solicitud en `/v1/comercio/reclamos` y verificación manual por moderador sin almacenar documentos legales sensibles. |
| **D-10** | Reputación | Fórmula bayesiana $(A + 2) / (A + 3M + 4)$ con arranque en `0.500`. |
| **D-11** | Privacidad GPS y red | `lat`/`lng` solo en RAM y eliminados de logs. `huella_red = HMAC-SHA256(IP, clave_diaria)` con borrado a los 30 días. |
| **D-12** | Fallo de APIs externas | Ninguna API externa en el camino crítico de lectura o reporte. Timeout de 3 s, 2 reintentos y *circuit breaker* de 60 s tras 5 fallos. |
| **D-13** | Orden en dos bloques | Criterio por defecto: `precio_unitario` (`precio_por_base` ascendente). `Bloque 1` (vigentes) arriba y `Bloque 2` (`dudoso` y `desactualizado`) al final. |
| **D-14** | Ganchos para `EC-05` | El núcleo deja solo 3 ganchos (`PoliticaPrecioReferencia`, `establecimiento.comercio_id` nulo y `"promociones": []`), sin crear las tablas comerciales hasta la Ola 6. |

### 2.4 Los 43 Parámetros de Negocio (`config_parametro` — `PROPUESTA`)
| # | Clave (`clave`) | Valor por defecto (`valor`) | Descripción | Rango válido en `PUT /parametros` |
| :---: | :--- | :--- | :--- | :--- |
| 1 | `precio.min_cop` | `50` | Precio mínimo aceptado en COP | Entero `10..1000` |
| 2 | `precio.max_cop` | `2000000` | Precio máximo aceptado en COP | Entero `100000..10000000` |
| 3 | `precio.ratio_extremo` | `5.0` | Multiplicador/divisor respecto a la mediana para `ratio_extremo` | Número `2.0..20.0` |
| 4 | `observado.max_antiguedad_horas` | `24` | Horas máximas hacia atrás permitidas en `observado_en` | Entero `1..168` |
| 5 | `vigencia.fresco_horas` | `48` | Horas durante las cuales el reporte conserva factor temporal 1.0 | Entero `6..168` |
| 6 | `vigencia.vida_media_horas` | `72` | Horas para reducir el peso del reporte a la mitad | Entero `12..336` |
| 7 | `vigencia.vigente_dias` | `7` | Días máximos para considerar vigente un reporte de usuario | Entero `1..30` |
| 8 | `vigencia.antiguo_dias` | `30` | Días máximos para mostrar un reporte como `desactualizado` | Entero `8..90` |
| 9 | `vigencia.comercio_revalidar_dias` | `30` | Días sin cambios para marcar precio oficial como por revalidar | Entero `7..90` |
| 10 | `anomalia.ventana_dias` | `14` | Días de antigüedad máxima de reportes del conjunto de referencia | Entero `3..60` |
| 11 | `anomalia.n_min_referencia` | `3` | Mínimo de reportes aceptados para usar un nivel de referencia | Entero `2..10` |
| 12 | `anomalia.n_min_z` | `5` | Mínimo de reportes para usar z-score modificado | Entero `4..20` |
| 13 | `anomalia.z_umbral` | `3.5` | Umbral absoluto del z-score modificado | Número `2.0..6.0` |
| 14 | `anomalia.desviacion_pct_umbral` | `0.30` | Umbral de desviación porcentual cuando `n < 5` o `MAD = 0` | Número `0.10..0.80` |
| 15 | `riesgo.pesos` | `{"sin_foto":0.15,"cuenta_nueva":0.25,"rafaga":0.40,"reputacion_baja":0.20}` | Pesos de las 4 señales de contexto (suman 1.0) | Objeto JSON con suma `1.0` |
| 16 | `riesgo.umbral_dudoso` | `0.60` | Puntaje de riesgo de contexto para marcar reporte como `dudoso` | Número `0.30..0.95` |
| 17 | `cuenta_nueva.dias` | `7` | Días desde registro para considerar una cuenta como nueva | Entero `1..30` |
| 18 | `cuenta_nueva.min_aceptados` | `3` | Reportes corroborados mínimos para dejar de ser cuenta nueva | Entero `1..20` |
| 19 | `reputacion.inicial` | `0.500` | Reputación de arranque de todo perfil nuevo | Número `0.300..0.700` |
| 20 | `reputacion.baja_umbral` | `0.350` | Umbral por debajo del cual se activa la señal `reputacion_baja` | Número `0.100..0.490` |
| 21 | `reputacion.corroboracion_tolerancia` | `0.10` | Tolerancia porcentual (+/- 10 %) para considerar corroborado un reporte | Número `0.03..0.25` |
| 22 | `rafaga.ventana_min` | `30` | Ventana en minutos para detectar ráfaga desde la misma `huella_red` | Entero `5..120` |
| 23 | `rafaga.min_cuentas` | `3` | Cuentas distintas mínimas en la ventana para declarar `rafaga` | Entero `2..10` |
| 24 | `sello.n_min_validos` | `3` | Mínimo de reportes vigentes para otorgar sello `confiable` | Entero `2..10` |
| 25 | `sello.min_fuentes` | `2` | Mínimo de fuentes distintas para otorgar sello `confiable` | Entero `2..5` |
| 26 | `sello.dispersion_max` | `0.15` | Dispersión máxima (`MAD / mediana`) permitida para sello `confiable` | Número `0.05..0.40` |
| 27 | `peso.con_foto` | `1.2` | Multiplicador del peso cuando el reporte incluye fotografía | Número `1.0..2.0` |
| 28 | `cache.ttl_segundos` | `60` | Tiempo máximo de vida en caché de comparación (`EC-02`) | Entero `10..60` |
| 29 | `cache.l1_segundos` | `5` | Tiempo de vida en caché L1 de memoria del proceso | Entero `1..15` |
| 30 | `limite.reportes_hora_nuevo` | `20` | Máximo de reportes por hora para cuenta nueva | Entero `5..100` |
| 31 | `limite.reportes_hora_normal` | `60` | Máximo de reportes por hora para cuenta establecida | Entero `20..300` |
| 32 | `limite.reportes_dia` | `200` | Máximo de reportes por día por usuario | Entero `50..1000` |
| 33 | `limite.consultas_ip_min` | `120` | Máximo de lecturas públicas por minuto por IP | Entero `30..600` |
| 34 | `limite.escrituras_ip_min` | `20` | Máximo de escrituras por minuto por IP | Entero `5..100` |
| 35 | `limite.correcciones_ip_dia` | `3` | Máximo de solicitudes de corrección de tienda por día por IP | Entero `1..20` |
| 36 | `limite.fotos_hora_usuario` | `30` | Máximo de URLs firmadas de subida de foto por hora por usuario | Entero `5..120` |
| 37 | `foto.max_kb` | `300` | Tamaño máximo de archivo de foto de prueba en KB | Entero `100..1024` |
| 38 | `foto.tipos` | `["image/webp","image/jpeg"]` | Tipos MIME aceptados para fotografías de prueba | Arreglo no vacío |
| 39 | `huella.retencion_dias` | `30` | Días de retención de `huella_red` antes de su anulación | Entero `7..90` |
| 40 | `comparacion.radio_km` | `10.0` | Radio espacial por defecto en km para filtrar por cercanía | Número `1.0..50.0` |
| 41 | `comparacion.max_resultados` | `50` | Cantidad máxima de establecimientos devueltos en comparación | Entero `10..100` |
| 42 | `disputa.min_reportes_y_cuentas` | `{"min_reportes":3,"min_cuentas":2}` | Mínimo de reportes y cuentas para declarar disputa con precio oficial | Objeto JSON con enteros >= 2 |
| 43 | `disputa.ventana_y_diferencia` | `{"ventana_horas":48,"diferencia_pct":0.10}` | Ventana de horas y diferencia porcentual para declarar disputa | Objeto JSON válido |

---

## 3. Arquitectura de Ejecución y Archivos de Infraestructura

### 3.1 Estructura de carpetas del repositorio
```text
/
├─ .agents/skills/                  # Skills de GitHub Spec Kit para Antigravity (agy)
├─ .specify/                        # Motor de Spec Kit (memory/constitution.md, templates, scripts)
├─ specs/                           # Especificaciones por incremento (001-nucleo-comparador/)
├─ AGENTS.md                        # Contexto persistente cargado al abrir el agente
├─ CLAUDE.md                        # Copia sincronizada para la extensión agent-context
├─ PROYECTO.md                      # Resumen ejecutivo del proyecto
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py                    # Factory create_app(), montaje de middlewares, routers y DI
│  │  ├─ config.py                  # Configuracion(BaseSettings) con pydantic-settings
│  │  ├─ bd.py                      # AsyncEngine, async_sessionmaker y dependencia obtener_sesion
│  │  ├─ compartido/
│  │  │  ├─ errores.py              # Excepciones de aplicación y manejador RFC 9457 (problem+json)
│  │  │  ├─ reloj.py                # Protocolo Reloj e implementaciones RelojSistema / RelojFalso
│  │  │  ├─ seguridad.py            # Validación JWT (JWKS/HS256), requiere_usuario, requiere_rol
│  │  │  ├─ limites.py              # LimitadorVentanaDeslizante en memoria por IP y usuario
│  │  │  ├─ texto.py                # Función normalizar_texto(texto) -> minúsculas sin tildes
│  │  │  ├─ huella.py               # Cálculo HMAC-SHA256 con clave rotativa diaria
│  │  │  └─ logging_cfg.py          # Logging JSON estructurado que elimina lat/lng y correos
│  │  ├─ dominio/                   # LÓGICA PURA SIN I/O (mypy --strict, 0 dependencias externas)
│  │  │  ├─ unidades.py             # Conversión de unidades, precio_por_base y parsear_cantidad
│  │  │  ├─ reputacion.py           # Cálculo bayesiano, es_cuenta_nueva y tiene_reputacion_baja
│  │  │  ├─ anomalia.py             # Selección jerárquica de referencia, z-score modificado y %
│  │  │  ├─ riesgo.py               # Puntaje de contexto, ráfagas y evaluar_reporte
│  │  │  ├─ vigencia.py             # Peso temporal exponencial y mediana ponderada
│  │  │  ├─ sello.py                # Árbol de decisión de sello_precio y motivo_sello
│  │  │  └─ orden.py                # Ordenamiento neutral en dos bloques y desempates
│  │  ├─ puertos/
│  │  │  ├─ cache.py                # Protocolo PuertoCache
│  │  │  ├─ almacenamiento.py       # Protocolo PuertoAlmacenamientoFotos
│  │  │  ├─ catalogo_externo.py     # Protocolo PuertoCatalogoExterno
│  │  │  ├─ politica_precio.py      # Protocolo PoliticaPrecioReferencia e impl. SoloUsuarios
│  │  │  └─ proveedor_ia.py         # Protocolo ProveedorIA (Fase 2)
│  │  ├─ adaptadores/
│  │  │  ├─ cache_dos_niveles.py    # L1 TTLCache en memoria + L2 Redis (Upstash/local)
│  │  │  ├─ storage_supabase.py     # URLs firmadas y limpieza de EXIF con Pillow
│  │  │  ├─ open_food_facts.py      # Cliente HTTP con User-Agent, timeout 3s y circuit breaker
│  │  │  └─ ia_gemini.py            # Adaptador Gemini Flash (Fase 2)
│  │  ├─ modulos/
│  │  │  ├─ cuentas/                # api.py, servicio.py, repositorio.py, esquemas.py, modelos.py
│  │  │  ├─ catalogo/               # api.py, servicio.py, repositorio.py, esquemas.py, modelos.py
│  │  │  ├─ establecimientos/       # api.py, servicio.py, repositorio.py, esquemas.py, modelos.py
│  │  │  ├─ precios/                # api.py, servicio.py, repositorio.py, esquemas.py, modelos.py
│  │  │  ├─ confianza/              # servicio.py (orquesta dominio al evaluar reportes y ráfagas)
│  │  │  ├─ moderacion/             # api.py, servicio.py, repositorio.py, esquemas.py, modelos.py
│  │  │  └─ comercial/              # ETAPA 2 (NO existe en el núcleo; se crea en T-61)
│  │  └─ tareas/
│  │     └─ router_jobs.py          # POST /internal/jobs/{nombre} protegido con X-Job-Token
│  ├─ tests/
│  │  ├─ unitarias/                 # Pruebas TDD de dominio/ (sin BD ni red)
│  │  ├─ integracion/               # Pruebas contra PostgreSQL+PostGIS y Redis reales
│  │  ├─ contrato/                  # Pruebas Schemathesis y matriz parametrizada de permisos
│  │  └─ arquitectura/              # Pruebas de fronteras de módulos e inmutabilidad
│  ├─ pyproject.toml
│  └─ Dockerfile
├─ frontend/
│  ├─ src/
│  │  ├─ app/                       # Next.js App Router: rutas S1 a S7 + /offline
│  │  ├─ components/                # Los 15 componentes especificados en la Sección 7.4
│  │  ├─ lib/
│  │  │  ├─ api/                    # Cliente tipado generado desde docs/api/openapi.json
│  │  │  ├─ auth/                   # Cliente Supabase Auth
│  │  │  ├─ offline/                # Cola IndexedDB (cola_reportes) y sincronizador
│  │  │  └─ imagen/                 # Compresión WebP <= 300KB en <canvas> sin EXIF
│  ├─ public/                       # manifest.webmanifest e íconos PWA
│  ├─ tests/e2e/                    # Pruebas Playwright + axe-core
│  ├─ package.json
│  └─ tsconfig.json
├─ supabase/
│  ├─ migrations/                   # Archivos SQL numerados (0001_..., 0002_..., etc.)
│  └─ seed/                         # Archivos CSV de semilla inicial
├─ docs/
│  ├─ PLAN_CONSTRUCCION.md          # Este documento
│  ├─ PREGUNTAS_ABIERTAS.md         # Registro de dudas pendientes
│  ├─ DECLARACION_USO_IA.md         # Declaración académica de asistencia de IA
│  ├─ adr/                          # ADR-001 a ADR-018 en formato MADR
│  ├─ c4/                           # Diagramas Mermaid C1, C2 y C3
│  ├─ api/openapi.json              # Esquema OpenAPI exportado automáticamente
│  └─ calidad/                      # trazabilidad.csv e informes EC-01 a EC-06
├─ infra/
│  ├─ docker-compose.yml            # (Opcional) Referencia de servicios, no requerido en desarrollo local sin Docker
│  └─ k6/ec04_carga.js              # Script de prueba de carga para 500 usuarios
├─ scripts/
│  ├─ dev.cmd                       # Script de automatización local para Windows CMD (entorno uv)
│  ├─ verificar_conexion.py         # Script de verificación de conexión a Supabase y Upstash
│  ├─ migrar.py                     # Ejecutor de migraciones SQL con MIGRATIONS_DATABASE_URL
│  ├─ semilla.py                    # Carga idempotente de CSV
│  ├─ exportar_openapi.py           # Exporta docs/api/openapi.json sin levantar servidor
│  └─ evaluar_ec03.py               # Simulación y matriz de confusión de EC-03
└─ .github/workflows/
   ├─ ci.yml                        # Verificación en cada Pull Request y push
   └─ jobs.yml                      # Tareas programadas (ping_bd, reputación, precio_vigente, huellas)
```

### 3.2 Contenido exacto de `backend/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "comparador-precios-backend"
version = "1.0.0"
description = "Backend API para la plataforma colaborativa de comparacion de precios"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0,<1.0.0",
  "uvicorn[standard]>=0.30.0,<1.0.0",
  "pydantic>=2.9.0,<3.0.0",
  "pydantic-settings>=2.5.0,<3.0.0",
  "sqlalchemy[asyncio]>=2.0.35,<3.0.0",
  "asyncpg>=0.29.0,<1.0.0",
  "redis>=5.1.0,<6.0.0",
  "httpx>=0.27.0,<1.0.0",
  "pyjwt[crypto]>=2.9.0,<3.0.0",
  "pillow>=10.4.0,<12.0.0",
  "cachetools>=5.5.0,<6.0.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.0",
  "pytest-asyncio>=0.24.0",
  "pytest-cov>=5.0.0",
  "hypothesis>=6.112.0",
  "schemathesis>=3.36.0",
  "ruff>=0.6.0",
  "mypy>=1.11.0",
  "import-linter>=2.1",
  "types-cachetools>=5.5.0"
]

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["app"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "S", "UP"]
ignore = ["S101"]

[tool.importlinter]
root_package = "app"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Dominio es puro y no importa infraestructura ni frameworks"
type = "forbidden"
source_modules = ["app.dominio"]
forbidden_modules = [
  "app.modulos",
  "app.adaptadores",
  "app.puertos",
  "app.bd",
  "fastapi",
  "sqlalchemy",
  "redis",
  "httpx"
]

[[tool.importlinter.contracts]]
name = "Precios nunca importa el modulo comercial (EC-06)"
type = "forbidden"
source_modules = ["app.modulos.precios", "app.dominio"]
forbidden_modules = ["app.modulos.comercial"]

[[tool.importlinter.contracts]]
name = "Modulos no importan adaptadores concretos directamente"
type = "forbidden"
source_modules = ["app.modulos"]
forbidden_modules = ["app.adaptadores"]
```

### 3.3 Entorno de Desarrollo Local sin Docker y `.env.example`

> [!NOTE]
> **Entorno local sin Docker Desktop:** El desarrollo local y las pruebas de integración se conectan directamente al proyecto de Supabase (PostgreSQL + PostGIS, Auth y Storage vía MCP y variables en `.env`) y a Redis en Upstash (o mock en memoria para pruebas unitarias y de carga local sin gastar cuota de comandos). No se requiere ni utiliza Docker Desktop ni `docker-compose` en la máquina local.
> 
> El archivo `infra/docker-compose.yml` se conserva únicamente como referencia opcional o de contingencia.

**`infra/docker-compose.yml` (Opcional / Referencia):**
```yaml
services:
  postgres:
    image: postgis/postgis:16-3.4
    container_name: comparador_postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres_local_password
      POSTGRES_DB: comparador
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d comparador"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: comparador_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

**`.env.example`:**
```ini
# =================================================
# Entorno y Servidor Backend (FastAPI)
# =================================================
ENTORNO=local
FASTAPI_HOST=127.0.0.1
FASTAPI_PORT=8000
CORS_ORIGINS=["http://localhost:3000"]

# =================================================
# Supabase (API, Auth y Storage)
# =================================================
# SUPABASE_URL:              https://[PROJECT_REF].supabase.co
# SUPABASE_ANON_KEY:         Publishable key (o clave anon pública)
# SUPABASE_SERVICE_ROLE_KEY: Secret key (o clave service_role, NUNCA exponer al cliente)
# SUPABASE_JWT_SECRET:       Opcional: solo para proyectos legados con HMAC.
#                            En proyectos modernos con JWT Signing Keys (JWKS asimétrico),
#                            dejar vacío; FastAPI valida contra el endpoint JWKS público automáticamente.

SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_ANON_KEY=tu-publishable-key-o-anon-key
SUPABASE_SERVICE_ROLE_KEY=tu-secret-key-o-service-role-key
SUPABASE_JWT_SECRET=
SUPABASE_JWKS_URL=

# =================================================
# Base de datos (PostgreSQL con asyncpg y Pooler)
# =================================================
# En Windows / redes IPv4 se utiliza el Session Pooler (puerto 5432) o Transaction Pooler (puerto 6543).
# Formato: postgresql+asyncpg://[USUARIO].[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:[PUERTO]/postgres
#
# DATABASE_URL:             Conexión cotidiana de la API (en T-02 con rol app_backend; inicialmente con postgres)
# MIGRATIONS_DATABASE_URL:  Conexión exclusiva con rol postgres para DDL (migraciones y semilla en puerto 5432)

DATABASE_URL=postgresql+asyncpg://postgres.tu-ref:tu-password@aws-0-tu-region.pooler.supabase.com:5432/postgres
MIGRATIONS_DATABASE_URL=postgresql+asyncpg://postgres.tu-ref:tu-password@aws-0-tu-region.pooler.supabase.com:5432/postgres

# =================================================
# Caché (Upstash Redis)
# =================================================
# Instancia serverless Upstash con conexión TLS
REDIS_URL=rediss://default:tu-password@tu-endpoint.upstash.io:6379

# =================================================
# Seguridad Operativa y Privacidad (Ley 1581)
# =================================================
HUELLA_SECRETO_MAESTRO=secreto_maestro_hmac_desarrollo_local_32b
JOB_TOKEN=token_interno_jobs_desarrollo_local

# =================================================
# Integraciones Externas y Contacto Legal (PA-01)
# =================================================
CONTACTO_LEGAL_EMAIL=por-confirmar-equipo@cue.edu.co
OFF_USER_AGENT=ComparadorPreciosArmenia/1.0 (por-confirmar-equipo@cue.edu.co)

# =================================================
# IA Generativa (Google Gemini - Fase 2)
# =================================================
# GEMINI_API_KEY: Clave de API de Google AI Studio (https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=tu-gemini-api-key

# =================================================
# Frontend (Next.js - Variables Públicas en Navegador)
# =================================================
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://tu-proyecto.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=tu-publishable-key-o-anon-key
```

### 3.4 Contenido de `backend/Dockerfile` (Exclusivo para Despliegue en la Nube)

> [!NOTE]
> Este `Dockerfile` multi-etapa se reserva exclusivamente para el empaquetado y despliegue del backend en la nube en T-50 (Railway / Render / Fly.io). No se ejecuta ni se requiere Docker en el entorno local del desarrollador.

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml ./
COPY app ./app
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels .
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r <(python -c "import tomllib; p=tomllib.load(open('pyproject.toml','rb')); print('\n'.join(p['project']['dependencies']))")

FROM python:3.12-slim AS runtime
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
WORKDIR /app
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY app ./app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('[http://127.0.0.1:8000/v1/salud](http://127.0.0.1:8000/v1/salud)')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### 3.5 Flujos de Ejecución Paso a Paso (`F1` a `F4`)

#### Flujo `F1` — Consultar la comparación de un producto (`GET /v1/productos/{id}/comparacion`)
1. Validar parámetros de consulta (`presentacion_id` opcional, `orden` en `{'precio_unitario', 'precio', 'distancia'}`, `municipio='Armenia'`, `lat` y `lng` opcionales, `radio_km`, `limite`). Si `orden == 'precio'` y no se envió `presentacion_id`, devolver `422 VALIDACION`.
2. Construir llave de caché por producto y variante sin coordenadas: `subllave = f"{municipio}:{presentacion_id or 'todas'}:{orden}"`.
3. Buscar `(generado_en, payload)` en la caché en memoria L1 (`cache.l1_segundos = 5`). Si existe y `(ahora - generado_en) <= cache.ttl_segundos (60)`, pasar al paso 6.
4. Si no está en L1: ejecutar `HGET cmp:{producto_id} {subllave}` en Redis (1 solo comando). Si existe y `(ahora - generado_en) <= 60 s`, guardar en L1 y pasar al paso 6.
5. Si no está en Redis, venció o Redis lanzó excepción (el fallo de Redis se registra en el contador `cache_fallos` y nunca aborta la petición):
   * Consultar en PostgreSQL las filas de `precio_vigente` para `producto_id` (haciendo `JOIN` con `establecimiento` activo en `municipio` y `presentacion` activa).
   * Invocar `dominio.orden.ordenar_resultados(items, criterio=orden)` que particiona en `Bloque 1` y `Bloque 2`.
   * Construir el objeto con `generado_en = ahora_utc_iso` y guardarlo en L1 y en Redis con `HSET cmp:{producto_id} {subllave}` + `EXPIRE cmp:{producto_id} 120`.
6. Si la petición incluyó `lat` y `lng`: calcular en memoria la distancia Haversine en metros hacia cada establecimiento, filtrar por `radio_km` y, si `orden == 'distancia'`, reordenar cada bloque internamente con `dominio.orden.ordenar_resultados`.
7. Responder `200 OK` con cabecera `Cache-Control: no-cache` y `ETag` calculado sobre el cuerpo.

#### Flujo `F2` — Registrar un reporte de precio (`POST /v1/reportes`)
1. **Autenticación y estado de cuenta:** Validar JWT (`requiere_usuario`), cargar fila de `perfil` desde BD/caché, verificar `estado == 'activa'` (si está `suspendida` o `bloqueada`, responder `403 CUENTA_SUSPENDIDA`) y verificar que exista una fila activa en `autorizacion_datos` (`revocado_en is null`; si no existe, responder `403 AUTORIZACION_REQUERIDA`).
2. **Límites de uso (*Rate Limiting*):** Verificar en `LimitadorVentanaDeslizante` el límite por IP (`limite.escrituras_ip_min = 20`) y el límite por usuario (`limite.reportes_hora_nuevo = 20` si es cuenta nueva o `limite.reportes_hora_normal = 60`, y `limite.reportes_dia = 200`). Si se excede, responder `429 LIMITE_EXCEDIDO` con cabecera `Retry-After`.
3. **Validación de entrada y rango duro:** Verificar cabecera `Idempotency-Key` (UUID válido; si falta, `422 VALIDACION`). Verificar que `precio_cop` sea entero dentro de `[precio.min_cop, precio.max_cop]` (si no, `422 PRECIO_FUERA_DE_RANGO` y no se guarda nada). Verificar que `observado_en` no sea mayor a `ahora + 60 s` ni menor a `ahora - observado.max_antiguedad_horas` (`422 FECHA_INVALIDA`). Verificar que `presentacion_id` y `establecimiento_id` existan y estén activos (`404 NO_ENCONTRADO`).
4. **Verificación de idempotencia:** Consultar en `reporte_precio` si ya existe una fila con `(reportante_id, idempotency_key)`. Si existe, devolver `200 OK` con el cuerpo exacto `{id, estado_visible, mensaje}` original sin volver a insertar.
5. **Carga de contexto para evaluación:**
   * Calcular `huella_red = calcular_huella_red(ip_cliente, secreto_maestro, fecha_utc)`.
   * Consultar los candidatos de referencia aceptados en los últimos `anomalia.ventana_dias` (14 días), excluyendo reportes del mismo `reportante_id` y separando `es_demo`: nivel 1 (`presentacion_tienda`), nivel 2 (`presentacion` en el mismo municipio) y nivel 3 (`producto_unitario` en el mismo municipio).
   * Contar cuántas cuentas distintas han reportado hacia `establecimiento_id` con la misma `huella_red` en los últimos `rafaga.ventana_min` (30 min), incluyendo al reportante actual.
6. **Evaluación determinista en el dominio:** Invocar `dominio.riesgo.evaluar_reporte(...)` que retorna `EvaluacionReporte(estado, senales, puntaje_anomalia, riesgo_contexto, conjunto_referencia)`.
7. **Transacción atómica en PostgreSQL:**
   * Insertar la fila en `reporte_precio` con `estado` y `estado_original` iguales al estado evaluado.
   * Si `estado == 'aceptado'`: recalcular la fila del par `(presentacion_id, establecimiento_id)` en `precio_vigente` usando la política activa (`PoliticaPrecioReferencia`) y verificar si este reporte corrobora reportes previos de otras cuentas para incrementar su contador `reportes_corroborados`.
   * Si `estado == 'dudoso'`: insertar un `caso_moderacion` (`tipo = 'reporte_dudoso'`, `referencia_tabla = 'reporte_precio'`, `referencia_id = reporte.id`). Si además no existe ningún reporte aceptado en 30 días para ese par, actualizar `precio_vigente` con sello `'dudoso'`.
   * Si `'rafaga' in senales`: crear un `caso_moderacion` (`tipo = 'rafaga'`, `prioridad = 1`), actualizar a `estado = 'dudoso'` los reportes de esa misma `(huella_red, establecimiento_id)` dentro de la ventana de 30 minutos y recalcular las filas de `precio_vigente` afectadas.
8. **Post-commit y respuesta:** Si `precio_vigente` cambió, ejecutar `DEL cmp:{producto_id}` en Redis y limpiar la llave en L1. Responder `201 Created` con `estado_visible = 'recibido'` (si fue `aceptado`) o `'en_revision'` (si fue `dudoso`).

#### Flujo `F3` — Garantía de actualidad de `EC-02` (<= 60 segundos)
Toda operación que modifique el precio vigente de un par (nuevo reporte `aceptado`, resolución de moderación con `descartar`/`confirmar` o actualización de `precio_oficial` en Etapa 2) ejecuta en orden: (1) `UPSERT` o `DELETE` inmediato de la fila en `precio_vigente` dentro de la transacción SQL, (2) invalidación síncrona de L1 y `DEL cmp:{producto_id}` en Redis tras el `COMMIT`, y (3) en caso de que el comando `DEL` a Redis falle por red, toda lectura en `F1` verifica el campo `generado_en` del objeto cacheado y lo descarta si `(ahora - generado_en) > 60 s`.

#### Flujo `F4` — Orden exacto de sincronización de la cola offline (`IndexedDB`)
Cuando el reportante guarda un reporte sin señal en `/reportar`:
1. Se almacena localmente en la tabla `cola_reportes` de `IndexedDB` el registro: `{idempotency_key: uuid, presentacion_id, establecimiento_id, precio_cop, observado_en, foto_blob: Blob | null, foto_ruta_remota: string | null, intentos: 0}`.
2. Al recuperar conectividad (evento `online` o apertura de la aplicación), el sincronizador procesa cada elemento en este orden estricto:
   * **Subpaso A (Fotografía):** Si `foto_blob !== null` y `foto_ruta_remota === null`, llama primero a `POST /v1/fotos/url-subida`, sube el blob WebP con `PUT` a la `url_firmada` y guarda `foto_ruta_remota = ruta` en `IndexedDB` antes de continuar (para no volver a subir la foto si falla el paso siguiente).
   * **Subpaso B (Reporte):** Llama a `POST /v1/reportes` enviando `Idempotency-Key: idempotency_key`, `observado_en` original y `foto_ruta: foto_ruta_remota`.
   * **Subpaso C (Limpieza):** Si recibe `201 Created`, `200 OK` o un error `422` no recuperable, elimina el registro de `IndexedDB`. Si recibe error de red, `5xx` o `429`, incrementa `intentos` y reprograma con *exponential backoff*.

---

## 4. Esquema Completo de Base de Datos y Migraciones SQL

### 4.1 Migración `0001_fundaciones_seguridad.sql`
```sql
create extension if not exists postgis;
create extension if not exists pg_trgm;
create extension if not exists unaccent;
create extension if not exists pgcrypto;

-- Rol de aplicación con LOGIN y privilegios mínimos (cumple ADR-012)
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_backend') then
    create role app_backend with login password 'app_backend_local_pass';
  end if;
end
$$;

alter role app_backend bypassrls;
grant usage on schema public to app_backend;
grant app_backend to postgres;
revoke all on all tables in schema public from anon, authenticated;
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public grant select, insert, update, delete on tables to app_backend;
alter default privileges in schema public grant usage, select on sequences to app_backend;

create or replace function actualizar_columna_timestamp()
returns trigger
language plpgsql
as $$
begin
  new.actualizado_en = now();
  return new;
end;
$$;
```

### 4.2 Migración `0002_catalogo_establecimientos_parametros.sql`
```sql
create type rol_usuario as enum ('reportante', 'comercio', 'moderador');
create type estado_cuenta as enum ('activa', 'suspendida', 'bloqueada', 'eliminada');
create type unidad_base as enum ('g', 'ml', 'unidad');
create type unidad_entrada as enum ('g', 'kg', 'lb', 'ml', 'l', 'unidad', 'docena');
create type tipo_establecimiento as enum ('tienda_barrio', 'minimercado', 'supermercado', 'cadena');
create type estado_verificacion as enum ('sin_dueno', 'pendiente', 'verificado');
create type fuente_precio as enum ('usuario', 'comercio', 'semilla');
create type estado_confianza as enum ('aceptado', 'dudoso', 'rechazado');
create type sello_precio as enum ('confiable', 'pocos_datos', 'dudoso', 'desactualizado', 'oficial', 'en_disputa');
create type tipo_caso as enum ('reporte_dudoso', 'rafaga', 'solicitud_correccion', 'sugerencia_presentacion', 'verificacion_comercio', 'disputa_precio');
create type estado_caso as enum ('abierto', 'en_revision', 'resuelto');
create type decision_caso as enum ('confirmar', 'descartar', 'sancionar');
create type tipo_sancion as enum ('advertencia', 'suspension', 'bloqueo');

create table categoria (
  id smallint primary key,
  nombre text not null unique check (char_length(nombre) between 2 and 80),
  padre_id smallint references categoria(id),
  orden smallint not null default 0
);
alter table categoria enable row level security;

create table producto (
  id uuid primary key default gen_random_uuid(),
  nombre text not null unique check (char_length(nombre) between 2 and 120),
  nombre_norm text not null,
  categoria_id smallint not null references categoria(id),
  unidad_base unidad_base not null,
  imagen_url text check (imagen_url is null or char_length(imagen_url) <= 500),
  activo boolean not null default true,
  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);
alter table producto enable row level security;
create trigger trg_producto_actualizado before update on producto
for each row execute function actualizar_columna_timestamp();

create table presentacion (
  id uuid primary key default gen_random_uuid(),
  producto_id uuid not null references producto(id),
  marca text check (marca is null or char_length(marca) between 1 and 80),
  valor_cantidad numeric(12,3) not null check (valor_cantidad > 0),
  unidad unidad_entrada not null,
  multiplicador smallint not null default 1 check (multiplicador >= 1),
  cantidad_base numeric(14,3) not null check (cantidad_base > 0),
  etiqueta text not null check (char_length(etiqueta) between 3 and 180),
  etiqueta_norm text not null,
  codigo_barras text unique check (codigo_barras is null or codigo_barras ~ '^[0-9]{8,14}$'),
  fuente_catalogo text not null default 'manual' check (fuente_catalogo in ('manual', 'semilla', 'open_food_facts')),
  activa boolean not null default true,
  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now(),
  unique nulls not distinct (producto_id, marca, cantidad_base)
);
alter table presentacion enable row level security;
create trigger trg_presentacion_actualizado before update on presentacion
for each row execute function actualizar_columna_timestamp();

create table alias_producto (
  id uuid primary key default gen_random_uuid(),
  producto_id uuid not null references producto(id) on delete cascade,
  alias text not null check (char_length(alias) between 2 and 120),
  alias_norm text not null,
  unique (producto_id, alias_norm)
);
alter table alias_producto enable row level security;

create table establecimiento (
  id uuid primary key default gen_random_uuid(),
  nombre text not null check (char_length(nombre) between 2 and 120),
  tipo tipo_establecimiento not null,
  cadena text check (cadena is null or char_length(cadena) <= 80),
  direccion text not null check (char_length(direccion) between 3 and 200),
  barrio text check (barrio is null or char_length(barrio) <= 80),
  municipio text not null default 'Armenia' check (char_length(municipio) <= 80),
  departamento text not null default 'Quindío' check (char_length(departamento) <= 80),
  ubicacion geography(Point, 4326) not null,
  osm_id bigint,
  comercio_id uuid,
  estado_verificacion estado_verificacion not null default 'sin_dueno',
  activo boolean not null default true,
  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now(),
  unique (nombre, direccion)
);
alter table establecimiento enable row level security;
create trigger trg_establecimiento_actualizado before update on establecimiento
for each row execute function actualizar_columna_timestamp();

create table config_parametro (
  clave text primary key check (char_length(clave) between 3 and 80),
  valor jsonb not null,
  descripcion text not null check (char_length(descripcion) <= 300),
  actualizado_por uuid,
  actualizado_en timestamptz not null default now()
);
alter table config_parametro enable row level security;

create index idx_producto_nombre_trgm on producto using gin (nombre_norm gin_trgm_ops);
create index idx_presentacion_etiqueta_trgm on presentacion using gin (etiqueta_norm gin_trgm_ops);
create index idx_alias_producto_trgm on alias_producto using gin (alias_norm gin_trgm_ops);
create index idx_presentacion_producto on presentacion (producto_id) where activa = true;
create index idx_establecimiento_ubicacion on establecimiento using gist (ubicacion);
create index idx_establecimiento_municipio on establecimiento (municipio, activo);

-- Semilla de las 10 categorías base
insert into categoria (id, nombre, padre_id, orden) values
  (1, 'Granos, arroz y pastas', null, 1),
  (2, 'Lácteos y huevos', null, 2),
  (3, 'Aceites, sal y endulzantes', null, 3),
  (4, 'Café, chocolate y bebidas', null, 4),
  (5, 'Harinas, panadería y arepas', null, 5),
  (6, 'Enlatados y conservas', null, 6),
  (7, 'Carnes, pollo y embutidos', null, 7),
  (8, 'Frutas, verduras y tubérculos', null, 8),
  (9, 'Aseo del hogar', null, 9),
  (10, 'Cuidado personal', null, 10)
on conflict (id) do nothing;

-- Semilla obligatoria de los 43 parámetros de negocio
insert into config_parametro (clave, valor, descripcion) values
  ('precio.min_cop', '50'::jsonb, 'Precio mínimo aceptado en COP'),
  ('precio.max_cop', '2000000'::jsonb, 'Precio máximo aceptado en COP'),
  ('precio.ratio_extremo', '5.0'::jsonb, 'Multiplicador o divisor respecto a la mediana para señal ratio_extremo'),
  ('observado.max_antiguedad_horas', '24'::jsonb, 'Horas máximas hacia atrás permitidas en observado_en'),
  ('vigencia.fresco_horas', '48'::jsonb, 'Horas durante las cuales el reporte conserva factor temporal 1.0'),
  ('vigencia.vida_media_horas', '72'::jsonb, 'Horas para reducir el peso del reporte a la mitad'),
  ('vigencia.vigente_dias', '7'::jsonb, 'Días máximos para considerar vigente un reporte de usuario'),
  ('vigencia.antiguo_dias', '30'::jsonb, 'Días máximos para mostrar un reporte como desactualizado'),
  ('vigencia.comercio_revalidar_dias', '30'::jsonb, 'Días sin cambios para marcar precio oficial como por revalidar'),
  ('anomalia.ventana_dias', '14'::jsonb, 'Días de antigüedad máxima de los reportes del conjunto de referencia'),
  ('anomalia.n_min_referencia', '3'::jsonb, 'Mínimo de reportes aceptados para usar un nivel de referencia'),
  ('anomalia.n_min_z', '5'::jsonb, 'Mínimo de reportes para usar z-score modificado'),
  ('anomalia.z_umbral', '3.5'::jsonb, 'Umbral absoluto del z-score modificado'),
  ('anomalia.desviacion_pct_umbral', '0.30'::jsonb, 'Umbral de desviación porcentual cuando n < 5 o MAD = 0'),
  ('riesgo.pesos', '{"sin_foto":0.15,"cuenta_nueva":0.25,"rafaga":0.40,"reputacion_baja":0.20}'::jsonb, 'Pesos de las 4 señales de contexto'),
  ('riesgo.umbral_dudoso', '0.60'::jsonb, 'Puntaje de riesgo de contexto para marcar reporte como dudoso'),
  ('cuenta_nueva.dias', '7'::jsonb, 'Días desde creación para considerar cuenta nueva'),
  ('cuenta_nueva.min_aceptados', '3'::jsonb, 'Reportes corroborados mínimos para dejar de ser cuenta nueva'),
  ('reputacion.inicial', '0.500'::jsonb, 'Reputación inicial de todo perfil nuevo'),
  ('reputacion.baja_umbral', '0.350'::jsonb, 'Umbral por debajo del cual se activa reputacion_baja'),
  ('reputacion.corroboracion_tolerancia', '0.10'::jsonb, 'Tolerancia porcentual para considerar corroborado un reporte'),
  ('rafaga.ventana_min', '30'::jsonb, 'Ventana en minutos para detectar ráfaga por huella de red'),
  ('rafaga.min_cuentas', '3'::jsonb, 'Cuentas distintas mínimas con igual huella hacia la misma tienda'),
  ('sello.n_min_validos', '3'::jsonb, 'Mínimo de reportes vigentes para otorgar sello confiable'),
  ('sello.min_fuentes', '2'::jsonb, 'Mínimo de fuentes distintas para otorgar sello confiable'),
  ('sello.dispersion_max', '0.15'::jsonb, 'Dispersión máxima MAD/mediana permitida para sello confiable'),
  ('peso.con_foto', '1.2'::jsonb, 'Multiplicador del peso cuando el reporte incluye foto de prueba'),
  ('cache.ttl_segundos', '60'::jsonb, 'Tiempo máximo de vida en caché de comparación (EC-02)'),
  ('cache.l1_segundos', '5'::jsonb, 'Tiempo de vida en caché L1 de memoria'),
  ('limite.reportes_hora_nuevo', '20'::jsonb, 'Máximo de reportes por hora para cuenta nueva'),
  ('limite.reportes_hora_normal', '60'::jsonb, 'Máximo de reportes por hora para cuenta establecida'),
  ('limite.reportes_dia', '200'::jsonb, 'Máximo de reportes por día por usuario'),
  ('limite.consultas_ip_min', '120'::jsonb, 'Máximo de lecturas públicas por minuto por IP'),
  ('limite.escrituras_ip_min', '20'::jsonb, 'Máximo de escrituras por minuto por IP'),
  ('limite.correcciones_ip_dia', '3'::jsonb, 'Máximo de solicitudes de corrección de tienda por día por IP'),
  ('limite.fotos_hora_usuario', '30'::jsonb, 'Máximo de URLs firmadas de subida de foto por hora por usuario'),
  ('foto.max_kb', '300'::jsonb, 'Tamaño máximo de archivo de foto de prueba en KB'),
  ('foto.tipos', '["image/webp","image/jpeg"]'::jsonb, 'Tipos MIME aceptados para fotografías de prueba'),
  ('huella.retencion_dias', '30'::jsonb, 'Días de retención de huella_red antes de su anulación'),
  ('comparacion.radio_km', '10.0'::jsonb, 'Radio espacial por defecto en km para filtrar por cercanía'),
  ('comparacion.max_resultados', '50'::jsonb, 'Cantidad máxima de establecimientos devueltos en comparación'),
  ('disputa.min_reportes_y_cuentas', '{"min_reportes":3,"min_cuentas":2}'::jsonb, 'Mínimo de reportes y cuentas para declarar disputa con precio oficial'),
  ('disputa.ventana_y_diferencia', '{"ventana_horas":48,"diferencia_pct":0.10}'::jsonb, 'Ventana de horas y diferencia porcentual para declarar disputa')
on conflict (clave) do nothing;
```

### 4.3 Migración `0003_cuentas_precios_moderacion_auditoria.sql`
*(Nota: `reporte_precio.precio_cop` valida `precio_cop > 0` en SQL para que el rango configurable `precio.min_cop` y `precio.max_cop` en `config_parametro` pueda modificarse sin chocar con un `CHECK` fijo).*

```sql
create table perfil (
  id uuid primary key,
  alias text not null unique check (char_length(alias) between 3 and 30 and alias ~ '^[a-zA-Z0-9_.-]+$'),
  rol rol_usuario not null default 'reportante',
  estado estado_cuenta not null default 'activa',
  suspendida_hasta timestamptz,
  reputacion numeric(4,3) not null default 0.500 check (reputacion between 0 and 1),
  reportes_corroborados int not null default 0 check (reportes_corroborados >= 0),
  reportes_malos_confirmados int not null default 0 check (reportes_malos_confirmados >= 0),
  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);
alter table perfil enable row level security;
create trigger trg_perfil_actualizado before update on perfil
for each row execute function actualizar_columna_timestamp();

alter table establecimiento
  add constraint fk_establecimiento_comercio foreign key (comercio_id) references perfil(id) on delete set null;

create table autorizacion_datos (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references perfil(id) on delete cascade,
  version_politica text not null check (char_length(version_politica) <= 20),
  finalidad text not null check (char_length(finalidad) between 20 and 2000),
  aceptada_en timestamptz not null default now(),
  revocada_en timestamptz
);
alter table autorizacion_datos enable row level security;

create table sancion (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references perfil(id),
  tipo tipo_sancion not null,
  motivo text not null check (char_length(motivo) between 5 and 500),
  desde timestamptz not null default now(),
  hasta timestamptz,
  moderador_id uuid not null references perfil(id),
  apelacion text check (apelacion is null or char_length(apelacion) <= 1000),
  apelacion_resuelta boolean
);
alter table sancion enable row level security;

create table sugerencia_presentacion (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid references perfil(id) on delete set null,
  producto_id uuid references producto(id),
  texto_libre text not null check (char_length(texto_libre) between 3 and 200),
  marca text check (marca is null or char_length(marca) <= 80),
  valor_cantidad numeric(12,3) check (valor_cantidad is null or valor_cantidad > 0),
  unidad unidad_entrada,
  codigo_barras text check (codigo_barras is null or codigo_barras ~ '^[0-9]{8,14}$'),
  estado text not null default 'pendiente' check (estado in ('pendiente', 'aprobada', 'rechazada')),
  creado_en timestamptz not null default now()
);
alter table sugerencia_presentacion enable row level security;

create table reporte_precio (
  id uuid primary key default gen_random_uuid(),
  presentacion_id uuid not null references presentacion(id),
  establecimiento_id uuid not null references establecimiento(id),
  producto_id uuid not null references producto(id),
  precio_cop integer not null check (precio_cop > 0),
  incluye_impuestos boolean not null default true check (incluye_impuestos = true),
  cantidad_base_snapshot numeric(14,3) not null check (cantidad_base_snapshot > 0),
  precio_por_base numeric(14,6) not null check (precio_por_base > 0),
  fuente fuente_precio not null,
  reportante_id uuid references perfil(id) on delete set null,
  observado_en timestamptz not null,
  foto_prueba_path text check (foto_prueba_path is null or char_length(foto_prueba_path) <= 300),
  estado estado_confianza not null,
  estado_original estado_confianza not null,
  senales text[] not null default '{}',
  puntaje_anomalia numeric(8,3),
  riesgo_contexto numeric(4,3) not null default 0 check (riesgo_contexto between 0 and 1),
  conjunto_referencia text not null check (conjunto_referencia in ('presentacion_tienda', 'presentacion', 'producto_unitario', 'sin_referencia')),
  huella_red text check (huella_red is null or char_length(huella_red) = 64),
  idempotency_key uuid,
  es_demo boolean not null default false,
  revisado_por uuid references perfil(id),
  revisado_en timestamptz,
  creado_en timestamptz not null default now(),
  unique (reportante_id, idempotency_key)
);
alter table reporte_precio enable row level security;

create or replace function bloquear_cambios_reporte()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'PROHIBIDO_BORRAR_REPORTE: La tabla reporte_precio es inmutable.';
  end if;

  if new.id <> old.id
     or new.presentacion_id <> old.presentacion_id
     or new.establecimiento_id <> old.establecimiento_id
     or new.producto_id <> old.producto_id
     or new.precio_cop <> old.precio_cop
     or new.cantidad_base_snapshot <> old.cantidad_base_snapshot
     or new.precio_por_base <> old.precio_por_base
     or new.fuente <> old.fuente
     or new.observado_en <> old.observado_en
     or new.estado_original <> old.estado_original
     or new.es_demo <> old.es_demo
     or new.creado_en <> old.creado_en then
    raise exception 'PROHIBIDO_MODIFICAR_REPORTE: Los campos de evidencia del reporte son inmutables.';
  end if;

  if old.reportante_id is not null and new.reportante_id is not null and new.reportante_id <> old.reportante_id then
    raise exception 'PROHIBIDO_CAMBIAR_AUTOR: Solo se permite anonimizar reportante_id a NULL.';
  end if;

  return new;
end;
$$;

create trigger trg_inmutabilidad_reporte
before update or delete on reporte_precio
for each row execute function bloquear_cambios_reporte();

create table precio_vigente (
  presentacion_id uuid not null references presentacion(id),
  establecimiento_id uuid not null references establecimiento(id),
  producto_id uuid not null references producto(id),
  precio_cop integer not null check (precio_cop > 0),
  precio_por_base numeric(14,6) not null check (precio_por_base > 0),
  cantidad_base numeric(14,3) not null check (cantidad_base > 0),
  sello sello_precio not null,
  motivo_sello text check (motivo_sello is null or char_length(motivo_sello) <= 200),
  n_reportes_validos smallint not null check (n_reportes_validos >= 0),
  n_fuentes smallint not null check (n_fuentes >= 0),
  dispersion numeric(6,4),
  ultimo_reporte_en timestamptz not null,
  reporte_origen_id uuid references reporte_precio(id),
  recalculado_en timestamptz not null default now(),
  primary key (presentacion_id, establecimiento_id)
);
alter table precio_vigente enable row level security;

create table caso_moderacion (
  id uuid primary key default gen_random_uuid(),
  tipo tipo_caso not null,
  referencia_tabla text not null check (char_length(referencia_tabla) <= 60),
  referencia_id uuid,
  detalle jsonb not null default '{}',
  prioridad smallint not null default 3 check (prioridad between 1 and 5),
  estado estado_caso not null default 'abierto',
  decision decision_caso,
  moderador_id uuid references perfil(id),
  nota text check (nota is null or char_length(nota) <= 1000),
  creado_en timestamptz not null default now(),
  resuelto_en timestamptz
);
alter table caso_moderacion enable row level security;

create table auditoria (
  id bigserial primary key,
  actor_id uuid,
  rol text,
  accion text not null check (char_length(accion) <= 100),
  entidad text not null check (char_length(entidad) <= 60),
  entidad_id text,
  antes jsonb,
  despues jsonb,
  creado_en timestamptz not null default now()
);
alter table auditoria enable row level security;

revoke update, delete on auditoria from app_backend;
revoke delete on reporte_precio from app_backend;

create index idx_reporte_par_observado on reporte_precio (presentacion_id, establecimiento_id, observado_en desc) where estado = 'aceptado';
create index idx_reporte_rafaga on reporte_precio (establecimiento_id, huella_red, creado_en desc) where huella_red is not null;
create index idx_reporte_autor on reporte_precio (reportante_id, creado_en desc);
create index idx_reporte_producto_fecha on reporte_precio (producto_id, observado_en desc);
create index idx_precio_vigente_producto on precio_vigente (producto_id, sello, precio_por_base);
create index idx_caso_moderacion_cola on caso_moderacion (estado, prioridad asc, creado_en asc);
```

### 4.4 Migración `0004_modulo_comercial.sql` *(Exclusiva de Etapa 2 — Tarea `T-61`)*
```sql
create type tipo_promocion as enum ('porcentaje', 'precio_especial', 'pague_x_lleve_y');

create table solicitud_verificacion_comercio (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references perfil(id) on delete cascade,
  establecimiento_id uuid not null references establecimiento(id),
  telefono_contacto text not null check (char_length(telefono_contacto) between 7 and 30),
  mensaje text not null check (char_length(mensaje) between 5 and 500),
  estado estado_verificacion not null default 'pendiente',
  verificado_por uuid references perfil(id),
  verificado_en timestamptz,
  creado_en timestamptz not null default now()
);
alter table solicitud_verificacion_comercio enable row level security;

create table precio_oficial (
  presentacion_id uuid not null references presentacion(id),
  establecimiento_id uuid not null references establecimiento(id),
  producto_id uuid not null references producto(id),
  comercio_id uuid not null references perfil(id),
  precio_cop integer not null check (precio_cop > 0),
  precio_por_base numeric(14,6) not null check (precio_por_base > 0),
  actualizado_en timestamptz not null default now(),
  revalidado_en timestamptz not null default now(),
  activo boolean not null default true,
  primary key (presentacion_id, establecimiento_id)
);
alter table precio_oficial enable row level security;

create table promocion (
  id uuid primary key default gen_random_uuid(),
  establecimiento_id uuid not null references establecimiento(id),
  producto_id uuid not null references producto(id),
  presentacion_id uuid references presentacion(id),
  comercio_id uuid not null references perfil(id),
  titulo text not null check (char_length(titulo) between 5 and 120),
  tipo tipo_promocion not null,
  porcentaje_descuento smallint check (porcentaje_descuento is null or porcentaje_descuento between 1 and 90),
  precio_especial_cop integer check (precio_especial_cop is null or precio_especial_cop > 0),
  pague_x smallint check (pague_x is null or pague_x >= 1),
  lleve_y smallint check (lleve_y is null or lleve_y >= 2),
  condiciones text not null check (char_length(condiciones) between 10 and 500),
  vigente_desde timestamptz not null,
  vigente_hasta timestamptz,
  hasta_revocar boolean not null default false,
  revocada_en timestamptz,
  activa boolean not null default true,
  creado_en timestamptz not null default now(),
  check ((vigente_hasta is not null and hasta_revocar = false) or (vigente_hasta is null and hasta_revocar = true)),
  check (pague_x is null or lleve_y > pague_x)
);
alter table promocion enable row level security;

alter table precio_vigente
  add column if not exists precio_oficial_cop integer,
  add column if not exists diferencia_pct numeric(6,4),
  add column if not exists requiere_revalidacion boolean not null default false;
```

### 4.5 Migración `0005_supervisor_ia.sql` *(Exclusiva de Fase 2 — Tarea `T-73`)*
```sql
create table informe_supervisor (
  id uuid primary key default gen_random_uuid(),
  fecha_corte date not null unique,
  n_casos_analizados int not null default 0,
  resumen_markdown text not null,
  proveedor_ia text not null,
  creado_en timestamptz not null default now()
);
alter table informe_supervisor enable row level security;
```

---

## 5. Algoritmos del Dominio Puro y Tablas de Pruebas TDD (`backend/app/dominio/`)

### 5.1 Módulo `unidades.py`
* **Factores de conversión hacia `unidad_base`:**
  * `('g', 'g') -> Decimal('1')`
  * `('kg', 'g') -> Decimal('1000')`
  * `('lb', 'g') -> Decimal('500')` *(supuesto documentado: convención comercial colombiana donde 1 libra métrica equivale exactamente a 500 g)*
  * `('ml', 'ml') -> Decimal('1')`
  * `('l', 'ml') -> Decimal('1000')`
  * `('unidad', 'unidad') -> Decimal('1')`
  * `('docena', 'unidad') -> Decimal('12')`
  * Cualquier otra tupla `(unidad_entrada, unidad_base)` lanza `ErrorUnidadesIncompatibles`.
* **Fórmulas exactas:**
  * `cantidad_base = (valor_cantidad * factor * Decimal(multiplicador)).quantize(Decimal('0.001'))`
  * `precio_por_base = (Decimal(precio_cop) / cantidad_base).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)`
  * `calcular_precio_visualizacion(precio_por_base, unidad_base)`:
    * Si `unidad_base == 'g'`: retorna `(int((precio_por_base * Decimal('1000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)), 'kg')`
    * Si `unidad_base == 'ml'`: retorna `(int((precio_por_base * Decimal('1000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)), 'l')`
    * Si `unidad_base == 'unidad'`: retorna `(int(precio_por_base.quantize(Decimal('1'), rounding=ROUND_HALF_UP)), 'unidad')`

**Casos obligatorios de prueba TDD para `test_unidades.py`:**
| Entrada | Resultado esperado |
| :--- | :--- |
| `parsear_cantidad("500 g")`, `"500g"`, `"500 gr"` | `valor=500, unidad='g', multiplicador=1, cantidad_base=500.000` |
| `parsear_cantidad("1/2 kg")`, `"½ kg"`, `"medio kilo"` | `valor=0.5, unidad='kg', multiplicador=1, cantidad_base=500.000` |
| `parsear_cantidad("1 libra")`, `"1 lb"` | `valor=1, unidad='lb', multiplicador=1, cantidad_base=500.000` |
| `parsear_cantidad("1,5 L")`, `"1.5 l"` | `valor=1.5, unidad='l', multiplicador=1, cantidad_base=1500.000` |
| `parsear_cantidad("6 x 330 ml")`, `"x6 330ml"` | `valor=330, unidad='ml', multiplicador=6, cantidad_base=1980.000` |
| `parsear_cantidad("docena")` | `valor=1, unidad='docena', multiplicador=1, cantidad_base=12.000` |
| `parsear_cantidad("500")` (sin unidad) | `None` (nunca adivina unidad) |
| Comparación guía: `1 kg` a `$5.000` vs. `500 g` a `$2.800` | `$5.000/kg` (`precio_por_base = 5.000000`) < `$5.600/kg` (`precio_por_base = 5.600000`) |
| `unidad_entrada='ml'` en producto con `unidad_base='g'` | Lanza `ErrorUnidadesIncompatibles` |
| Propiedad `hypothesis` | Escalar `precio_cop` y `cantidad_base` por cualquier entero $k \ge 1$ deja `precio_por_base` invariante |

### 5.2 Módulo `reputacion.py`
* **Fórmula bayesiana:**
  $$\text{reputacion} = \text{Decimal}\left(\frac{A + 2}{A + 3M + 4}\right).\text{quantize}(\text{Decimal}('0.001'), \text{rounding}=\text{ROUND\_HALF\_UP})$$
* **Casos obligatorios de prueba TDD (`test_riesgo_reputacion.py`):**
  * $(A=0, M=0) \rightarrow 0.500$
  * $(A=10, M=0) \rightarrow 0.857$
  * $(A=10, M=2) \rightarrow 0.600$
  * $(A=0, M=1) \rightarrow 0.286$
  * `es_cuenta_nueva`: `True` si `(ahora - creado_en) < 7 días` **o** `A < 3`; `False` cuando tiene $\ge 7$ días **y** $A \ge 3$.

### 5.3 Módulos `anomalia.py` y `riesgo.py` (`EC-03`)
* **Conjunto de referencia jerárquico (3 niveles + respaldo `sin_referencia`):**
  Se evalúa en orden:
  1. `presentacion_tienda`: reportes aceptados de la misma presentación y mismo establecimiento en los últimos `anomalia.ventana_dias` (variable comparada: `precio_cop`).
  2. `presentacion`: reportes aceptados de la misma presentación en otras tiendas del mismo municipio (variable comparada: `precio_cop`).
  3. `producto_unitario`: reportes aceptados del mismo producto en el municipio (variable comparada: `precio_por_base`).
  * Se selecciona el primer nivel que tenga longitud $n \ge \text{params.anomalia\_n\_min\_referencia}$ (3).
  * **Comportamiento exacto con `sin_referencia`:** Si ninguno de los 3 niveles alcanza $n \ge 3$, la función retorna `conjunto_referencia = 'sin_referencia'`, `es_anomalo = False`, `puntaje_anomalia = None` y no activa `ratio_extremo`. El reporte solo pasará a `dudoso` si su `riesgo_contexto >= params.riesgo_umbral_dudoso` (0.60); de lo contrario es `aceptado` y `sello.py` le asignará el sello `'pocos_datos'` hasta reunir suficientes reportes.
* **Cálculo de anomalía cuando hay referencia ($n \ge 3$):**
  * Sea $m = \text{mediana}(\text{valores\_ref})$ y $\text{MAD} = \text{mediana}(\{|v - m| \text{ para } v \in \text{valores\_ref}\})$.
  * `ratio_extremo = (x > m * params.precio_ratio_extremo) or (x < m / params.precio_ratio_extremo)`.
  * Si $n \ge \text{params.anomalia\_n\_min\_z}$ (5) y $\text{MAD} > 0$:
    $$M = \frac{0.6745 \cdot (x - m)}{\text{MAD}}$$
    `es_anomalo = (abs(M) > params.anomalia_z_umbral) or ratio_extremo`, `puntaje_anomalia = round(abs(M), 3)`.
  * Si $n \in \{3, 4\}$ o $\text{MAD} == 0$:
    $$d = \frac{|x - m|}{m}$$
    `es_anomalo = (d > params.anomalia_desviacion_pct_umbral) or ratio_extremo`, `puntaje_anomalia = round(d, 3)`.
* **Puntaje de riesgo de contexto (`riesgo_contexto`):**
  $$\text{riesgo\_contexto} = \sum_{s \in \{\text{sin\_foto}, \text{cuenta\_nueva}, \text{rafaga}, \text{reputacion\_baja}\}} \text{params.riesgo\_pesos}[s] \cdot \mathbb{I}(s)$$
  * Decisión: `estado = 'dudoso'` si `es_anomalo` es `True` **o** `riesgo_contexto >= params.riesgo_umbral_dudoso` (0.60); en otro caso `estado = 'aceptado'`.

**Casos obligatorios de prueba TDD para `test_anomalia.py` y `test_riesgo_reputacion.py` (Sección 5.3):**
| Caso de prueba | Entrada | Resultado esperado |
| :--- | :--- | :--- |
| **1. Z-score claro** | 10 reportes en `presentacion_tienda` entre `$2.600` y `$2.700`; nuevo reporte de `$900` | `conjunto_referencia = 'presentacion_tienda'`, `es_anomalo = True`, `estado = 'dudoso'` |
| **2. Método porcentual (`n = 4`)** | 4 reportes con mediana `$2.600`; nuevo de `$3.510` (+35 %) vs. nuevo de `$3.120` (+20 %) | `$3.510` -> `dudoso` (`d = 0.35 > 0.30`); `$3.120` -> `aceptado` (`d = 0.20 <= 0.30`) |
| **3. Todos iguales (`MAD = 0`)** | 6 reportes idénticos de `$2.600` (`MAD = 0`); nuevo de `$2.700` (+3.8 %) vs. `$3.600` (+38.5 %) | Usa respaldo porcentual sin dividir por cero: `$2.700` -> `aceptado`; `$3.600` -> `dudoso` |
| **4. Sin referencia (`n < 3`)** | Nivel 1 tiene 2 reportes, Nivel 2 tiene 1, Nivel 3 tiene 2; usuario normal con foto | `conjunto_referencia = 'sin_referencia'`, `puntaje_anomalia = None`, `estado = 'aceptado'` |
| **5. Aislamiento tienda vs. cadena** | Tienda de barrio con 5 reportes propios en `$2.500` y supermercados en `$3.200`; nuevo en tienda a `$2.550` | Usa Nivel 1 (`presentacion_tienda` de la tienda de barrio) y da `aceptado` (evita falsa alarma) |
| **6. Error de digitación (`ratio_extremo`)** | Mediana `$2.600`, usuario reporta `$26.000` (10x) | `'ratio_extremo' in senales`, `es_anomalo = True`, `estado = 'dudoso'` |
| **7. Usuario nuevo honesto sin foto** | Precio normal `$2.600`, `sin_foto` (0.15) + `cuenta_nueva` (0.25) = `0.40 < 0.60` | `estado = 'aceptado'` (no castiga a nuevos aportantes honestos) |
| **8. Ataque en ráfaga de cuentas nuevas** | Precio dentro de rango pero `cuenta_nueva` (0.25) + `rafaga` (0.40) = `0.65 >= 0.60` | `estado = 'dudoso'` y dispara reevaluación hacia atrás de la ventana |
| **9. Determinismo estricto** | 1.000 ejecuciones seguidas con la misma entrada | Exactamente el mismo objeto `EvaluacionReporte` |

### 5.4 Módulos `vigencia.py` y `sello.py`
* **Fórmula exacta del peso de cada reporte ($w_i$):**
  Para cada candidato aceptado con edad $\le \text{params.vigencia\_antiguo\_dias}$:
  $$\text{edad\_horas} = \max\left(0.0, \frac{(\text{ahora} - \text{reporte.observado\_en}).\text{total\_seconds}()}{3600.0}\right)$$
  $$\text{exponente} = \frac{\max(0.0, \text{edad\_horas} - \text{params.vigencia\_fresco\_horas})}{\text{params.vigencia\_vida\_media\_horas}}$$
  $$\text{factor\_foto} = \text{params.peso\_con\_foto si reporte.tiene\_foto sino } 1.0$$
  $$\text{rep\_autor} = \text{reporte.reputacion\_autor si reporte.fuente == 'usuario' sino params.reputacion\_inicial}$$
  $$w_i = \text{rep\_autor} \times \left(0.5^{\text{exponente}}\right) \times \text{factor\_foto}$$
* **Cálculo de `precio_vigente` y árbol de decisión de `sello_precio` (leyendo siempre `params`):**
  1. Filtrar `vigentes` = reportes `aceptado` con `edad <= timedelta(days=params.vigencia_vigente_dias)`.
  2. Filtrar `antiguos` = reportes `aceptado` con `timedelta(days=params.vigencia_vigente_dias) < edad <= timedelta(days=params.vigencia_antiguo_dias)`.
  3. Filtrar `dudosos_recientes` = reportes `dudoso` con `edad <= timedelta(days=params.vigencia_vigente_dias)`.
  4. **Regla 1 (`dudoso` por ausencia de aceptados):** Si `vigentes` y `antiguos` están vacíos, pero `dudosos_recientes` no está vacío: calcular mediana simple de `dudosos_recientes`, asignar `sello = 'dudoso'` y `motivo_sello = 'En revisión: reportes sin confirmar'`. (Si también está vacío, retornar `None` para que no exista fila en `precio_vigente`).
  5. **Regla 2 (`desactualizado`):** Si `vigentes` está vacío y `antiguos` no está vacío: elegir el reporte de `antiguos` con mayor `observado_en`, asignar `sello = 'desactualizado'` y `motivo_sello = f'Sin actualizar hace {dias_antiguedad} días'`.
  6. Si `vigentes` no está vacío: calcular el precio mediante **mediana ponderada** (ordenar `vigentes` por `precio_cop` ascendente y `observado_en` descendente, acumular $w_i$ y elegir el primer elemento cuyo peso acumulado sea $\ge (\sum w_i) / 2$). Calcular `n_reportes_validos = len(vigentes)`, `n_fuentes = cuentas_distintas + (1 si hay fuente=='semilla' sino 0)` y `dispersion = MAD(vigentes) / mediana(vigentes)` (`0` si `len(vigentes) < 2`).
  7. **Regla 3 (`pocos_datos`):** Si `n_reportes_validos < params.sello_n_min_validos` **o** `n_fuentes < params.sello_min_fuentes`: asignar `sello = 'pocos_datos'` y `motivo_sello = 'Pocos datos: ayúdanos a confirmarlo'`.
  8. **Regla 4 (`dudoso` por contradicción):** Si `dispersion > params.sello_dispersion_max`: asignar `sello = 'dudoso'` y `motivo_sello = 'Reportes contradictorios'`.
  9. **Regla 5 (`confiable`):** En cualquier otro caso: asignar `sello = 'confiable'` y `motivo_sello = None`.

**Casos obligatorios de prueba TDD para `test_vigencia_sello_orden.py` (con `RelojFalso`):**
* Con igual reputación y foto, el peso $w_i$ de un reporte de `120 h` (`48 + 72`) es exactamente la mitad (`0.5 * w`) del de un reporte de `48 h`.
* Un único reporte aceptado de hace `8 días` produce `sello = 'desactualizado'`.
* Un único reporte aceptado de hace `31 días` retorna `None` (sale de `precio_vigente`).
* 3 reportes vigentes de 3 cuentas distintas dentro de $\pm 5\%$ producen `sello = 'confiable'`.
* 2 reportes vigentes de 2 cuentas producen `sello = 'pocos_datos'`.
* 3 reportes vigentes de 1 sola cuenta (`n_fuentes = 1 < 2`) producen `sello = 'pocos_datos'`.

### 5.5 Módulo `orden.py` (`D-13`, `EC-06`)
* Separa los ítems en `bloque_1` (`sello in ('confiable', 'pocos_datos', 'oficial', 'en_disputa')`, marcando `es_bloque_secundario = False`) y `bloque_2` (`sello in ('dudoso', 'desactualizado')`, marcando `es_bloque_secundario = True`).
* Ordena cada bloque internamente según `criterio`:
  * `'precio_unitario'`: `(item.precio_por_base, -item.ultimo_reporte_en.timestamp(), normalizar_texto(item.establecimiento_nombre), str(item.establecimiento_id))`
  * `'precio'`: `(item.precio_cop, -item.ultimo_reporte_en.timestamp(), normalizar_texto(item.establecimiento_nombre), str(item.establecimiento_id))`
  * `'distancia'`: `(item.distancia_m if item.distancia_m is not None else 999999999, item.precio_por_base, -item.ultimo_reporte_en.timestamp(), str(item.establecimiento_id))`
* Retorna `bloque_1 + bloque_2`.

---

## 6. Contratos de la API REST (`/v1`), Catálogo de Errores y Matriz de Permisos

### 6.1 Convenciones de la API
* Prefijo base `/v1`; JSON UTF-8; identificadores `snake_case`; fechas ISO 8601 en UTC; precios enteros en COP; IDs `uuid`.
* Los endpoints internos `/internal/jobs/{nombre}` llevan `include_in_schema=False` y exigen cabecera `X-Job-Token`.

### 6.2 Catálogo Completo de Códigos de Error (`application/problem+json` — RFC 9457)
| Código (`codigo`) | Estado HTTP | Cuándo se devuelve |
| :--- | :---: | :--- |
| `VALIDACION` | `422` | Esquema inválido, campo extra no permitido (`extra='forbid'`), falta `Idempotency-Key` o se pide `orden=precio` sin `presentacion_id`. |
| `PRECIO_FUERA_DE_RANGO` | `422` | `precio_cop` es menor que `precio.min_cop` o mayor que `precio.max_cop`. |
| `FECHA_INVALIDA` | `422` | `observado_en` está en el futuro (> 60 s) o tiene más de `observado.max_antiguedad_horas` (24 h). |
| `UNIDADES_INCOMPATIBLES` | `422` | La `unidad` de la presentación no es convertible a la `unidad_base` del producto. |
| `ARCHIVO_INVALIDO` | `422` | La fotografía supera `foto.max_kb` (300 KB) o su tipo MIME no está en `foto.tipos`. |
| `NO_AUTENTICADO` | `401` | Falta cabecera `Authorization: Bearer`, token malformado, firma inválida o token expirado. |
| `PROHIBIDO` | `403` | El rol en `perfil.rol` no tiene permiso para el endpoint o el comercio intenta operar un establecimiento ajeno. |
| `AUTORIZACION_REQUERIDA` | `403` | El usuario autenticado aún no ha registrado su aceptación de datos en `POST /v1/mi-cuenta/autorizacion`. |
| `CUENTA_SUSPENDIDA` | `403` | `perfil.estado` es `'suspendida'` o `'bloqueada'`. |
| `NO_ENCONTRADO` | `404` | El recurso (`producto`, `presentacion`, `establecimiento`, `caso`) no existe o está inactivo. |
| `CONFLICTO` | `409` | Duplicado en restricción única (`alias` ya usado, `codigo_barras` repetido o presentación duplicada). |
| `LIMITE_EXCEDIDO` | `429` | Se superó el límite de peticiones por usuario o por IP; incluye cabecera obligatoria `Retry-After`. |
| `SERVICIO_NO_DISPONIBLE` | `503` | La base de datos PostgreSQL no responde en `/v1/salud/listo`. |

### 6.3 Inventario Completo de Endpoints

| Grupo | Método y Ruta | Resumen funcional |
| :--- | :--- | :--- |
| **Públicos** | `GET /v1/salud` | Liveness check (`200 OK {"estado": "ok"}`). |
| **Públicos** | `GET /v1/salud/listo` | Readiness check: verifica PostgreSQL (`200 OK` o `503`); informa estado de Redis (`ok` o `degradado`). |
| **Públicos** | `GET /v1/categorias` | Árbol de categorías ordenado. |
| **Públicos** | `GET /v1/productos` | Buscador y listado paginado (`q`, `categoria_id`, `limite`, `cursor`). |
| **Públicos** | `GET /v1/productos/{id}` | Ficha del producto y sus presentaciones activas. |
| **Públicos** | `GET /v1/productos/{id}/comparacion` | Comparador de precios en dos bloques + arreglo `promociones` + `meta` (Flujo `F1`). |
| **Públicos** | `GET /v1/establecimientos` | Directorio filtrable por `q`, `tipo`, `municipio`, `lat`, `lng`, `radio_km`. |
| **Públicos** | `GET /v1/establecimientos/{id}` | Ficha de tienda, sus precios vigentes paginados y sus promociones activas. |
| **Públicos** | `POST /v1/establecimientos/{id}/solicitudes-correccion` | Envía `{correo, mensaje, sitio_web_trampa?}` para abrir caso `solicitud_correccion`. |
| **Públicos** | `GET /v1/legal/politica-tratamiento` | Versión vigente, texto de política Ley 1581 y correo de contacto. |
| **Reportante** | `POST /v1/mi-cuenta/autorizacion` | Crea `perfil` y `autorizacion_datos` con `{alias, version_politica, acepta: true}`. |
| **Reportante** | `GET /v1/mi-cuenta` | Devuelve perfil, reputación, contadores y fecha de autorización (Ley 1581 art. 8). |
| **Reportante** | `PATCH /v1/mi-cuenta` | Actualiza el `alias` público. |
| **Reportante** | `DELETE /v1/mi-cuenta` | Suprime la cuenta y anonimiza todos sus reportes y fotos (`FR-007`). |
| **Reportante** | `POST /v1/fotos/url-subida` | Genera `{ruta, url_firmada, expira_en}` (5 min) en bucket privado `pruebas`. |
| **Reportante** | `POST /v1/reportes` | Registra un reporte de precio con `Idempotency-Key` obligatoria (Flujo `F2`). |
| **Reportante** | `GET /v1/mis-reportes` | Historial propio paginado mostrando solo `estado_visible` (`recibido`, `en_revision`, `rechazado`). |
| **Reportante** | `POST /v1/sugerencias-presentacion` | Envía sugerencia de nueva presentación y abre caso de moderación. |
| **Moderador** | `GET /v1/moderacion/casos` | Cola de casos filtrable por `estado`, `tipo`, `prioridad`. |
| **Moderador** | `GET /v1/moderacion/casos/{id}` | Detalle del caso, señales activadas, contexto y URL firmada de foto por 10 min. |
| **Moderador** | `POST /v1/moderacion/casos/{id}/resolver` | Resuelve caso con `{decision: 'confirmar'\|'descartar'\|'sancionar', nota, sancion?}`. |
| **Moderador** | `GET /v1/moderacion/usuarios/{id}` | Historial de reportes, reputación y sanciones de un usuario. |
| **Moderador** | `POST /v1/moderacion/sanciones` | Aplica sanción manual (`advertencia`, `suspension`, `bloqueo`). |
| **Moderador** | `POST /v1/moderacion/sanciones/{id}/apelacion` | Registra o resuelve apelación de sanción. |
| **Moderador** | `POST` y `PATCH /v1/moderacion/productos` | Crea o actualiza productos en el catálogo. |
| **Moderador** | `POST` y `PATCH /v1/moderacion/presentaciones` | Crea presentaciones (calculando `cantidad_base`) o las activa/desactiva. |
| **Moderador** | `POST` y `PATCH /v1/moderacion/establecimientos` | Crea o actualiza establecimientos en el directorio. |
| **Moderador** | `GET /v1/moderacion/catalogo-externo` | Consulta Open Food Facts por `codigo_barras` con *circuit breaker*. |
| **Moderador** | `GET` y `PUT /v1/moderacion/parametros` | Lista y actualiza las 43 claves de `config_parametro` con auditoría. |
| **Moderador** | `GET /v1/moderacion/auditoria` | Consulta paginada de la tabla `auditoria`. |
| **Moderador** | `POST /v1/moderacion/recalcular-precio-vigente` | Fuerza reconstrucción de `precio_vigente` para un producto o global. |
| **Comercio (Etapa 2)** | `POST /v1/comercio/reclamos` | Solicita reclamar la titularidad de un establecimiento (`D-09`). |
| **Comercio (Etapa 2)** | `GET /v1/comercio/establecimientos` | Lista los establecimientos verificados del comercio y sus 30 productos principales. |
| **Comercio (Etapa 2)** | `PUT /v1/comercio/establecimientos/{id}/precios` | Publica o actualiza hasta 200 precios oficiales en lote. |
| **Comercio (Etapa 2)** | `POST /v1/comercio/establecimientos/{id}/revalidar` | Acción «Todo sigue igual»: renueva `revalidado_en = now()` en sus precios vigentes. |
| **Comercio (Etapa 2)** | `GET`, `POST`, `DELETE /v1/comercio/establecimientos/{id}/promociones` | Gestiona promociones cumpliendo condiciones y vigencia de Ley 1480. |
| **Moderador (Etapa 2)** | `POST /v1/moderacion/comercios/{id}/verificar` | Aprueba verificación de comercio, asigna rol `comercio` y enlaza `comercio_id`. |
| **Jobs Internos** | `POST /internal/jobs/{nombre}` | Ejecuta `ping_bd`, `recalcular_reputacion`, `reconstruir_precio_vigente`, `limpiar_huellas` o `supervisor_ia`. |

### 6.4 Contratos JSON de Referencia (Sección 6.2 / 6.4)

**1. Respuesta de `GET /v1/productos/{id}/comparacion`:**
```json
{
  "datos": {
    "producto": {
      "id": "3b241101-e2bb-4255-8caf-4136c566a962",
      "nombre": "Arroz blanco",
      "categoria_id": 1,
      "unidad_base": "g",
      "unidad_visualizacion": "kg",
      "presentaciones": [
        {
          "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
          "etiqueta": "Arroz Diana 500 g",
          "marca": "Diana",
          "cantidad_base": 500.0
        }
      ]
    },
    "resultados": [
      {
        "establecimiento": {
          "id": "11111111-2222-3333-4444-555555555555",
          "nombre": "Tienda La Esquina",
          "tipo": "tienda_barrio",
          "barrio": "Centro",
          "direccion": "Cra 14 # 18-22",
          "distancia_m": 420
        },
        "presentacion": {
          "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
          "etiqueta": "Arroz Diana 500 g",
          "marca": "Diana",
          "cantidad_base": 500.0
        },
        "precio_cop": 2600,
        "precio_oficial_cop": null,
        "precio_por_unidad": {
          "valor_cop": 5200,
          "por": "kg"
        },
        "sello": "confiable",
        "motivo_sello": null,
        "n_reportes_validos": 4,
        "n_fuentes": 3,
        "ultimo_reporte_en": "2026-11-01T14:20:00Z",
        "con_foto_prueba": true,
        "es_bloque_secundario": false
      }
    ],
    "promociones": [],
    "meta": {
      "criterio_orden": "precio_unitario",
      "texto_neutralidad": "Ordenado por precio por kg. Las promociones no cambian el orden.",
      "bloques": ["vigentes", "dudosos_y_desactualizados"],
      "generado_en": "2026-11-01T14:22:10Z",
      "datos_de_demostracion": false
    }
  }
}
```

**2. Petición y Respuesta de `POST /v1/reportes` (con cabecera `Idempotency-Key: <uuid>`):**
```json
// Request
{
  "presentacion_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "establecimiento_id": "11111111-2222-3333-4444-555555555555",
  "precio_cop": 2600,
  "observado_en": "2026-11-01T14:19:00Z",
  "foto_ruta": null
}

// Response 201 Created (o 200 OK si la Idempotency-Key ya existía)
{
  "datos": {
    "id": "9f8e7d6c-5b4a-3c2d-1e0f-123456789abc",
    "estado_visible": "recibido",
    "mensaje": "Gracias, tu precio quedó registrado."
  }
}
```

### 6.5 Matriz de Permisos por Rol (Verificada con prueba parametrizada en `T-51`)
| Grupo de Endpoints | Anónimo (sin JWT) | Reportante (sin autorizar Ley 1581) | Reportante (`activa`) | Comercio (`activa` y `verificado`) | Moderador (`activa`) | Cuenta `suspendida` o `bloqueada` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `GET` públicos y `POST .../solicitudes-correccion` | `200 / 201` | `200 / 201` | `200 / 201` | `200 / 201` | `200 / 201` | `200 / 201` |
| `POST /v1/mi-cuenta/autorizacion` | `401` | `201` | `200` | `200` | `200` | `403 CUENTA_SUSPENDIDA` |
| `GET /v1/mi-cuenta` y `DELETE /v1/mi-cuenta` | `401` | `403 AUTORIZACION_REQUERIDA` | `200` | `200` | `200` | `200` (derecho de ley) |
| `POST /v1/reportes`, `/fotos/*`, `/sugerencias-*` | `401` | `403 AUTORIZACION_REQUERIDA` | `201` | `201` | `201` | `403 CUENTA_SUSPENDIDA` |
| `POST /v1/comercio/reclamos` | `401` | `403 AUTORIZACION_REQUERIDA` | `201` | `201` | `201` | `403 CUENTA_SUSPENDIDA` |
| `/v1/comercio/establecimientos/{id}/*` | `401` | `403 PROHIBIDO` | `403 PROHIBIDO` | `200 / 201` (solo si `comercio_id == usuario.id`, sino `404`) | `403 PROHIBIDO` | `403 CUENTA_SUSPENDIDA` |
| `/v1/moderacion/*` | `401` | `403 PROHIBIDO` | `403 PROHIBIDO` | `403 PROHIBIDO` | `200 / 201` | `403 CUENTA_SUSPENDIDA` |
| `POST /internal/jobs/{nombre}` | `401` (sin `X-Job-Token`) | `401` | `401` | `401` | `401` | `200` (solo con `X-Job-Token` válido) |

---

## 7. Especificación del Frontend (`frontend/`) — Pantallas y Componentes

### 7.1 Principios, Cola Offline y Accesibilidad WCAG 2.2 AA
* **Stack:** Next.js (App Router), TypeScript estricto, Tailwind CSS, `shadcn/ui` y `lucide-react`. Cliente HTTP generado desde `docs/api/openapi.json`.
* **Sincronización Offline:** Sigue el **Flujo `F4`** de la Sección 3.5 (primero obtiene URL firmada y sube el archivo WebP, guarda `foto_ruta_remota` en `IndexedDB` y luego envía `POST /v1/reportes` con `Idempotency-Key`).
* **Paleta de colores e íconos para `SelloConfianza` (contraste >= 4.5:1, nunca solo color):**
  * `confiable`: `bg-emerald-50 text-emerald-900 border-emerald-300` + ícono `CheckCircle2` + texto `"Confiable"`.
  * `oficial`: `bg-blue-50 text-blue-900 border-blue-300` + ícono `BadgeCheck` + texto `"Precio oficial"`.
  * `pocos_datos`: `bg-amber-50 text-amber-900 border-amber-300` + ícono `HelpCircle` + texto `"Pocos datos: ayúdanos a confirmarlo"`.
  * `en_disputa`: `bg-orange-50 text-orange-950 border-orange-400` + ícono `Scale` + texto `"En disputa: comercio vs. usuarios"`.
  * `desactualizado`: `bg-slate-100 text-slate-700 border-slate-300` + ícono `Clock` + texto `motivo_sello`.
  * `dudoso`: `bg-red-50 text-red-900 border-red-300` + ícono `AlertTriangle` + texto `motivo_sello`.

### 7.2 Las 7 Pantallas (`S1` a `S7`)
* **`S1 (/)` — Vitrina de Inicio:** Buscador superior, chips horizontales de categorías, cuadrícula `GrillaProductos` (24 por página) y botón fijo flotante «Reportar precio».
* **`S2 (/producto/[id])` — Comparador de Producto:** Encabezado del producto, filtro opcional de presentación, selector de orden (`precio_unitario`, `precio`, `distancia`), texto de neutralidad, `ListaPrecios` en dos bloques y `BloquePromociones` separado.
* **`S3 (/tienda/[id])` — Ficha de Establecimiento:** Datos de la tienda, precios vigentes paginados, promociones y botón *«¿Hay información errónea sobre este negocio?»*.
* **`S4 (/reportar)` — Registro Rápido (`EC-01` <= 15 s):** Una sola vista con 3 controles (`SelectorTienda`, `SelectorPresentacion`, `CampoPrecio`), botón opcional de cámara (compresión `<canvas>` a WebP <= 300 KB sin EXIF), soporte offline y modo `?medicion=1` que cronometra el tiempo en pantalla para la prueba de usabilidad.
* **`S5 (/ingresar)` — Acceso y Autorización Ley 1581:** Login/registro con Supabase Auth y paso obligatorio de aceptación de política de tratamiento de datos (casilla sin marcar por defecto) y elección de `alias`.
* **`S6 (/gestion)` — Panel Único por Rol (`TablaGestion`):**
  * *Pestañas Reportante:* `Mis reportes` y `Mi cuenta` (ver datos, editar alias, eliminar cuenta con anonimización).
  * *Pestañas Moderador:* `Cola de casos`, `Catálogo y tiendas`, `Parámetros (43)` y `Auditoría`.
  * *Pestañas Comercio (Etapa 2):* `Mis tiendas`, `Precios (Modo rápido + botón Todo sigue igual)` y `Promociones`.
* **`S7 (/legal)` — Transparencia y Créditos:** Política de tratamiento de datos versionada, términos de uso Ley 527, explicación pública de sellos/cálculos y créditos ODbL de OpenStreetMap y Open Food Facts.

### 7.3 Contrato de los 15 Componentes Reutilizables (`frontend/src/components/`)
| # | Componente | Props principales (TypeScript) | Responsabilidad visual |
| :---: | :--- | :--- | :--- |
| 1 | `AppShell` | `{ children: ReactNode }` | Navegación superior, buscador, enlace a `/gestion`, pie legal y botón flotante fijo a `/reportar`. |
| 2 | `TarjetaProducto` | `{ id, nombre, categoriaNombre, precioDesdePorUnidadCop, unidadVisualizacion, nTiendas }` | Tarjeta enlazada a `/producto/[id]` con precio mínimo por unidad formateado en `es-CO`. |
| 3 | `GrillaProductos` | `{ productos, siguienteCursor, onCargarMas }` | Cuadrícula responsive con paginación por cursor. |
| 4 | `SelloConfianza` | `{ sello: SelloPrecio, motivoSello: string \| null }` | Badge accesible (`role="status"`) con ícono + texto + borde según Sección 7.1. |
| 5 | `FilaPrecio` | `{ item: ItemComparacion, productoId: string }` | Muestra tienda, distancia, presentación, `SelloConfianza`, precio por unidad, precio empaque (con IVA) y contraste si está `en_disputa`. |
| 6 | `ListaPrecios` | `{ resultados, criterioOrden, productoId }` | Renderiza aviso de neutralidad, Bloque 1 arriba y divisor hacia Bloque 2 al final. |
| 7 | `BloquePromociones` | `{ promociones: ItemPromocion[] }` | Renderiza ofertas en contenedor separado con etiqueta `"Promoción"`; si está vacío retorna `null`. |
| 8 | `SelectorTienda` | `{ valor, onChange, tiendaRecienteId }` | Combobox con preselección de última tienda (< 2 h), botón de cercanía GPS en memoria y búsqueda. |
| 9 | `SelectorPresentacion` | `{ valor, onChange, recientesIds }` | Buscador de presentación con las 5 recientes arriba y enlace para sugerir presentación. |
| 10 | `CampoPrecio` | `{ valor, onChange, error }` | Input numérico grande (`inputMode="numeric"`) con separador de miles en vivo y aviso `"con IVA incluido"`. |
| 11 | `TablaGestion` | `{ columnas, datos, cargando, vacioTexto, siguienteCursor, onSiguiente }` | Tabla paginada reutilizable para todas las pestañas de `/gestion`. |
| 12 | `AvisoDatosDemo` | `{ visible: boolean }` | Banda amarilla superior cuando `datos_de_demostracion === true`. |
| 13 | `EstadoVacio` | `{ titulo, descripcion, accionTexto?, accionHref? }` | Vista vacía con llamada a la acción. |
| 14 | `EstadoError` | `{ detalle, codigo?, requestId?, onReintentar? }` | Alerta `role="alert"` que muestra el `detail` y `request_id` del `problem+json`. |
| 15 | `Cargando` | `{ filas?: number }` | Esqueleto de carga que respeta `prefers-reduced-motion`. |

---

## 8. Plan de Construcción Secuencial (`T-00` a `T-90`) y Reparto para 4 Integrantes

### 8.1 Roles de los 4 integrantes (para trazabilidad en el historial de Git)
* **Rol A (Arquitectura y Dominio de Precios — Líder técnico):** Esqueleto FastAPI, dominio de unidades/vigencia/sello/orden, módulo `precios`, caché en dos niveles, `PoliticaPrecioReferencia` y ADRs.
* **Rol B (Backend de Confianza, Cuentas y Moderación):** Dominio de anomalías/riesgo/reputación, módulos `cuentas`, `confianza`, `moderacion` y `comercial`, fotos sin EXIF y jobs internos.
* **Rol C (Frontend Web Responsive, PWA y Usabilidad):** Esqueleto Next.js, los 15 componentes, las 7 pantallas (`S1` a `S7`), cola offline `IndexedDB`, pruebas Playwright/`axe` y protocolo `EC-01`.
* **Rol D (Datos, DevOps y Aseguramiento de Calidad):** Entorno local con uv y scripts, migraciones SQL en Supabase, semilla CSV, CI/CD en GitHub Actions, despliegue con Docker en la nube, pruebas `k6` (`EC-04`), simulación `EC-03` e informes ISO/IEC 25010, 25012 y 25040.

### 8.2 Olas y Tareas en Orden Estricto de Construcción

#### Ola 0: Fundaciones, Entorno y Descubrimiento
| ID | Tarea | Depende de | Resp. | Archivos a crear / modificar | Hecho cuando… (Criterio verificable) |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **T-00** | Inicializar repositorio Git con GitHub Spec Kit (`agy`), crear carpetas de la Sección 3.1, guardar `PROYECTO.md`, `docs/PLAN_CONSTRUCCION.md`, `AGENTS.md` y `CLAUDE.md`, ejecutar los 4 comandos de Spec Kit (`constitution`, `specify`, `plan`, `tasks`) y proteger la rama `main` en GitHub. | — | **A + D** | `.specify/`, `.agents/`, `specs/001-nucleo-comparador/`, `PROYECTO.md`, `docs/PLAN_CONSTRUCCION.md`, `AGENTS.md`, `CLAUDE.md` | Existen los artefactos en `specs/001-nucleo-comparador/`, `git status` está limpio y `main` tiene Ruleset activo en GitHub. |
| **T-01** | Configurar entorno local reproducible sin Docker: entorno virtual de Python con uv, archivo `.env.example` (Sección 3.3), script de automatización `scripts/dev.cmd` y script `scripts/verificar_conexion.py` (verificación de conexión a Supabase y Upstash). | `T-00` | **D** | `.env.example`, `scripts/dev.cmd`, `scripts/verificar_conexion.py` | `uv venv` crea el entorno virtual, `uv pip install` instala dependencias de `pyproject.toml`, y `python scripts/verificar_conexion.py` valida conexión a Supabase y Upstash con éxito. |
| **T-02** | Crear migración `0001_fundaciones_seguridad.sql` (Sección 4.1: extensiones, rol `app_backend` con `LOGIN`, RLS y revocación a `anon`/`authenticated`), script `scripts/migrar.py` y prueba de seguridad SQL. | `T-01` | **D** | `supabase/migrations/0001_fundaciones_seguridad.sql`, `scripts/migrar.py`, `backend/tests/integracion/test_seguridad_bd.py` | La migración aplica con `MIGRATIONS_DATABASE_URL`, la app conecta como `app_backend` y la prueba confirma que `anon`/`authenticated` no leen tablas. |
| **T-03** | Implementar esqueleto de FastAPI: `pyproject.toml` (Sección 3.2), `Dockerfile` (Sección 3.4, reservado para despliegue en la nube en T-50), `config.py`, `bd.py`, `errores.py` (RFC 9457), `logging_cfg.py` (sin `lat`/`lng`), `reloj.py`, `seguridad.py` (JWKS/HS256), `/v1/salud`, `/v1/salud/listo` y `scripts/exportar_openapi.py`. | `T-02` | **A** | `backend/pyproject.toml`, `backend/Dockerfile`, `backend/app/main.py`, `backend/app/compartido/*`, `scripts/exportar_openapi.py`, `backend/tests/integracion/test_salud_y_auth.py` | `pytest` pasa `/v1/salud`, `/v1/salud/listo` y rechazos `401`/`403`; `Dockerfile` queda listo para el despliegue en T-50 y se exporta `docs/api/openapi.json`. |
| **T-04** | Implementar esqueleto de Next.js (App Router, TypeScript estricto, Tailwind, `shadcn/ui`), `AppShell`, generación de cliente tipado desde `docs/api/openapi.json` y cliente de sesión Supabase Auth. | `T-03` | **C** | `frontend/package.json`, `frontend/tsconfig.json`, `frontend/src/app/layout.tsx`, `frontend/src/components/AppShell.tsx`, `frontend/src/lib/api/*` | `npm run typecheck`, `npm run lint` y `npm run build` en `frontend/` terminan con código `0`. |
| **T-05** | Redactar documentos base de ingeniería: `ADR-001` a `ADR-018` en `docs/adr/`, diagramas C4 (C1, C2 y C3 en `docs/c4/`), `docs/PREGUNTAS_ABIERTAS.md` (con `PA-01` a `PA-04`), `docs/DECLARACION_USO_IA.md` y texto de política de tratamiento v1. | `T-00` | **A + D** | `docs/adr/0001-*.md`..`0018-*.md`, `docs/c4/*.mmd`, `docs/PREGUNTAS_ABIERTAS.md`, `docs/DECLARACION_USO_IA.md` | Existen los 18 ADRs, los 3 diagramas C4 en Mermaid y los registros formales. |
| **T-06** | Configurar CI en GitHub Actions (`.github/workflows/ci.yml`): `ruff`, `mypy --strict`, `import-linter`, `pytest` con servicios PostGIS/Redis, verificación de `openapi.json`, `npm run build` y `docker build`. | `T-03`, `T-04` | **D** | `.github/workflows/ci.yml` | El workflow ejecuta todas las verificaciones en verde. |
| **T-07** | Elaborar y aplicar entrevistas/encuestas a consumidores y al menos una tienda de barrio de Armenia (Entregable 1). | `T-00` | **Todos** | `docs/calidad/entregable_1_entrevistas.md` | Documento con instrumento, respuestas y hallazgos conectados con `EC-01` y `D-06`. |
| **T-08** | Elaborar estudio de Benchmarking de comparadores de precios y manejo de confiabilidad (Entregable 2). | `T-00` | **D** | `docs/calidad/entregable_2_benchmarking.md` | Tabla comparativa y conclusiones conectadas con `D-01` a `D-04`. |
| **T-09** | Consolidar Especificación de Requisitos y Calidad de Datos ISO/IEC 25012 (Entregable 3), Plan de Calidad ISO/IEC 25010:2023 (Entregable 4) y matriz `docs/calidad/trazabilidad.csv`. | `T-07`, `T-08` | **D** | `docs/calidad/entregable_3_requisitos_iso25012.md`, `docs/calidad/entregable_4_plan_calidad_iso25010.md`, `docs/calidad/trazabilidad.csv` | Entregables 3 y 4 completos y `trazabilidad.csv` vinculando cada `FR` y `EC` con su prueba. |

#### Ola 1: Catálogo Normalizado y Directorio de Establecimientos
| ID | Tarea | Depende de | Resp. | Archivos a crear / modificar | Hecho cuando… (Criterio verificable) |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **T-10** | Desarrollar con TDD `backend/app/dominio/unidades.py` (Sección 5.1). | `T-03` | **A** | `backend/app/dominio/unidades.py`, `backend/tests/unitarias/test_unidades.py` | Pasan todos los casos de la tabla de la Sección 5.1, la propiedad con `hypothesis` y cobertura del 100 % en `unidades.py`. |
| **T-11** | Aplicar migración `0002_catalogo_establecimientos_parametros.sql` (Sección 4.2) con las 10 categorías y los **43 parámetros** de `config_parametro`. | `T-02` | **D** | `supabase/migrations/0002_catalogo_establecimientos_parametros.sql`, `backend/tests/integracion/test_migracion_0002.py` | La migración aplica en limpio y la prueba automática verifica que existen exactamente las **43 claves** de la Sección 2.4 en `config_parametro`. |
| **T-12** | Crear archivos CSV en `supabase/seed/` (~150 productos con presentaciones y alias, ~30 establecimientos de Armenia con coordenadas OpenStreetMap) y script idempotente `scripts/semilla.py`. | `T-10`, `T-11` | **D** | `supabase/seed/*.csv`, `scripts/semilla.py`, `backend/tests/integracion/test_semilla.py` | Correr `python scripts/semilla.py` dos veces seguidas no duplica filas y deja el catálogo poblado. |
| **T-13** | Implementar lectura de `catalogo`: `GET /v1/categorias`, `GET /v1/productos` (`pg_trgm` + `unaccent`) y `GET /v1/productos/{id}`. | `T-12` | **A** | `backend/app/modulos/catalogo/*`, `backend/tests/integracion/test_api_catalogo.py` | Buscar `"arroz 1/2 kilo"` encuentra `"Arroz blanco"` con sus presentaciones en `< 300 ms`. |
| **T-14** | Implementar `establecimientos`: `GET /v1/establecimientos` (cercanía PostGIS), `GET /v1/establecimientos/{id}` y `POST /v1/establecimientos/{id}/solicitudes-correccion`. | `T-12` | **A** | `backend/app/modulos/establecimientos/*`, `backend/tests/integracion/test_api_establecimientos.py` | Filtra por `radio_km` y calcula `distancia_m` sin registrar `lat`/`lng` en logs; la solicitud de corrección abre caso en moderación. |
| **T-15** | Implementar endpoints de moderación de catálogo/tiendas, adaptador `open_food_facts.py` con *circuit breaker* y registro en `auditoria`. | `T-13`, `T-14` | **B** | `backend/app/puertos/catalogo_externo.py`, `backend/app/adaptadores/open_food_facts.py`, `backend/app/modulos/moderacion/*`, `backend/tests/integracion/test_moderacion_catalogo.py` | Crear presentación calcula `cantidad_base` con `dominio.unidades`, prohíbe editar `cantidad_base` y registra en `auditoria`. |
| **T-16** | Implementar `POST /v1/sugerencias-presentacion` y su aprobación en moderación. | `T-15` | **B** | `backend/app/modulos/catalogo/api.py`, `backend/tests/integracion/test_sugerencias_presentacion.py` | Un reportante sugiere una presentación, el moderador la aprueba y nace en `presentacion`. |

#### Ola 2: Reportes, Vigencia, Caché y Comparación (`EC-01`, `EC-02`, `EC-04`, `EC-06`)
| ID | Tarea | Depende de | Resp. | Archivos a crear / modificar | Hecho cuando… (Criterio verificable) |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **T-20** | Desarrollar con TDD `vigencia.py`, `sello.py` y `orden.py` (Secciones 5.4 y 5.5, leyendo siempre `params.sello_*` y `params.vigencia_*`). | `T-10` | **A** | `backend/app/dominio/vigencia.py`, `backend/app/dominio/sello.py`, `backend/app/dominio/orden.py`, `backend/tests/unitarias/test_vigencia_sello_orden.py` | Pasan todas las pruebas de 5.4 y 5.5 con `RelojFalso` y `mypy --strict` limpio. |
| **T-21** | Aplicar migración `0003_cuentas_precios_moderacion_auditoria.sql` (Sección 4.3) y probar inmutabilidad. | `T-11` | **D** | `supabase/migrations/0003_cuentas_precios_moderacion_auditoria.sql`, `backend/tests/integracion/test_inmutabilidad_reportes.py` | El trigger y los permisos de `app_backend` bloquean cualquier `DELETE` sobre `reporte_precio` y `auditoria` y cualquier `UPDATE` de `precio_cop`. |
| **T-22** | Implementar módulo `cuentas`: autorización Ley 1581, `GET`, `PATCH`, `DELETE /v1/mi-cuenta` (anonimización completa según `FR-007`) y `GET /v1/legal/politica-tratamiento`. | `T-03`, `T-21` | **B** | `backend/app/modulos/cuentas/*`, `backend/tests/integracion/test_cuentas_ley1581.py` | Al borrar una cuenta, sus reportes quedan con `reportante_id = null`, sin fotos y con alias anonimizado. |
| **T-23** | Implementar `POST /v1/reportes` hasta el paso 4 de `F2` (rango desde `config_parametro`, `Idempotency-Key` obligatoria y límites de uso en memoria) y `GET /v1/mis-reportes`. | `T-20`, `T-21`, `T-22` | **A** | `backend/app/compartido/limites.py`, `backend/app/modulos/precios/*`, `backend/tests/integracion/test_crear_reporte_idempotencia.py` | Reintentar con la misma `Idempotency-Key` devuelve `200 OK` sin duplicar; fuera de rango da `422 PRECIO_FUERA_DE_RANGO`; exceso da `429` con `Retry-After`. |
| **T-24** | Implementar `PoliticaPrecioReferencia` (`SoloUsuarios`), recálculo transaccional de `precio_vigente` y job `reconstruir_precio_vigente`. | `T-20`, `T-23` | **A** | `backend/app/puertos/politica_precio.py`, `backend/app/modulos/precios/servicio.py`, `backend/tests/integracion/test_precio_vigente_equivalencia.py` | Reconstruir `precio_vigente` desde cero produce exactamente las mismas filas y valores que el cálculo incremental. |
| **T-25** | Implementar `PuertoCache` y `cache_dos_niveles.py` (L1 5 s + L2 Redis 60 s, invalidación `DEL` y tope `generado_en <= 60s`). | `T-24` | **A** | `backend/app/puertos/cache.py`, `backend/app/adaptadores/cache_dos_niveles.py`, `backend/tests/integracion/test_cache_comparacion.py` | Con Redis detenido la API responde desde PostgreSQL sin error 500; jamás sirve un valor con más de 60 s. |
| **T-26** | Implementar `GET /v1/productos/{id}/comparacion` (Flujo `F1` y contrato de la Sección 6.4 con `"promociones": []`). | `T-20`, `T-25` | **A** | `backend/app/modulos/precios/api.py`, `backend/tests/integracion/test_comparacion_ec06.py` | Cumple el contrato JSON de 6.4 y pasa la prueba de neutralidad `EC-06`. |
| **T-27** | Implementar subida de fotos de prueba (`POST /v1/fotos/url-subida`) y limpieza de metadatos EXIF con Pillow. | `T-23` | **B** | `backend/app/puertos/almacenamiento.py`, `backend/app/adaptadores/storage_supabase.py`, `backend/tests/unitarias/test_limpieza_exif.py` | Una imagen con coordenadas GPS en EXIF queda sin EXIF; archivos > `foto.max_kb` se rechazan con `422 ARCHIVO_INVALIDO`. |

#### Ola 3: Detección de Anomalías, Reputación y Moderación (`EC-03`)
| ID | Tarea | Depende de | Resp. | Archivos a crear / modificar | Hecho cuando… (Criterio verificable) |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **T-30** | Desarrollar con TDD `backend/app/dominio/anomalia.py` (3 niveles jerárquicos + respaldo `sin_referencia`, z-score modificado y desviación porcentual). | `T-10` | **B** | `backend/app/dominio/anomalia.py`, `backend/tests/unitarias/test_anomalia.py` | Pasan todos los casos de la tabla de la Sección 5.3. |
| **T-31** | Desarrollar con TDD `riesgo.py` y `reputacion.py` (Secciones 5.2 y 5.3). | `T-30` | **B** | `backend/app/dominio/riesgo.py`, `backend/app/dominio/reputacion.py`, `backend/tests/unitarias/test_riesgo_reputacion.py` | 1.000 ejecuciones iguales dan el mismo resultado; cobertura de `backend/app/dominio/` >= 95 %. |
| **T-32** | Integrar evaluación completa en `POST /v1/reportes` (pasos 5 a 8 de `F2`), `huella_red` con HMAC diario, detección de `rafaga` y reevaluación hacia atrás. | `T-31`, `T-23` | **B** | `backend/app/compartido/huella.py`, `backend/app/modulos/confianza/servicio.py`, `backend/tests/integracion/test_rafaga_y_anomalia.py` | 3 cuentas nuevas desde la misma huella hacia una tienda en 30 min quedan todas en `dudoso`, abren caso `rafaga` y no alteran `precio_vigente`. |
| **T-33** | Implementar endpoints de moderación de casos, sanciones, apelaciones y auditoría. | `T-32` | **B** | `backend/app/modulos/moderacion/*`, `backend/tests/integracion/test_flujo_moderacion.py` | `confirmar` rechaza reporte y suma `M+1`; `descartar` acepta y recalcula `precio_vigente`; `sancionar` suspende; todo queda en `auditoria`. |
| **T-34** | Implementar jobs internos `POST /internal/jobs/{nombre}` con `X-Job-Token` y `.github/workflows/jobs.yml`. | `T-31`, `T-24` | **B + D** | `backend/app/tareas/router_jobs.py`, `.github/workflows/jobs.yml`, `backend/tests/integracion/test_jobs_internos.py` | `limpiar_huellas` anula huellas > 30 días y `recalcular_reputacion` actualiza perfiles correctamente. |
| **T-35** | Implementar `scripts/evaluar_ec03.py` y calibrar parámetros frente a las metas de `EC-03`. | `T-32` | **B + D** | `scripts/evaluar_ec03.py`, `docs/calidad/informe_ec03.md` | Detección individual >= 90 % (9/10), grupal >= 70 % (7/10) y falsas alarmas <= 10 % (1/10). |
| **T-36** | Implementar `GET` y `PUT /v1/moderacion/parametros` validando los rangos de las 43 claves de la Sección 2.4. | `T-33` | **B** | `backend/app/modulos/moderacion/api.py`, `backend/tests/integracion/test_parametros_negocio.py` | Cambiar `precio.min_cop` en `config_parametro` cambia de inmediato la validación de `/v1/reportes` y audita antes/después. |

#### Ola 4: Frontend del Núcleo (`S1` a `S7`) y Prueba de Usabilidad `EC-01`
| ID | Tarea | Depende de | Resp. | Archivos a crear / modificar | Hecho cuando… (Criterio verificable) |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **T-40** | Construir `S1 (/)` Inicio con buscador, categorías, `GrillaProductos`, `TarjetaProducto` y `AvisoDatosDemo`. | `T-04`, `T-13` | **C** | `frontend/src/app/page.tsx`, `frontend/src/components/TarjetaProducto.tsx`, `frontend/src/components/GrillaProductos.tsx` | Renderiza productos y categorías reales desde la API y filtra sin errores. |
| **T-41** | Construir `S2 (/producto/[id])` con `ListaPrecios`, `FilaPrecio`, `SelloConfianza`, selector de orden y `BloquePromociones`. | `T-26`, `T-40` | **C** | `frontend/src/app/producto/[id]/page.tsx`, `frontend/src/components/ListaPrecios.tsx`, `frontend/src/components/FilaPrecio.tsx`, `frontend/src/components/SelloConfianza.tsx`, `frontend/src/components/BloquePromociones.tsx` | Muestra el orden exacto de la API en dos bloques, sellos con ícono+texto y bloque de promociones separado. |
| **T-42** | Construir `S3 (/tienda/[id])` y modal de solicitud de corrección con *honeypot*. | `T-14`, `T-41` | **C** | `frontend/src/app/tienda/[id]/page.tsx` | La solicitud enviada desde la ficha crea un caso `solicitud_correccion` visible para el moderador. |
| **T-43** | Construir `S4 (/reportar)` con 3 controles, compresión WebP <= 300 KB en `<canvas>`, cola `IndexedDB` siguiendo el orden del **Flujo `F4`** y modo `?medicion=1`. | `T-23`, `T-27`, `T-40` | **C** | `frontend/src/app/reportar/page.tsx`, `frontend/src/components/SelectorTienda.tsx`, `frontend/src/components/SelectorPresentacion.tsx`, `frontend/src/components/CampoPrecio.tsx`, `frontend/src/lib/offline/colaReportes.ts`, `frontend/src/lib/imagen/comprimirFoto.ts` | En modo avión guarda reporte + foto en `IndexedDB`; al volver la red sube primero la foto a la URL firmada y luego el reporte con `Idempotency-Key` sin duplicar. |
| **T-44** | Construir `S5 (/ingresar)` con Supabase Auth y aceptación obligatoria de política Ley 1581. | `T-22`, `T-04` | **C** | `frontend/src/app/ingresar/page.tsx` | Sin aceptar la política no permite reportar; guarda versión y texto en `autorizacion_datos`. |
| **T-45** | Construir `S6 (/gestion)` con `TablaGestion` para `Reportante` y `Moderador`. | `T-33`, `T-36`, `T-44` | **C** | `frontend/src/app/gestion/page.tsx`, `frontend/src/components/TablaGestion.tsx` | Un moderador resuelve un caso dudoso desde la interfaz y un reportante puede ver sus reportes y borrar su cuenta. |
| **T-46** | Construir `S7 (/legal)` y `/offline` con política Ley 1581, explicación de sellos y créditos ODbL. | `T-05`, `T-40` | **C** | `frontend/src/app/legal/page.tsx`, `frontend/src/app/offline/page.tsx` | Textos completos alineados con las Secciones 5.3 a 5.5 y atribución ODbL visible. |
| **T-47** | Configurar PWA instalable (`manifest.webmanifest`) y pasar auditoría automática de accesibilidad WCAG 2.2 AA con `axe-core` en Playwright. | `T-40`..`T-46` | **C** | `frontend/public/manifest.webmanifest`, `frontend/tests/e2e/accesibilidad.spec.ts` | `axe-core` reporta 0 violaciones críticas o serias en las 7 pantallas. |
| **T-48** | Ejecutar prueba de usabilidad `EC-01` (10 usuarios reales, 3 intentos c/u con conexión móvil limitada) y redactar Entregable 7. | `T-43`, `T-47` | **C + D** | `docs/calidad/entregable_7_usabilidad_ec01.md` | Al menos 8 de cada 10 intentos se completan en <= 15 s. |

#### Ola 5: Despliegue y Medición del Núcleo (Cierre Corte 2)
| ID | Tarea | Depende de | Resp. | Archivos a crear / modificar | Hecho cuando… (Criterio verificable) |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **T-50** | Desplegar el núcleo de forma reproducible (Vercel, Railway con Docker, Supabase y Upstash) y activar jobs en GitHub Actions. | `T-06`, `T-34`, `T-47` | **D** | `README.md`, `docs/despliegue.md` | Sistema operativo en URL pública y job `ping_bd` respondiendo `200 OK`. |
| **T-51** | Implementar pruebas E2E en Playwright (consultar, reportar, moderar) y prueba parametrizada de la Matriz de Permisos de la Sección 6.5. | `T-45` | **B + C** | `frontend/tests/e2e/flujos_nucleo.spec.ts`, `backend/tests/contrato/test_matriz_permisos.py` | Los 3 flujos E2E y todas las celdas de la Matriz de Permisos 6.5 pasan en CI. |
| **T-52** | Elaborar Informe de TDD y Análisis Estático (Entregable 9). | `T-31`, `T-51` | **D** | `docs/calidad/entregable_9_tdd_analisis_estatico.md` | Evidencia de ciclos TDD, cobertura >= 95 % en dominio y 0 hallazgos críticos en `ruff`/`mypy`/`pip-audit`. |
| **T-53** | Ejecutar prueba de carga `EC-04` con `k6` (500 usuarios concurrentes con backend local y mock en memoria / Upstash según cuota) y documentar resultados. | `T-50` | **D** | `infra/k6/ec04_carga.js`, `docs/calidad/informe_ec04.md` | `p95 <= 2000 ms` y tasa de errores `< 1 %`. |
| **T-54** | Ejecutar prueba automática de `EC-02` (100 repeticiones de cambio de precio vigente). | `T-25`, `T-50` | **A** | `backend/tests/integracion/test_ec02_actualidad.py`, `docs/calidad/informe_ec02.md` | Peor tiempo observado en las 100 repeticiones <= 60 s. |
| **T-55** | Congelar núcleo con etiqueta Git `v1.0-nucleo` y entregar Documento de Arquitectura v1 (Entregables 5, 6 y 8). | `T-52`, `T-53`, `T-54` | **A + D** | `docs/entregable_5_arquitectura_v1.md` | Etiqueta `v1.0-nucleo` creada y documento v1 completo. |

#### Ola 6: Módulo Comercial — Etapa 2 (`EC-05`, `EC-06`)
| ID | Tarea | Depende de | Resp. | Archivos a crear / modificar | Hecho cuando… (Criterio verificable) |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **T-60** | Redactar Análisis de Impacto y estimación previa de `EC-05` **antes** de programar la Etapa 2 (Entregable 10 — Parte 1). | `T-55` | **A** | `docs/calidad/ec05-estimado.md` | Archivo confirmado en Git antes del commit de `T-61`. |
| **T-61** | Aplicar migración aditiva `0004_modulo_comercial.sql` (Sección 4.4). | `T-60` | **D** | `supabase/migrations/0004_modulo_comercial.sql` | Aplica sin modificar ni borrar columnas existentes del núcleo. |
| **T-62** | Implementar reclamo y verificación de comercios (`D-09`). | `T-61` | **B** | `backend/app/modulos/comercial/*`, `backend/tests/integracion/test_verificacion_comercio.py` | Solo comercios verificados publican precios oficiales o promociones sobre su establecimiento. |
| **T-63** | Implementar `PUT .../precios` (lote de hasta 200) y botón «Todo sigue igual» (`POST .../revalidar`). | `T-62` | **B** | `backend/app/modulos/comercial/api.py`, `backend/app/modulos/comercial/servicio.py` | Actualizar precio oficial recalcula `precio_vigente` e invalida caché en el acto. |
| **T-64** | Desarrollar con TDD la estrategia `OficialConContraste` (`D-01`) del puerto `PoliticaPrecioReferencia`. | `T-60`, `T-63` | **A** | `backend/app/puertos/politica_precio.py`, `backend/tests/unitarias/test_oficial_con_contraste.py` | Pasan pruebas de precio oficial, contradicción (`en_disputa`) y aviso de revalidación a los 30 días. |
| **T-65** | Implementar CRUD de promociones comerciales validando Ley 1480 y entrega en el arreglo separado `promociones`. | `T-62` | **B** | `backend/app/modulos/comercial/*`, `backend/tests/integracion/test_promociones_ley1480.py` | Promoción sin condiciones o sin vigencia devuelve `422`; toda promoción sale con `es_promocion = true`. |
| **T-66** | Implementar flujo de casos `disputa_precio`. | `T-64` | **B** | `backend/app/modulos/comercial/servicio.py`, `backend/app/modulos/moderacion/servicio.py` | La contradicción abre el caso y muestra ambos precios en pantalla. |
| **T-67** | Agregar pestañas de `Comercio` en `S6 (/gestion)` y sellos `oficial`/`en_disputa` en `S2` y `S3`. | `T-63`, `T-65`, `T-45` | **C** | `frontend/src/app/gestion/page.tsx`, `frontend/tests/e2e/flujo_comercio.spec.ts` | Un comercio actualiza 20 precios en modo rápido en menos de 1 minuto. |
| **T-68** | Reejecutar pruebas automáticas de `EC-02` (con precio oficial) y `EC-06` (con promociones activas + `import-linter`). | `T-64`, `T-65`, `T-67` | **A** | `backend/tests/integracion/test_ec02_ec06_etapa2.py` | `EC-02 <= 60 s` y `EC-06` al 100 %. |
| **T-69** | Medir esfuerzo real vs. estimado de `EC-05` y actualizar Documento de Arquitectura v2 (Entregables 10 y 11). | `T-68` | **A + D** | `docs/calidad/ec05-resultado.md`, `docs/entregable_10_arquitectura_v2.md` | Informe comparativo demostrando 0 rediseños estructurales del núcleo. |

#### Ola 7 (Fase 2 — Plus con IA) y Ola 8 (Evaluación Final y Sustentación)
| ID | Tarea | Depende de | Resp. | Archivos a crear / modificar | Hecho cuando… (Criterio verificable) |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **T-70** | Ejecutar prueba de humo de la Idea A con 20 a 30 fotos reales de etiquetas de Armenia. | `T-55` | **D** | `docs/calidad/prueba_humo_ia_etiquetas.md` | Tabla de aciertos en producto, precio y cantidad documentada. |
| **T-71** | Implementar puerto `ProveedorIA` y adaptador `ia_gemini.py` con *timeout* de 3 s y *circuit breaker* (`D-12`). | `T-70` | **A** | `backend/app/puertos/proveedor_ia.py`, `backend/app/adaptadores/ia_gemini.py` | Si Gemini falla, el sistema cae limpiamente al formulario manual. |
| **T-72** | Implementar lectura de etiqueta por foto en `/reportar` exigiendo confirmación del usuario con un toque (`FR-026`). | `T-71`, `T-43` | **A + C** | `backend/app/modulos/precios/api.py`, `frontend/src/app/reportar/page.tsx` | Jamás se publica un precio leído por IA sin confirmación explícita del usuario. |
| **T-73** | Aplicar migración `0005_supervisor_ia.sql` e implementar job diario `supervisor_ia`. | `T-71`, `T-34` | **B** | `supabase/migrations/0005_supervisor_ia.sql`, `backend/app/tareas/router_jobs.py` | El supervisor genera informe diario consultivo sin tomar decisiones ni sancionar cuentas. |
| **T-90** | Elaborar Evaluación de Arquitectura ATAM (Entregable 12), Informe de Evaluación de Calidad ISO/IEC 25040 y 25012 (Entregable 13), Calidad del Proceso CMMI/ISO 330xx (Entregable 14), Artículo resumen (Entregable 15) y Sustentación (Entregable 16). | `T-69` | **Todos** | `docs/entregable_12_evaluacion_atam.md`, `docs/calidad/entregable_13_evaluacion_iso25040.md`, `docs/calidad/entregable_14_proceso_cmmi.md`, `docs/entregable_15_articulo.md` | Todos los entregables del Corte 3 terminados y demo ensayada. |

---

## 9. Aseguramiento de Calidad, Escenario `k6` (`EC-04`) e ISO/IEC 25012

### 9.1 Estrategia de Pruebas y Cobertura
* **Unitarias de dominio (`pytest` + `hypothesis`):** Cobertura obligatoria >= 95 % de líneas y ramas en `backend/app/dominio/`.
* **Integración y contrato (`pytest` + `schemathesis`):** Cobertura >= 80 % en el resto del backend; prueba parametrizada de la Matriz de Permisos (Sección 6.5).
* **Escenario de carga `infra/k6/ec04_carga.js` (`EC-04`):** Rampa de 0 a 500 VUs en 2 min, sostenimiento 5 min, pausa de 1 a 3 s. Mezcla: 60 % `GET /v1/productos`, 30 % `GET .../comparacion`, 5 % `GET /v1/establecimientos`, 5 % `POST /v1/reportes`. Umbrales: `http_req_failed < 0.01` y `http_req_duration{endpoint:comparacion} p(95) < 2000`. Se ejecuta contra el backend local utilizando mock en memoria para Redis (o instancia Upstash controlada) para no agotar la cuota de comandos.

### 9.2 Matriz de Calidad de Datos ISO/IEC 25012
| Característica | Prioridad | Significado en el comparador | Mecanismo técnico que la protege |
| :--- | :---: | :--- | :--- |
| **Credibilidad** | Crítica (1) | El precio es creíble para quien consulta | Evaluación determinista `D-03`, reputación bayesiana, fotos de prueba y sellos explícitos. |
| **Actualidad** | Crítica (2) | El precio no está vencido | Decaimiento exponencial (48 h / 72 h), ventana de 7 y 30 días e invalidación en <= 60 s (`EC-02`). |
| **Exactitud** | Crítica (3) | El valor coincide con el de la góndola | Entero estricto en rango, z-score modificado (`3.5`) y detección de `ratio_extremo` (`5x`). |
| **Consistencia** | Crítica (4) | Sin contradicciones entre presentaciones | Conversión obligatoria a `unidad_base`, referencia jerárquica en 3 niveles y dispersión `MAD/mediana <= 0.15`. |
| **Completitud** | Alta (5) | Datos suficientes para comparar | Semilla de ~150 productos y ~30 tiendas, y sello `pocos_datos` cuando hay < 3 reportes o < 2 fuentes. |
| **Trazabilidad** | Alta (6) | Se conoce el origen de cada precio y cambio | Historial inmutable en `reporte_precio` y bitácora *append-only* en `auditoria`. |
| **Confidencialidad** | Alta (7) | Protección de datos personales del reportante | RLS sin políticas públicas, ausencia de GPS en BD/logs, `huella_red` con HMAC diario y anonimización al borrar cuenta. |

---

## 10. Catálogo de Decisiones Arquitectónicas (`ADR-001` a `ADR-018`)

1. **`ADR-001`:** PWA responsive *mobile-first* frente a app móvil nativa.
2. **`ADR-002`:** Monolito modular frente a microservicios y frente a BaaS sin backend.
3. **`ADR-003`:** Backend en Python con FastAPI frente a Node.js con NestJS.
4. **`ADR-004`:** Frontend en Next.js con cliente tipado OpenAPI y cero lógica de negocio en cliente.
5. **`ADR-005`:** Persistencia en Supabase (PostgreSQL + PostGIS, Auth, Storage) frente a NoSQL.
6. **`ADR-006`:** Caché en Redis (Upstash) con TTL de 60 s para cumplir `EC-02` y `EC-04`.
7. **`ADR-007`:** Patrón *Strategy* para proveedores de IA con Gemini Flash primero en Fase 2.
8. **`ADR-008`:** Despliegue en Vercel + contenedor Docker en Railway y jobs en GitHub Actions.
9. **`ADR-009`:** Historial inmutable `reporte_precio` separado del modelo de lectura `precio_vigente`.
10. **`ADR-010`:** Cola offline en `IndexedDB` (orden: foto firmada primero, reporte después) e `Idempotency-Key` obligatoria (`EC-01`).
11. **`ADR-011`:** Conjunto de referencia jerárquico en 3 niveles más respaldo `sin_referencia` y z-score modificado (`EC-03`).
12. **`ADR-012`:** RLS activada sin políticas públicas y conexión exclusiva del backend mediante rol `app_backend` con `LOGIN` y permisos mínimos.
13. **`ADR-013`:** Puerto `PoliticaPrecioReferencia` y exclusión de tablas comerciales en el núcleo para medir `EC-05`.
14. **`ADR-014`:** Huella de red mediante `HMAC-SHA256` diario y purga a los 30 días.
15. **`ADR-015`:** Servicios externos fuera del camino crítico con *timeout* de 3 s y *circuit breaker*.
16. **`ADR-016`:** Caché de dos niveles (L1 5 s + L2 Redis 60 s) y límites de uso en memoria para proteger la cuota gratuita de Upstash.
17. **`ADR-017`:** Portabilidad del contenedor Docker hacia Render Free / Fly.io como contingencia de costo cero.
18. **`ADR-018`:** Ordenamiento en dos bloques por `precio_por_base` y separación estructural de promociones (`EC-06`).