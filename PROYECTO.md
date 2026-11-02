# Plataforma Colaborativa de Comparación de Precios

Plataforma web informativa donde los ciudadanos registran los precios que observan en tiendas de barrio, minimercados y supermercados, cualquier persona puede consultarlos y compararlos libremente, y los comercios pueden crear un perfil voluntario para publicar precios oficiales y promociones. El foco inicial es Armenia y el departamento del Quindío.

No es una tienda virtual: quedan fuera del alcance la venta en línea, el carrito de compras, los pagos, los pedidos y los domicilios, y no pretende sustituir a las autoridades de protección al consumidor ni constituir un sistema oficial de precios.

## 1. El problema y la idea

* **Problema:** Un mismo producto de la canasta familiar presenta precios muy distintos según el establecimiento, el barrio o la presentación, pero la información está dispersa y el consumidor rara vez puede comparar antes de comprar. Por ejemplo: una bolsa de arroz de 500 g cuesta $2.600 en una tienda de barrio y $3.100 en un supermercado de cadena, sin que exista un canal neutral que lo visibilice. Esta asimetría afecta a dos grupos:
  * Los hogares, especialmente aquellos de presupuesto ajustado.
  * Las tiendas de barrio y comercios pequeños, que ofrecen precios competitivos pero carecen de canales digitales frente a la capacidad publicitaria de las grandes cadenas.
* **Idea:**
  * La comunidad reporta los precios que ve en los establecimientos.
  * Cualquier persona consulta y compara precios sin necesidad de crear cuenta.
  * Los comercios participan voluntariamente publicando precios oficiales y promociones.
* **El reto técnico central:** Los datos provienen de fuentes con distinto nivel de confiabilidad e intereses en conflicto (usuarios ocasionales, usuarios frecuentes y comercios con interés propio) y pierden vigencia con el tiempo. El sistema debe presentar información confiable, actualizada y neutral incluso frente a errores de digitación o intentos deliberados de manipulación.

## 2. Actores

| Actor | Quién es | Qué necesita | Qué implica para el sistema |
| :--- | :--- | :--- | :--- |
| **Consumidor** | Persona que consulta precios para decidir dónde comprar (con o sin cuenta). | Encontrar rápido dónde es más económico un producto con información confiable. | Consultas públicas de muy baja latencia y sellos claros de vigencia y veracidad. |
| **Reportante** | Consumidor registrado que aporta precios observados en tiendas. | Registrar un precio en pocos segundos desde el pasillo y con señal móvil limitada. | Formulario mínimo de 3 controles, cola de envío offline e idempotencia. |
| **Comercio** | Tienda, minimercado o supermercado con perfil voluntario. | Publicar precios oficiales y promociones, hacerse visible y solicitar correcciones sobre su negocio. | Panel de actualización ágil y reglas para reconciliar precios oficiales frente a reportes comunitarios. |
| **Moderador** | Rol administrativo de la plataforma. | Atender reportes dudosos, gestionar el catálogo y las cuentas, y preservar la integridad de la comparación. | Bandeja de casos priorizada, auditoría inmutable y gestión de parámetros y sanciones. |

**Principios operativos sobre los actores:**
* Las consultas de comparación superan ampliamente en volumen a los registros de precios. El diseño optimiza la lectura mediante precalculado y caché.
* La participación de un comercio es voluntaria y nunca otorga privilegios en el posicionamiento: el contenido promocional jamás altera el orden de los resultados.

## 3. Alcance funcional y evolución en dos etapas

El sistema se construye en dos incrementos para evaluar con evidencia la capacidad de evolución de la arquitectura:

