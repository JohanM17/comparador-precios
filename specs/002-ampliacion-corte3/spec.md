# Feature Specification: Ampliación Corte 3 — Historial de Precios (A2) y Observabilidad con SLO (B1)

**Feature Branch**: `002-ampliacion-corte3`

**Created**: 2026-11-25

**Status**: Draft — pendiente de aprobación del equipo

**Input**: Anexo 1 del corte 3 (`docs/Anexo1_Cambio_Alcance_Corte3_Seminario_Nuclear.pdf`) y decisión del equipo de implementar la opción **A2 (Historial y tendencia de precios)** y la opción **B1 (Observabilidad con objetivos de nivel de servicio)**.

## Contexto y alcance

El núcleo `v1.0-nucleo` ya resuelve catálogo, reportes, comparación por unidad base, confianza, moderación, caché y cola offline. El corte 3 incorpora el módulo comercial (primer cambio de alcance) y, en paralelo, esta ampliación de dos semanas (segundo cambio). La ampliación debe reutilizar el núcleo, medir la evolución arquitectónica (`EC-05`) y dejar evidencia de operación.

Esta spec cubre únicamente:

- **A2**: serie histórica de precios de los últimos 90 días por producto y establecimiento, con origen y estado de confiabilidad.
- **B1**: instrumentación OpenTelemetry de los flujos de registro y comparación, tablero, SLO sobre `EC-04`, presupuesto de error y alerta.

No cubre A1, A3, A4, B2 ni B3. El módulo comercial se especifica y planifica por separado (`T-60` a `T-69`).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Consultar el historial de precios de 90 días (Priority: P1)

Como consumidor, quiero consultar cómo ha variado el precio de un producto en un establecimiento durante los últimos 90 días, viendo el origen y la confiabilidad de cada punto, para decidir si el precio actual es alto o bajo respecto a su historia.

**Why this priority**: Es la funcionalidad de producto de la ampliación. Aprovecha el historial inmutable que ya existe y añade contexto temporal a la comparación, sin alterar el orden neutral ni la lógica certificada de confianza.

**Independent Test**: Sembrar un producto con reportes aceptados, dudosos y de demostración distribuidos en 90 días; consultar el endpoint y la gráfica; verificar puntos, orden cronológico, origen, estado, ventana de 90 días, estado vacío y ausencia de datos personales.

**Acceptance Scenarios**:

1. **Given** un producto con reportes aceptados en los días 1, 30, 60 y 90 en un establecimiento, **When** el consumidor abre el historial, **Then** ve cuatro puntos ordenados cronológicamente, cada uno con fecha, precio por unidad base, origen (`usuario`, `comercio` o `semilla`) y estado (`aceptado` o `dudoso`).
2. **Given** un cambio de precio oficial registrado por el módulo comercial en el instante `T`, **When** el consumidor consulta el historial después del plazo de `EC-02` (≤ 60 s), **Then** aparece un nuevo punto con origen `comercio` y el punto oficial anterior permanece visible; no se sobrescribe.
3. **Given** un reporte en estado `dudoso`, **When** se muestra el historial, **Then** el punto aparece marcado como `dudoso` y nunca se presenta como `confiable`; un reporte `rechazado` no se muestra como precio histórico válido.
4. **Given** un producto sin reportes en los últimos 90 días, **When** el consumidor abre el historial, **Then** ve un estado vacío explicativo, sin ceros ni puntos inventados.
5. **Given** datos de demostración (`es_demo = true`), **When** se muestra el historial, **Then** se activa el aviso visible «Datos de demostración» y los puntos demo se distinguen.
6. **Given** un reporte con fecha anterior a 90 días, **When** se consulta la serie, **Then** queda excluido de la ventana y no se mezcla con los puntos vigentes.
7. **Given** un producto con varias presentaciones, **When** el consumidor consulta el historial, **Then** cada punto identifica su presentación y la gráfica permite distinguirlas o filtrar por una de ellas.

---

### User Story 2 — Comparar la tendencia entre dos establecimientos (Priority: P3 — extensión opcional)

Como consumidor, quiero comparar la tendencia del mismo producto en dos establecimientos en la misma gráfica, para decidir dónde ha evolucionado mejor el precio.

**Why this priority**: Es una extensión opcional del anexo. No compensate el mínimo de A2.

**Independent Test**: Consultar dos establecimientos con series solapadas y verificar dos series distinguibles por color, leyenda y tabla accesible.

**Acceptance Scenarios**:

