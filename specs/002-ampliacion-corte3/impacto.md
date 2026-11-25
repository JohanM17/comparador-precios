# Análisis de Impacto — Ampliación Corte 3 (A2 + B1)

**Feature**: `002-ampliacion-corte3`

**Fecha**: 2026-11-25

**Estado**: Borrador para revisión y aprobación — debe confirmarse en Git antes del primer commit de implementación.

**Alcance**: opción **A2 (Historial y tendencia de precios)** y opción **B1 (Observabilidad con SLO)** del Anexo 1 del corte 3.

> Este documento usa la plantilla 8.3 del anexo. Las horas son una estimación preliminar del equipo técnico; deben validarse en la reunión de planificación y contrastarse con las horas reales al cierre. El contraste exigido por el entregable 6 de Arquitectura II incluye **dos cambios**: el módulo comercial (`T-60` a `T-69`) y esta ampliación. La estimación del módulo comercial debe producirse en `T-60`; aún no existe en el repositorio.

---

## 1. Registro de análisis de impacto (plantilla 8.3)

| Componente | Tipo de cambio | Esfuerzo estimado (h) | Esfuerzo real (h) | Observaciones |
|---|---|---:|---:|---|
| **A2 — Dominio puro `serie_precios.py`** | Nuevo | 8 | — | Reglas de ventana, orden, origen, estado, demo y truncado; TDD con `pytest` y cobertura ≥ 95 %. |
| **A2 — Repositorio de precios** | Modificado | 6 | — | Consulta por producto/establecimiento/presentación y rango de 90 días; índice adicional si el plan lo confirma. |
| **A2 — Servicio y esquemas de historial** | Nuevo | 8 | — | DTOs, validación de parámetros, ventana máxima, límite y `truncado`; sin datos personales. |
| **A2 — Endpoint `GET /v1/productos/{id}/historial-precios`** | Nuevo | 4 | — | Contrato OpenAPI, códigos de error y pruebas de contrato. |
| **A2 — Migración aditiva** | Nuevo | 3 | — | Índice para la consulta de serie; numeración posterior a `0004_modulo_comercial.sql`. |
| **A2 — Componente de gráfica accesible** | Nuevo | 12 | — | Gráfica con origen/estado, leyenda, tabla alternativa, estados de carga/vacío/error y WCAG 2.2 AA. |
| **A2 — Integración en ficha de producto** | Modificado | 4 | — | Selector de establecimiento/presentación y carga del historial. |
| **A2 — Pruebas de integración y datos demo de 90 días** | Nuevo | 8 | — | Semilla/script con datos demo marcados `es_demo`; pruebas de ventana y cambio oficial. |
| **A2 — OpenAPI, cliente tipado y trazabilidad** | Modificado | 3 | — | Regenerar `docs/api/openapi.json` y `esquema.d.ts`; añadir `EC-08` a la matriz. |
| **B1 — Módulo de telemetría y configuración OTel** | Nuevo | 8 | — | SDK, recurso de servicio, exportador OTLP, variables de entorno, modo deshabilitado y degradación. |
| **B1 — Instrumentación de registro y comparación** | Modificado | 10 | — | Spans, métricas, atributos permitidos y correlación de logs; sin datos personales. |
| **B1 — Tablero como código** | Nuevo | 8 | — | Paneles de tasa, latencia, errores, caché, base de datos, SLO y presupuesto de error. |
| **B1 — SLO, alerta y simulacro EC-11** | Nuevo | 6 | — | Regla de alerta, notificación, inyección de latencia y evidencia del simulacro. |
| **B1 — Pruebas de privacidad y telemetría** | Nuevo | 5 | — | Exportador en memoria; escaneo de atributos prohibidos; fallo del exportador no bloquea. |
| **B1 — Runbook y despliegue** | Modificado | 5 | — | `docs/observabilidad.md`, variables en `.env.example`, secretos y procedimiento de diagnóstico/reversión. |
| **Transversal — ADRs, spec y análisis de impacto** | Nuevo | 6 | — | `ADR-0019`, `ADR-0020`, esta spec y este análisis; commit previo a la implementación. |
| **Transversal — Integración, demo y medición** | Nuevo | 6 | — | Integración con el módulo comercial, guion de demo y contraste estimado/real. |
| **Total** | — | **110** | — | Estimación preliminar; no incluye el módulo comercial. |

### 1.1 Desglose por opción