* **Etapa 1 — Núcleo (comparación colaborativa de precios):**
  * **Catálogo normalizado de productos:** Reconoce un mismo producto en distintas marcas, presentaciones y denominaciones (ej. "arroz 500 g" y "arroz 1/2 kg").
  * **Registro colaborativo de precios:** Vincula cada reporte a una presentación específica y a un establecimiento, conservando un historial inmutable y foto opcional de prueba.
  * **Directorio de establecimientos:** Tiendas de barrio, minimercados y supermercados geolocalizados.
  * **Consulta y comparación normalizada:** Compara entre establecimientos incluyendo el cálculo de **precio por unidad de medida base** (g, ml, unidad). Ejemplo: 1 kg a $5.000 equivale a $5.000/kg, mientras que 500 g a $2.800 equivale a $5.600/kg; el primero se posiciona como más económico.
* **Etapa 2 — Módulo comercial (se incorpora sobre el núcleo):**
  * Perfil voluntario de comercio verificado por moderación.
  * Publicación y revalidación rápida de precios oficiales.
  * Publicación de promociones con reglas estructuradas (descuento porcentual, precio especial, "pague X lleve Y" y vigencia).
  * Integración y contraste entre el precio oficial del comercio y los reportes de la comunidad.
* **Preparación arquitectónica para el cambio (EC-05):** El módulo comercial se incorpora sin rediseñar estructuralmente el núcleo. Para que la medición de modificabilidad sea real, el núcleo no crea por adelantado las tablas comerciales; únicamente deja definidos tres puntos de extensión: el puerto `PoliticaPrecioReferencia`, la columna anulable `establecimiento.comercio_id` y el arreglo `promociones: []` separado en la respuesta de comparación.
* **Fuera de alcance:** Venta en línea, carrito, pagos, pedidos, domicilios, perfilamiento de usuarios para recomendaciones e intermediación comercial.

## 4. Escenarios de calidad y umbrales medibles

| ID | Atributo (ISO/IEC 25010 / 25012) | Escenario | Meta y umbral de aceptación |
| :--- | :--- | :--- | :--- |
| **EC-01** | Capacidad de interacción (Operabilidad) | Un reportante frente a la góndola, con conectividad móvil limitada, registra un precio. | Completado en <= 15 s en al menos el 80 % de los intentos (8/10) en prueba con 10 usuarios reales (3 intentos c/u). |
| **EC-02** | Actualidad del dato y Comportamiento temporal | Cambia el precio vigente de un producto en un establecimiento. | El precio anterior deja de mostrarse como vigente en <= 60 s en el 100 % de las ejecuciones (100 repeticiones automáticas). |
| **EC-03** | Credibilidad del dato e Integridad | Un usuario o un grupo coordinado registra precios falsos de un establecimiento. | Detección de >= 9/10 falsos individuales y >= 7/10 grupales, con máximo 1/10 de falsos positivos sobre reportes honestos. Ningún dato dudoso se presenta como vigente sin advertencia. |
| **EC-04** | Eficiencia de desempeño | En fin de semana de quincena, 500 usuarios concurrentes consultan comparaciones. | Percentil 95 (p95) del tiempo de respuesta <= 2 s y tasa de error < 1 %. |
| **EC-05** | Mantenibilidad (Modificabilidad) | Se incorpora el módulo comercial sobre el núcleo construido. | 0 rediseños estructurales en tablas o dominio del núcleo; registro comparativo entre esfuerzo estimado y real. |
| **EC-06** | Corrección funcional y Neutralidad | Un comercio publica una promoción activa. | El orden de comparación es 100 % idéntico con y sin promociones, y el 100 % de las promociones se muestra en un bloque separado y etiquetado. |

## 5. Decisiones frente a las 8 preguntas de diseño