1. **Given** dos establecimientos con datos en el mismo periodo, **When** el consumidor activa la comparación, **Then** la gráfica muestra dos series etiquetadas y una tabla alternativa con ambas.

---

### User Story 3 — Operar y diagnosticar con SLO (Priority: P1)

Como integrante del equipo, quiero un tablero con métricas, trazas y registros correlacionados de los flujos de registro y comparación, y una alerta cuando el SLO de `EC-04` se incumpla, para saber si cumplimos el objetivo y localizar la causa de una degradación sin revisar logs manualmente.

**Why this priority**: Es la opción de operación de la ampliación. Demuestra que la plataforma se puede observar y gobernar en producción, no solo que existe la herramienta.

**Independent Test**: Ejecutar una prueba de carga con latencia artificial en un componente; verificar que el tablero muestra latencia, errores y trazas correlacionadas, que la alerta se dispara en ≤ 5 minutos y que la traza identifica el componente responsable.

**Acceptance Scenarios**:

1. **Given** una prueba de carga normal sobre registro y comparación, **When** se consulta el tablero, **Then** se ven tasa de peticiones, latencia p50/p95/p99, tasa de error, aciertos de caché, latencia de base de datos y el panel de SLO/presupuesto de error.
2. **Given** una latencia artificial inyectada en un componente durante una prueba de carga, **When** el SLO se incumple, **Then** la alerta se dispara en ≤ 5 minutos y la traza muestra el span del componente responsable.
3. **Given** cualquier telemetría emitida, **When** se inspeccionan atributos, **Then** no aparecen `lat`, `lng`, `reportante_id`, alias, correo, IP, `huella_red`, `foto_prueba_path` ni cabeceras de autorización.
4. **Given** que el colector/exportador de telemetría no responde, **When** llega una petición, **Then** la API responde con normalidad y el fallo de exportación solo se registra; nunca bloquea ni devuelve error al usuario.
5. **Given** una ventana de evaluación, **When** se consulta el SLO, **Then** se muestran el SLI, la meta, el presupuesto de error consumido y el estado de la alerta.
6. **Given** un simulacro de incidente, **When** se ejecuta el procedimiento documentado, **Then** queda evidencia de la alerta, la traza y la acción de diagnóstico.

---

### Edge Cases

- **Sin historial**: el endpoint devuelve una serie vacía con metadatos, nunca `null` ni ceros.
- **Solo reportes dudosos**: se muestran marcados como `dudoso`; no se promueven a `confiable`.
- **Reportes rechazados**: no se presentan como precios históricos válidos; si se incluyen por trazabilidad, se separan y etiquetan como `rechazado`.
- **Cambio de precio oficial sin historial**: si el módulo comercial aún no escribe el cambio en el historial, el punto oficial no aparece; se registra como dependencia y no se inventa.
- **Ventana mayor a 90 días**: la API rechaza el rango con `422 VALIDACION` o lo acota explícitamente; la UI usa 90 días.
- **Múltiples reportes el mismo día**: se conservan los puntos con su hora; no se agregan silenciosamente sin regla documentada.
- **Zona horaria**: la API entrega UTC ISO 8601; la UI formatea `America/Bogota`.
- **Datos demo mezclados**: el aviso de demostración permanece visible y cada punto conserva `es_demo`.
- **Telemetría deshabilitada**: `OTEL_SDK_DISABLED=true` deja la aplicación operativa sin trazas.
- **Muestreo**: los errores se muestrean al 100 %; los éxitos pueden muestrearse; la configuración es explícita y documentada.
- **Alerta sin tráfico**: el SLO no se evalúa como incumplido por ausencia de datos; la regla distingue «sin datos» de «fallo».
- **Coste/exportador**: el exportador usa lotes y timeouts; si se agota la cuota, la aplicación sigue funcionando.

---

## Requirements *(mandatory)*

### Functional Requirements — A2 (historial de precios)

