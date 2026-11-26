# Escenarios de Calidad Refinados — Ampliación Corte 3 (A2 + B1)

**Plantilla**: 8.2 del Anexo 1 — formato de Bass, Clements y Kazman (2021).

**Opciones seleccionadas**:

- **A2** — Historial y tendencia de precios → `EC-08`.
- **B1** — Observabilidad con objetivos de nivel de servicio → `EC-11`.

**Fecha**: 2026-11-26.

**Estado**: EC-08 con evidencia completa; EC-11 con implementación y evidencia de código, pendiente de certificación real en `T-126`.

> Este documento formaliza los escenarios que ya estaban descritos como criterios en `spec.md`. No reemplaza la spec: la complementa con el formato exigido por el anexo.

---

## EC-08 — Historial de precios con origen y confiabilidad

| Parte | Descripción |
|---|---|
| **Fuente del estímulo** | Consumidor que consulta la ficha de un producto en la plataforma. |
| **Estímulo** | Solicita el historial de los últimos 90 días de un producto en un establecimiento cuyo precio cambió durante la semana. |
| **Artefacto** | Backend FastAPI (`GET /v1/productos/{id}/historial-precios`), repositorio `reporte_precio`, servicio de historial y componente de gráfica en la ficha del producto. |
| **Entorno** | Operación normal; datos reportados, oficiales o de semilla/demostración; ventana máxima de 90 días; sin datos personales. |
| **Respuesta** | Devuelve la serie ordenada cronológicamente. Cada punto incluye fecha, precio, precio por unidad base, origen (`usuario`, `comercio`, `semilla`), estado (`aceptado`, `dudoso`), presentación y marca `es_demo`. El cambio de precio aparece dentro del plazo de `EC-02`. La gráfica distingue origen y estado, y la tabla alternativa expone los mismos datos. |
| **Medida de la respuesta** | **100 %** de los puntos con origen y estado; cambio visible en **≤ 60 s** (`EC-02`); **0** campos prohibidos de datos personales; p95 de la consulta de 90 días con 100 puntos **≤ 500 ms** (criterio interno del plan); gráfica y tabla sin violaciones críticas o serias de WCAG 2.2 AA. |

### Trazabilidad EC-08

| Elemento | Referencia |
|---|---|
| Requisitos | `FR-A2-001` a `FR-A2-015`, `NFR-001`, `SC-A2-01` a `SC-A2-05` |
| Pruebas backend | `backend/tests/integracion/test_historial_precios.py` |
| Pruebas frontend | `frontend/tests/e2e/historial_precios.spec.ts` |
| Tarea | `T-119` |
| Estado | Integración **13/13**, E2E **19/19**, axe sin violaciones críticas. p95 con 100 puntos pendiente de medición explícita. |

---

## EC-11 — Detección de incumplimiento del SLO con trazas

| Parte | Descripción |
|---|---|
| **Fuente del estímulo** | Equipo de operación o prueba de carga automatizada (`k6`). |
| **Estímulo** | Se inyecta una latencia artificial de 3 s en el componente de comparación durante una prueba de carga. |
| **Artefacto** | API de comparación, instrumentación OpenTelemetry, colector OTLP, reglas de SLO/alerta, tablero de Grafana y trazas. |
| **Entorno** | Entorno de pruebas (`ENTORNO=pruebas`, `SIMULAR_LATENCIA_MS=3000`), colector/Grafana activo y tráfico de comparación sostenido. |
| **Respuesta** | El SLI de comparación cae por debajo de 0,99; la alerta `ComparadorSLOComparacionIncumplido` se dispara; la traza de una petición lenta identifica el componente responsable; el tablero muestra el SLI y el presupuesto de error consumido. |
| **Medida de la respuesta** | Alerta en **≤ 5 minutos**; traza con el componente responsable identificable sin revisar logs manualmente; **0** datos personales en trazas/logs; p95 de comparación sin latencia inyectada **≤ 2 s** y sin degradación por la instrumentación. |

### Trazabilidad EC-11

| Elemento | Referencia |
|---|---|
| Requisitos | `FR-B1-001` a `FR-B1-014`, `NFR-002`, `SC-B1-01` a `SC-B1-05` |
| Pruebas backend | `backend/tests/integracion/test_telemetria.py` |
| Carga | `infra/k6/ec11_latencia.js` |
| Tablero | `infra/observabilidad/grafana/dashboards/observabilidad-comparador.json` |
| Reglas | `infra/observabilidad/grafana/alertas/slo-comparador.yml` |
| Tarea | `T-126` |
| Estado | Implementación y pruebas de privacidad/degradación completas. Certificación real pendiente: requiere colector OTLP/Grafana, reglas cargadas y `k6`. |

---

## EC-04 — Escenario base del SLO (referencia)

`EC-04` pertenece al núcleo y no es una opción nueva del anexo, pero el SLO de B1 se define sobre él.

| Parte | Descripción |
|---|---|
| **Fuente del estímulo** | Usuarios concurrentes consultando comparaciones. |
| **Estímulo** | Carga de 200 a 500 usuarios concurrentes sobre catálogo, comparación, tiendas y reportes. |
| **Artefacto** | API FastAPI, caché L1/L2, PostgreSQL y Redis. |
| **Entorno** | Operación normal; `--workers 1` en la prueba local; caché activa. |
| **Respuesta** | La API responde sin errores y mantiene la latencia dentro del objetivo. |
| **Medida de la respuesta** | p95 de comparación **≤ 2 s**, tasa de error **< 1 %** y sin degradación por la instrumentación de B1. |

---

## Relación con el anexo

| Requisito del anexo | Dónde se evidencia |
|---|---|
| Escenarios refinados antes de implementar | Este documento + `spec.md` + `impacto.md` |
| A2: serie de 90 días, origen y confiabilidad | `EC-08` y pruebas de integración/E2E |
| A2: TDD de reglas | `backend/tests/unitarias/test_serie_precios.py` |
| B1: OTel, métricas, trazas y logs | `EC-11`, `telemetria.py`, tablero y runbook |
| B1: SLO, SLI y presupuesto | `EC-04` + `slo-comparador.yml` |
| B1: alerta y evidencia de funcionamiento | `EC-11`, pendiente `T-126` |
| Privacidad Ley 1581 | Pruebas de `test_historial_precios.py` y `test_telemetria.py` |

## Pendientes para cerrar la evidencia

1. Medir el p95 de la serie de 90 días con 100 puntos.
2. Ejecutar `T-126` con colector real: alerta, traza, tablero y 0 PII.
3. Incorporar estos escenarios a la matriz de trazabilidad y al documento de arquitectura v2.