| # | Pregunta de diseño | Decisión adoptada y justificación |
| :--- | :--- | :--- |
| **1** | **Comercio vs. usuarios (D-01):** Cuando el comercio publica un precio oficial y los usuarios reportan otro distinto, ¿cuál se muestra? | **Política de precio con contraste:** En la Etapa 1 rige la mediana ponderada de usuarios. En la Etapa 2 se muestra el precio oficial (`sello = oficial`), salvo contradicción comunitaria: al menos 3 reportes aceptados de al menos 2 cuentas distintas en las últimas 48 h cuya mediana difiera en >= 10 % del oficial. En contradicción el sello pasa a `en_disputa`, se posiciona usando el precio de los usuarios y se exhiben ambos valores de forma transparente. |
| **2** | **Vigencia (D-02):** ¿A partir de qué momento un precio reportado deja de ser confiable? | **Decaimiento exponencial y ventanas de 7 y 30 días:** Un reporte mantiene el 100 % de su peso durante 48 h y se reduce a la mitad cada 72 h. Entre los días 1 y 7 es vigente (sello `confiable` si tiene >= 3 reportes de >= 2 fuentes, o `pocos_datos` si tiene menos); entre los días 8 y 30 pasa al segundo bloque con sello `desactualizado`; tras 30 días sale de la comparación activa y permanece únicamente en el historial. El precio oficial dura hasta que el comercio lo modifique y a los 30 días sin cambios muestra el aviso "por revalidar". |
| **3** | **Reportes falsos (D-03):** ¿Cómo se detectan y tratan reportes erróneos o malintencionados? | **Evaluación determinista por capas:** (1) Rango duro ($50 a $2.000.000 COP parametrizado); (2) Comparación contra conjunto de referencia jerárquico en 3 niveles (misma presentación+tienda -> misma presentación en el municipio -> mismo producto por unidad base; respaldo `sin_referencia`) mediante z-score modificado (abs(M) > 3.5 con n >= 5) o desviación porcentual (> 30 % con n entre 3 y 4 o MAD=0); (3) Puntaje de riesgo de contexto (sin foto, cuenta nueva, baja reputación y ráfaga por huella de red). Lo anómalo queda en estado `dudoso` (no altera el precio vigente y abre caso al moderador), mostrando al autor "Recibido, en revisión". Las sanciones solo las aplica un moderador humano. |
| **4** | **Reconocimiento de productos (D-04):** ¿Cómo se reconoce el mismo producto y se comparan tamaños distintos? | **Catálogo cerrado en dos niveles:** Nivel 1 `producto` (familia genérica con una única `unidad_base`: g, ml o unidad) y Nivel 2 `presentacion` (marca, contenido neto, multiplicador y `cantidad_base` precalculada). Los usuarios no crean productos en texto libre al reportar: buscan en el catálogo con tolerancia a tildes y fracciones (`pg_trgm` + `unaccent`) o envían una sugerencia a moderación. La comparación se realiza siempre por **precio por unidad base**. |
| **5** | **Datos iniciales (D-05):** ¿De dónde provienen los primeros datos antes de tener comunidad? | **Semilla propia verificable:** Carga reproducible por CSV (`scripts/semilla.py`) con ~150 productos de canasta básica y sus presentaciones, ~30 establecimientos de Armenia con coordenadas de OpenStreetMap (bajo atribución ODbL), precios reales levantados en 5 a 8 comercios locales (`fuente = semilla`) y datos de prueba marcados explícitamente con `es_demo = true` ("Datos de demostración"). Se descarta SIPSA (DANE) para el catálogo minorista por tratarse de precios mayoristas agropecuarios y evitamos riesgo con términos de uso de terceros. |
| **6** | **Comercio pequeño (D-06):** ¿Cómo participa una tienda de barrio sin sistema POS ni tiempo? | **Visibilidad comunitaria y Modo rápido:** Toda tienda de barrio aparece sin costo gracias a los reportes de los consumidores. Si decide reclamar su perfil en la Etapa 2, dispone de una vista móvil de "Modo rápido" con sus 20 a 30 productos más consultados y un botón "Todo sigue igual" que renueva la fecha de sus precios oficiales vigentes con un solo toque. |
| **7** | **Neutralidad (D-07, D-13):** ¿Cómo se garantiza que las promociones no alteren la comparación? | **Separación garantizada por diseño y verificada con pruebas:** Las promociones se almacenan en su propia tabla y viajan en un arreglo JSON separado (`promociones`) distinto de `resultados`, siempre con `es_promocion = true`. Una regla de arquitectura (`import-linter`) prohíbe que el módulo `precios` importe al módulo `comercial`. El ordenamiento por defecto es por **precio por unidad base** dividido en dos bloques (D-13: primero vigentes; al final dudosos y desactualizados). |
| **8** | **Inmediatez vs. diferido (D-08):** ¿Qué responde al instante y qué se actualiza con retraso? | **Modelo de lectura precalculado:** Responden al instante la consulta de comparación (lectura de `precio_vigente` + caché de dos niveles), la recepción y evaluación del reporte, la actualización transaccional de `precio_vigente` y la invalidación de caché. Se ejecutan en diferido (GitHub Actions): recálculo de reputación (cada hora), reconstrucción nocturna completa de `precio_vigente`, purga de huellas de red > 30 días (diaria) e informe del supervisor IA (diario en Fase 2). |