| Opción | Horas estimadas | Riesgo principal |
|---|---:|---|
| **A2 — Historial y tendencia** | 56 | Dependencia del historial de precio oficial y datos demo de 90 días. |
| **B1 — Observabilidad con SLO** | 42 | Cuota gratuita del backend de observabilidad y configuración de credenciales. |
| **Transversal** | 12 | Coordinación con el módulo comercial y evidencia del simulacro. |
| **Total** | **110** | — |

---

## 2. Componentes afectados y reutilización

### 2.1 A2 — Historial de precios

| Activo existente | Uso | Impacto |
|---|---|---|
| `backend/app/modulos/precios/repositorio.py` | Consulta de `reporte_precio` | Se añade una consulta de serie por producto/establecimiento/presentación y rango. |
| `backend/app/modulos/precios/api.py` | Router de precios | Se añade el endpoint de historial. |
| `backend/app/modulos/precios/esquemas.py` | DTOs Pydantic | Se añaden esquemas de punto y serie. |
| `backend/app/dominio/` | Lógica pura | Se añade `serie_precios.py` con TDD; no se modifica la lógica certificada de vigencia, sello, orden, anomalía ni riesgo. |
| `backend/app/modulos/precios/servicio_comparacion.py` | Comparación actual | No se modifica; el historial es una lectura separada. |
| `reporte_precio` | Fuente de verdad append-only | Se reutiliza; no se sobrescribe. Puede requerir índice adicional. |
| `precio_vigente` | Proyección actual | No se usa para la serie histórica; se usa para la comparación vigente. |
| `frontend/src/app/producto/[id]/page.tsx` | Ficha de producto | Se integra la gráfica y el selector. |
| `frontend/src/lib/api/clienteApi.ts` y `esquema.d.ts` | Cliente tipado | Se regeneran y amplían. |
| `docs/api/openapi.json` | Contrato | Se regenera y verifica en CI. |

**No se toca**: `dominio/anomalia.py`, `dominio/riesgo.py`, `dominio/sello.py`, `dominio/orden.py`, `dominio/vigencia.py` ni la lógica de comparación. Esto reduce el riesgo sobre `EC-03` y `EC-06`.

### 2.2 B1 — Observabilidad y SLO

| Activo existente | Uso | Impacto |
|---|---|---|
| `backend/app/main.py` | Factory `create_app()` | Se inicializa OTel y se instrumenta FastAPI; debe ser opcional y no bloquear. |
| `backend/app/compartido/logging_cfg.py` | Logs JSON | Se añade `trace_id`/`span_id` y se mantiene el filtrado de coordenadas. |
| `backend/app/modulos/precios/servicio.py` | Registro de reportes | Se añaden spans/atributos permitidos. |
| `backend/app/modulos/precios/servicio_comparacion.py` | Comparación | Se añaden spans/atributos de caché, base de datos y resultados. |
| `backend/app/compartido/parametros.py` | Parámetros | Sin cambios; el SLO no es un parámetro de negocio. |
| `infra/k6/ec04_carga.js` | Carga | Se reutiliza para el simulacro de `EC-11`; se añade un escenario o variable de latencia. |
| `.github/workflows/ci.yml` | CI | Se añade validación de tablero/alertas y pruebas de telemetría; no se requiere backend externo. |
| `docs/despliegue.md` | Despliegue | Se añaden variables OTLP y secretos. |
| `docs/observabilidad.md` | Nuevo | Runbook, SLO, alerta, simulacro y diagnóstico. |

**No se toca**: la lógica de negocio, la base de datos, la caché L1/L2 ni el contrato público de la API. La instrumentación es transversal y debe poder deshabilitarse.

---

## 3. Dependencias y riesgos