- **FR-A2-001**: El sistema **MUST** exponer `GET /v1/productos/{id}/historial-precios` con `establecimiento_id` obligatorio, `presentacion_id` opcional y ventana por defecto de los últimos 90 días.
- **FR-A2-002**: La respuesta **MUST** devolver los puntos ordenados ascendentemente por `observado_en`, con `observado_en` en ISO 8601 UTC, `precio_cop` entero y `precio_por_unidad` calculado sobre la unidad base visualizable (`kg`, `l`, `unidad`).
- **FR-A2-003**: Cada punto **MUST** incluir `id`, `observado_en`, `precio_cop`, `precio_por_unidad`, `origen` (`usuario`, `comercio`, `semilla`), `estado` (`aceptado`, `dudoso`), `es_demo` y la presentación asociada.
- **FR-A2-004**: La serie **MUST** incluir reportes `aceptado` y `dudoso`; los `rechazado` **MUST NOT** presentarse como precio histórico válido. La decisión y su justificación se registran en `ADR-0019`.
- **FR-A2-005**: El origen `comercio` **MUST** corresponder al precio oficial; `usuario` al precio reportado; `semilla` a la fuente pública/demostración. La UI **MUST** etiquetar cada origen sin ambigüedad.
- **FR-A2-006**: Todo cambio de precio oficial del módulo comercial **MUST** conservarse sin sobrescribir el valor anterior, mediante el registro append-only `reporte_precio` con `fuente = 'comercio'` o la alternativa aprobada en `ADR-0019`.
- **FR-A2-007**: La respuesta **MUST NOT** incluir `reportante_id`, alias, correo, IP, `huella_red`, `foto_prueba_path`, `lat` ni `lng`.
- **FR-A2-008**: La ventana **MUST** limitarse a 90 días; un rango mayor **MUST** rechazarse con `422 VALIDACION` o acotarse de forma explícita y documentada.
- **FR-A2-009**: La respuesta **MUST** incluir un límite de puntos (por defecto 200, máximo 500) y una marca `truncado` si hay más; la UI **MUST** informar cuando la serie esté truncada.
- **FR-A2-010**: La consulta **MUST** reflejar un nuevo reporte o cambio oficial dentro del plazo de `EC-02` (≤ 60 s); si se usa caché, su TTL y su invalidación **MUST** respetar ese límite.
- **FR-A2-011**: Las reglas de selección, orden, origen y estado de la serie **MUST** implementarse en un módulo de dominio puro y desarrollarse con TDD antes de la implementación, con cobertura ≥ 95 %.
- **FR-A2-012**: La gráfica **MUST** ser accesible (WCAG 2.2 AA), con leyenda, patrones/íconos además de color y una tabla alternativa con los mismos datos.
- **FR-A2-013**: La UI **MUST** tener estados de carga, vacío y error, y **MUST** mostrar el aviso de datos de demostración cuando corresponda.
- **FR-A2-014**: La consulta de 90 días **MUST** tener un objetivo interno de p95 ≤ 500 ms para 100 puntos y **MUST NOT** degradar el p95 de comparación de `EC-04`.
- **FR-A2-015**: El contrato OpenAPI y el cliente tipado del frontend **MUST** regenerarse y validarse en CI.

### Functional Requirements — B1 (observabilidad y SLO)

- **FR-B1-001**: El backend **MUST** instrumentar con OpenTelemetry los flujos de registro de reportes y de comparación de precios (trazas, métricas y registros).
- **FR-B1-002**: La exportación **MUST** usar OTLP configurable por variables de entorno; las credenciales **MUST** vivir fuera del repositorio y **MUST** existir un modo `OTEL_SDK_DISABLED=true`.
- **FR-B1-003**: Los registros estructurados **MUST** incluir `trace_id` y `span_id` para correlacionarse con las trazas.
- **FR-B1-004**: El equipo **MUST** disponer de un tablero como código con tasa de peticiones, latencia p50/p95/p99, tasa de error, aciertos de caché, latencia de base de datos, SLO y presupuesto de error.
- **FR-B1-005**: El sistema **MUST** definir un SLO formal sobre `EC-04`: SLI = proporción de peticiones de comparación con latencia ≤ 2 s y sin error 5xx; meta 99,0 % en ventana móvil de 7 días; presupuesto de error 1,0 %.
- **FR-B1-006**: El sistema **MUST** tener al menos una alerta asociada al incumplimiento del SLO, con notificación al equipo y evidencia de un simulacro.
- **FR-B1-007**: Las trazas **MUST** incluir spans de los componentes internos relevantes (API, servicio, caché, base de datos) y atributos como `cache_hit`, `db_ms`, `resultados_count`, `estado` y `fuente`; **MUST NOT** incluir datos personales.
- **FR-B1-008**: El sistema **MUST** permitir inyectar latencia controlada para el simulacro de `EC-11`, solo en entornos de prueba y con un interruptor explícito; **MUST NOT** estar activo en producción.
- **FR-B1-009**: La estrategia de muestreo **MUST** ser explícita: 100 % de errores y un porcentaje configurable de éxitos; el costo y la retención **MUST** documentarse.
- **FR-B1-010**: La telemetría **MUST NOT** registrar `lat`, `lng`, `reportante_id`, alias, correo, IP, `huella_red`, `foto_prueba_path` ni cabeceras de autorización; **MUST** existir una prueba automatizada que lo verifique.
- **FR-B1-011**: Un fallo del exportador o del colector **MUST NOT** afectar la disponibilidad ni la latencia de la API; el exportador **MUST** usar lotes, timeouts y degradación silenciosa.
- **FR-B1-012**: El equipo **MUST** documentar un runbook (`docs/observabilidad.md`) con arquitectura, variables, tablero, SLO, alerta, simulacro, diagnóstico y reversión.
- **FR-B1-013**: CI **MUST** validar la sintaxis del tablero y de las reglas de alerta y ejecutar las pruebas de instrumentación con un exportador en memoria.
- **FR-B1-014**: El simulacro de `EC-11` **MUST** dejar evidencia: captura del tablero, alerta disparada, traza con el componente responsable y resultados de la prueba de carga.