## 6. Mínimos de ingeniería y calidad

* **Documentación de arquitectura (Modelo C4):** Diagramas en Mermaid versionados en `docs/c4/` cubriendo Nivel 1 (Contexto), Nivel 2 (Contenedores) y Nivel 3 (Componentes de `precios` y `confianza`).
* **Decisiones arquitectónicas (ADRs):** Registro completo (`ADR-001` a `ADR-018`) en `docs/adr/` con contexto, alternativas descartadas y consecuencias.
* **Contrato de API:** API REST en `/v1` documentada y exportada automáticamente en OpenAPI (`docs/api/openapi.json`), a partir de la cual se genera el cliente tipado del frontend.
* **Desarrollo guiado por pruebas (TDD):** El núcleo de reglas de negocio (`backend/app/dominio/`) es código puro sin entrada/salida desarrollado mediante TDD (`pytest` + `hypothesis`) con cobertura >= 95 %.
* **Repositorio Git:** Con historial verificable que evidencie el trabajo de los cuatro integrantes del equipo.
* **Marco de calidad (ISO/IEC 25010, 25012 y 25040):** Modelo de calidad de producto justificado frente al modelo de Boehm, modelo de calidad de datos enfocado en Exactitud, Credibilidad, Actualidad, Consistencia, Completitud, Trazabilidad y Confidencialidad, y evaluación sistemática conforme a ISO/IEC 25040.

## 7. Ética y cumplimiento legal por diseño

* **Protección de datos personales (Ley 1581 de 2012 y Decreto 1074 de 2015):**
  * Autorización previa, expresa e informada registrada en `autorizacion_datos` con versión de la política antes de crear el perfil del usuario.
  * Ejercicio de derechos de conocer, actualizar alias y suprimir cuenta en `/v1/mi-cuenta`. Al eliminar la cuenta se anonimizan los reportes históricos (`reportante_id = null`), se reemplaza el alias y se eliminan las fotografías asociadas.
  * Las coordenadas GPS del usuario jamás se almacenan en base de datos ni en archivos de log; solo se emplean en memoria durante la petición para calcular distancia.
  * Para detectar ataques en ráfaga sin guardar direcciones IP en texto plano, se almacena `huella_red = HMAC-SHA256(IP, secreto_diario)` con purga automática a los 30 días (D-11).
  * En los perfiles comerciales se exhibe únicamente la denominación comercial del establecimiento, nunca datos personales del propietario persona natural.
* **Protección al consumidor (Ley 1480 de 2011) y Comercio electrónico (Ley 527 de 1999):**
  * Todos los precios se registran y muestran en pesos colombianos enteros (`precio_cop`) con todos los impuestos incluidos (`incluye_impuestos = true`).
  * Toda promoción exige condiciones claras (tiempo, modo y lugar) y fecha de fin explícita o marca `hasta_revocar = true`.
* **Libre competencia y propiedad intelectual (Ley 155 de 1959, Ley 1340 de 2009, Ley 23 de 1982):**
  * Ningún comercio tiene acceso a precios no públicos de competidores ni existen canales de mensajería entre comercios.
  * No se realiza extracción no autorizada de sitios de terceros. El uso de OpenStreetMap y Open Food Facts respeta sus límites de uso y muestra la atribución de licencia ODbL en la interfaz.