| Riesgo / dependencia | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El módulo comercial no conserva el historial del precio oficial | Media | Alto para A2 | `ADR-0019`: escribir cada cambio oficial en `reporte_precio` con `fuente='comercio'`; coordinar con `T-63`. |
| No hay datos de 90 días en la semilla | Alta | Medio | Script/semilla de datos demo con `es_demo=true`; no inventar datos reales. |
| La capa gratuita de observabilidad no alcanza | Media | Medio | Muestreo, retención corta y alternativa nativa del proveedor; `PA-05`. |
| La instrumentación añade latencia | Baja | Medio | Exportador por lotes, muestreo y prueba de no degradación de `EC-04`. |
| Se filtran datos personales en trazas/logs | Media | Alto (Ley 1581) | Lista de atributos prohibidos, prueba automatizada y revisión de spans. |
| La alerta no se dispara en el simulacro | Media | Alto para EC-11 | Simulacro temprano, regla de alerta versionada y evidencia reproducible. |
| La migración choca con `0004_modulo_comercial.sql` | Media | Bajo | Numeración aditiva posterior; no editar migraciones aplicadas. |
| El equipo no alcanza el mínimo por el módulo comercial | Media | Alto | Priorizar el mínimo de A2/B1; extensiones opcionales al final; registrar lo logrado y la causa. |
| La gráfica no cumple accesibilidad | Baja | Medio | Tabla alternativa, patrones además de color y auditoría axe. |

---

## 4. Plan de evidencias

### A2 — EC-08

- Prueba de integración con reportes en días 1, 30, 60 y 90; verificación de orden, origen y estado.
- Prueba de cambio oficial: insertar un precio `fuente='comercio'` y verificar que aparece en ≤ 60 s sin borrar el anterior.
- Prueba de `dudoso` marcado y `rechazado` excluido.
- Prueba de estado vacío y de datos demo con aviso.
- Prueba de ausencia de campos prohibidos en la respuesta.
- Captura de la gráfica y de la tabla alternativa; auditoría axe.
- Medición de p95 de la consulta de 90 días con 100 puntos.

### B1 — EC-11

- Tablero con paneles de tasa, latencia p50/p95/p99, errores, caché, base de datos, SLO y presupuesto de error.
- Simulacro: activar latencia controlada, ejecutar k6, verificar alerta en ≤ 5 minutos y traza con el span responsable.
- Prueba de atributos prohibidos en trazas y logs.
- Prueba de exportador caído: la API sigue respondiendo.
- Captura de la alerta y de la traza; enlace al runbook.
- Registro de la configuración de muestreo y retención.

---

## 5. Contraste estimado vs real

La plantilla 8.3 se completará al cierre con las horas reales. El contraste del entregable 6 de Arquitectura II debe presentar dos columnas o dos tablas:

1. **Módulo comercial** (`T-60` a `T-69`): estimado en `docs/calidad/ec05-estimado.md` (pendiente) vs real.
2. **Ampliación A2 + B1**: estimado en este documento vs real.

Además, se documentarán:

- Componentes nuevos, modificados y sin cambio.
- Grado de reutilización del núcleo.
- Puntos de sensibilidad y trade-offs.
- Riesgos materializados y decisiones tomadas.
- Conclusión sobre `EC-05`: qué se reutilizó y qué se modificó.

---

## 6. Decisiones que deben aprobarse antes de implementar

1. **A2 — Fuente del historial**: `reporte_precio` append-only como fuente única y precio oficial agregado con `fuente='comercio'` (`ADR-0019`).
2. **A2 — Precios no confiables**: mostrar `dudoso` con marca; excluir `rechazado` como precio válido (`ADR-0019`).
3. **B1 — Backend de observabilidad**: OpenTelemetry + OTLP a Grafana Cloud Free (o alternativa nativa) (`ADR-0020`).
4. **B1 — SLO**: SLI de comparación ≤ 2 s y sin 5xx; meta 99 % en 7 días; presupuesto 1 % (`ADR-0020`).
5. **B1 — Privacidad**: lista de atributos prohibidos y prueba automatizada (`ADR-0020`).
6. **Mapeo de entregables**: confirmar con la guía del curso el significado de «Entregable 5/6» (`PA-06`).

---

## 7. Estimación del módulo comercial (referencia)

El anexo exige el contraste de **dos cambios**. El módulo comercial tiene su propio plan (`T-60` a `T-69`) y su estimación debe producirse en `T-60` antes de `T-61`. Para esta ampliación se asume que el módulo comercial incluye, como mínimo:

- Migración `0004_modulo_comercial.sql`.
- Reclamo y verificación de comercios.
- Precios oficiales por lote y revalidación.
- Estrategia `OficialConContraste`.
- Promociones y cumplimiento de Ley 1480.
- Casos de disputa.
- Pestañas de comercio en el frontend.
- Pruebas de `EC-02` y `EC-06` con el módulo activo.

La estimación detallada y el contraste estimado/real se completarán en `T-60`/`T-69`. Este documento no reemplaza ese artefacto.