### Non-Functional Requirements

- **NFR-001 (EC-08)**: La serie de 90 días **MUST** indicar origen y estado de confiabilidad en el 100 % de los puntos, y un cambio **MUST** aparecer dentro del plazo de `EC-02`.
- **NFR-002 (EC-11)**: La violación del SLO **MUST** detectarse con una alerta en ≤ 5 minutos y el componente responsable **MUST** identificarse con trazas, sin revisión manual de logs.
- **NFR-003 (Privacidad, Ley 1581)**: Ni la API de historial ni la telemetría **MUST** exponer datos personales o coordenadas.
- **NFR-004 (Accesibilidad)**: La gráfica y el tablero **MUST** cumplir WCAG 2.2 AA; la información no puede depender solo del color.
- **NFR-005 (Rendimiento)**: El historial **MUST NOT** degradar `EC-04`; la instrumentación **MUST NOT** añadir una latencia que empuje el p95 de comparación por encima de 2 s.
- **NFR-006 (Costo cero)**: La solución **MUST** caber en la capa gratuita de Grafana Cloud/OTLP o en la observabilidad nativa del proveedor; el muestreo y la retención **MUST** proteger la cuota.
- **NFR-007 (Mantenibilidad)**: Las reglas de la serie **MUST** ser dominio puro con TDD; la configuración de observabilidad **MUST** estar externalizada y documentada.

### Key Entities

- **PuntoSeriePrecio**: observación histórica de precio (`id`, `observado_en`, `precio_cop`, `precio_por_unidad`, `origen`, `estado`, `es_demo`, `presentacion_id`).
- **SeriePrecios**: conjunto ordenado de puntos para un producto y establecimiento, con ventana, unidad visualizable y marca de truncado.
- **OrigenPrecio**: `usuario` (reportado), `comercio` (oficial) o `semilla` (pública/demostración).
- **EstadoConfiabilidad**: `aceptado` o `dudoso` en la serie; `rechazado` se excluye o se separa explícitamente.
- **Traza/Métrica/Registro**: telemetría correlacionada por `trace_id` y `span_id`.
- **SLI/SLO/PresupuestoError/Alerta**: definición operativa del objetivo de `EC-04` y su gobierno.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-A2-01 (EC-08)**: El 100 % de los puntos de la serie de 90 días muestra origen y estado de confiabilidad; un cambio de precio aparece en el historial dentro del plazo de `EC-02`.
- **SC-A2-02**: El 100 % de las pruebas de la regla de serie (ventana, orden, origen, estado, demo) pasa y la cobertura del módulo puro es ≥ 95 %.
- **SC-A2-03**: La respuesta de historial no contiene ningún campo prohibido de datos personales (verificación automatizada).
- **SC-A2-04**: La consulta de 90 días con 100 puntos tiene p95 ≤ 500 ms en el entorno de prueba y no degrada el p95 de comparación.
- **SC-A2-05**: La gráfica y su tabla alternativa pasan la auditoría axe/WCAG 2.2 AA sin violaciones críticas o serias.
- **SC-B1-01 (EC-11)**: Ante una latencia artificial, la alerta se dispara en ≤ 5 minutos y la traza identifica el componente responsable.
- **SC-B1-02**: El 100 % de las peticiones de registro y comparación genera telemetría (sujeta a muestreo de éxitos; errores al 100 %).
- **SC-B1-03**: El 0 % de los atributos de telemetría corresponde a datos personales o coordenadas (prueba automatizada).
- **SC-B1-04**: El tablero muestra SLI, meta, presupuesto de error y estado de la alerta; el simulacro deja evidencia reproducible.
- **SC-B1-05**: La instrumentación no eleva el p95 de comparación por encima de 2 s ni afecta la disponibilidad cuando el exportador falla.