* **Accesibilidad:** Cumplimiento de pautas WCAG 2.2 Nivel AA verificado con `axe` y navegación por teclado.

## 8. Fuentes de datos externas

Ninguna API externa se encuentra en el camino crítico de lectura ni de registro de precios (D-12).

| Fuente | Uso en la plataforma | Regla de integración y contingencia |
| :--- | :--- | :--- |
| **OpenStreetMap / Nominatim** | Coordenadas iniciales de establecimientos de Armenia y geocodificación puntual en moderación. | Máximo 1 req/s, con caché y atribución ODbL visible en pantalla. |
| **Open Food Facts** | Consulta puntual por código de barras para autocompletar marca y cantidad al crear presentaciones en moderación. | Cabecera `User-Agent` propia y atribución ODbL. Sin copia masiva de volcados. Si falla, el moderador digita los campos manualmente. |
| **SIPSA (DANE)** | Referencia documental en benchmarking. | Descartada para el catálogo minorista por contener precios mayoristas agropecuarios. |
| **Open Prices** | Referente internacional en el estudio de benchmarking. | Modelo de referencia documental sobre pruebas fotográficas; no se consume su API. |

## 9. Fase 2: Capacidades asistidas por IA (Plus posterior a la Fase 1)

Se abordan únicamente tras completar y verificar la Fase 1 (Núcleo + Módulo Comercial):
1. **Prioridad 1 — Registro por foto de etiqueta (Idea A) + Supervisor IA diario (Idea B):**
   * **Idea A:** El reportante toma foto de la etiqueta del estante, el adaptador de IA (Gemini Flash bajo patrón Strategy) extrae producto, precio y tamaño, y el usuario **confirma explícitamente con un toque** antes de guardar. Jamás se publica un precio sin confirmación humana ni se envían datos personales en las imágenes.
   * **Idea B:** Un trabajo programado diario resume los casos marcados como `dudoso` por el motor determinista y genera un informe consultivo para el moderador humano.
2. **Prioridad 2 (Opcional si resta tiempo) — Lista de compras inteligente (Idea C) y Alertas de bajada de precio (Idea D).**

## 10. Arquitectura, stack tecnológico e interfaz

* **Estilo arquitectónico (ADR-002):** Monolito modular en un único repositorio (`backend/`, `frontend/`, `supabase/`, `docs/`, `infra/`, `scripts/`).
* **Backend (ADR-003):** Python 3.12, FastAPI, Pydantic v2 (`extra='forbid'`) y SQLAlchemy 2.0 asíncrono (`asyncpg`).
* **Frontend (ADR-001, ADR-004):** Next.js (App Router, TypeScript estricto, Tailwind CSS, `shadcn/ui`), PWA instalable mobile-first. Cero lógica de negocio en el cliente web.
* **Las 7 pantallas del sistema:**
  * `S1 (/)`: Vitrina de inicio con buscador, filtro por categorías, cuadrícula de productos ("Desde $X por kg en N tiendas") y botón flotante fijo "Reportar precio".
  * `S2 (/producto/[id])`: Comparador de precios en dos bloques con sellos de confianza, selector de criterio de orden y bloque separado de `Promociones`.
  * `S3 (/tienda/[id])`: Ficha del establecimiento, precios vigentes, promociones activas y formulario público para reportar información errónea del negocio.
  * `S4 (/reportar)`: Formulario rápido de 3 controles (establecimiento, presentación y precio en COP + foto opcional) con compresión WebP en cliente y cola offline en `IndexedDB`.
  * `S5 (/ingresar)`: Autenticación con Supabase Auth y paso obligatorio de aceptación de tratamiento de datos (Ley 1581) y creación de alias.
  * `S6 (/gestion)`: Panel unificado basado en el componente `TablaGestion` con pestañas según rol (`Reportante`, `Moderador` y `Comercio`).
  * `S7 (/legal)`: Política de tratamiento de datos, términos de uso, explicación pública de sellos/cálculos y créditos ODbL.
* **Persistencia y seguridad (ADR-005, ADR-012):** Supabase (PostgreSQL + PostGIS, Auth, Storage privado). RLS habilitada sin políticas públicas: el frontend solo usa Supabase para autenticación; todo acceso a datos pasa por FastAPI con el rol `app_backend`.
* **Caché y límites de uso (ADR-006, ADR-016):** Caché de dos niveles (L1 en memoria de 5 s + L2 en Redis de Upstash con TTL de 60 s). Límites de uso en memoria del proceso.
* **Despliegue reproducible (ADR-008, ADR-017):** Frontend en Vercel; Backend containerizado con Docker en Railway (con portabilidad a Render Free / Fly.io); tareas programadas e integración continua en GitHub Actions.
* **Metodología de desarrollo:** Desarrollo Guiado por Especificaciones (SDD) instrumentado con GitHub Spec Kit (`specify-cli`).

## 11. Entregables académicos por corte

| Hecho | N.º | Entregable | Asignatura | Contenido principal |
| :---: | :---: | :--- | :--- | :--- |
| [ ] | **1** | Entrevistas o encuestas | Ambas | Validación con consumidores y al menos una tienda de barrio (T-07). |
| [ ] | **2** | Benchmarking | Ambas | Comparativa de soluciones nacionales/internacionales y manejo de confiabilidad (T-08). |
| [ ] | **3** | Especificación de requisitos y calidad de datos | Modelos de Calidad | Requisitos del núcleo, escenarios refinados, características ISO/IEC 25012 y matriz de trazabilidad (T-09). |
| [x] | **4** | Plan de aseguramiento de calidad | Modelos de Calidad | Modelo ISO/IEC 25010:2023 justificado frente a Boehm, métricas, umbrales y estrategia de pruebas (T-09). |
| [ ] | **5** | Documento de arquitectura v1 del núcleo | Arquitectura II | Contexto, conductores arquitectónicos, comparación de alternativas, diagramas C4 y contrato OpenAPI (T-55). |
| [ ] | **6** | Registro de decisiones arquitectónicas (ADRs) | Arquitectura II | ADR-001 a ADR-018 en formato MADR (T-05, continuo). |
| [ ] | **7** | Prototipo con prueba de usabilidad | Modelos de Calidad | Flujos de registro y consulta probados con 10 usuarios reales frente a EC-01 (T-48). |
| [ ] | **8** | Núcleo funcional desplegado | Arquitectura II | Registro y comparación operando de extremo a extremo en producción con API documentada (T-50, T-55). |
| [ ] | **9** | Informe de TDD y análisis estático | Modelos de Calidad | Evidencia de ciclos rojo-verde-refactor, cobertura y análisis estático (T-52). |
| [ ] | **10** | Análisis de impacto y arquitectura v2 | Arquitectura II | Estimación previa (T-60), efecto del módulo comercial, arquitectura v2 y ADRs actualizados (T-69). |
| [ ] | **11** | Sistema integrado | Arquitectura II | Núcleo y módulo comercial integrados y desplegados (T-61 a T-68). |
| [ ] | **12** | Evaluación de la arquitectura y documento final | Arquitectura II | Evaluación basada en escenarios (ATAM), contraste estimado vs. real de EC-05 y lecciones (T-90). |
| [ ] | **13** | Informe de evaluación de calidad | Modelos de Calidad | Evaluación conforme a ISO/IEC 25040 e ISO/IEC 25012 con resultados de pruebas de sistema y carga (T-90). |
| [ ] | **14** | Calidad del proceso y plan de mejora | Modelos de Calidad | Reflexión del proceso frente a ISO/IEC 330xx o CMMI y plan de mejora (T-90). |
| [ ] | **15** | Documento resumen tipo artículo | Ambas | Artículo académico con abstract, introducción, decisiones, figuras/tablas, conclusiones y referencias (T-90). |
| [ ] | **16** | Sustentación del proyecto | Ambas | Presentación final con demostración funcional en vivo (T-90). |