---

## Decisiones de diseño propuestas

| Pregunta del anexo | Decisión propuesta | Evidencia |
|---|---|---|
| ¿Event Sourcing o solo inserción? | Usar `reporte_precio` append-only como fuente de verdad; no introducir Event Sourcing. | `ADR-0019` |
| ¿Se muestran los precios no confiables? | Mostrar `dudoso` con marca explícita; excluir `rechazado` como precio válido. | `ADR-0019` |
| ¿Cuánto historial se conserva? | Consultar 90 días; no borrar `reporte_precio`; el volumen es bajo. | `ADR-0019` |
| ¿Cómo se conserva el precio oficial? | El módulo comercial agrega cada cambio oficial a `reporte_precio` con `fuente='comercio'`. | `ADR-0019`, dependencia T-63 |
| ¿Qué SLI representa mejor al consumidor? | Proporción de comparaciones ≤ 2 s y sin 5xx; SLO 99 % en 7 días. | `ADR-0020` |
| ¿Qué muestreo y costo? | 100 % errores; éxitos configurable (20 % por defecto); retención según capa gratuita. | `ADR-0020` |
| ¿Qué no se registra? | Coordenadas, identidad, IP, correo, alias, huella, foto y cabeceras de autorización. | `ADR-0020`, `FR-B1-010` |

---

## Assumptions

- El módulo comercial se implementará en paralelo y escribirá el historial de precios oficiales según `ADR-0019`; si no lo hace, A2 se limita a precios reportados y de semilla.
- La serie se alimenta de `reporte_precio`; no se introduce un almacén de eventos separado.
- El volumen de 90 días es bajo (decenas o cientos de puntos por producto/establecimiento); no se requiere precomputar.
- La capa gratuita de Grafana Cloud (o un endpoint OTLP equivalente) está disponible; se confirma en `PA-05`.
- La gráfica se implementa en el frontend con una librería o SVG accesible; la decisión técnica se toma en `plan.md`.
- Los datos de demostración de 90 días se generan en la semilla o en un script de apoyo, marcados con `es_demo = true`.
- El equipo acepta que la ventana de evaluación del SLO sea de 7 días para el corte, documentando que en producción podría ampliarse.
- La numeración de la migración de la ampliación se coordina con `0004_modulo_comercial.sql`; no se edita una migración ya aplicada.
- El mapeo de «Entregable 5/6» del anexo con la numeración global de `PROYECTO.md` se confirma con la guía del curso (`PA-06`).

---

## Dependencies

- **Módulo comercial (T-60 a T-69)**: precios oficiales, promociones y disputas. A2 depende de que el cambio oficial se conserve.
- **`reporte_precio`**: tabla append-only existente; puede requerir un índice adicional para la consulta por producto/establecimiento/fecha.
- **OpenAPI y cliente tipado**: regeneración y verificación en CI.
- **Grafana Cloud / OTLP**: cuenta, endpoint, credenciales y cuota gratuita.
- **k6**: reutilizar `infra/k6/ec04_carga.js` y añadir el escenario de latencia para `EC-11`.
- **Documentación**: `docs/despliegue.md`, `docs/observabilidad.md`, `docs/calidad/trazabilidad.csv` y ADRs.

---

## Out of Scope

- A1 (canasta), A3 (validación comunitaria), A4 (offline), B2 (entrega continua) y B3 (integración con comercios/fuentes).
- Ingesta de SIPSA u otra fuente pública de precios; `semilla` se etiqueta como pública/demostración.
- Predicción, pronóstico o alertas de bajada de precio para consumidores.
- Comparación de más de dos establecimientos (la extensión opcional de A2 se evalúa después del mínimo).
- RUM del frontend y trazas de navegador (extensión posterior).
- Reemplazo de los logs y health checks existentes.

---

## Traceability

| Escenario | Historia | Requisitos | Verificación |
|---|---|---|---|
| **EC-08** | US-A2-1 | FR-A2-001 a FR-A2-015 | `backend/tests/integracion/test_historial_precios.py`, `frontend/tests/e2e/historial_precios.spec.ts` |
| **EC-11** | US-B1-1, US-B1-2 | FR-B1-001 a FR-B1-014 | `backend/tests/integracion/test_telemetria.py`, simulacro `EC-11` documentado |

Los escenarios refinados en la plantilla 8.2 del anexo están en [escenarios.md](./escenarios.md).
