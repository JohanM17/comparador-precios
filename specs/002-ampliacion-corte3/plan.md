# Implementation Plan: Ampliación Corte 3 — Historial de Precios (A2) y Observabilidad con SLO (B1)

**Branch**: `002-ampliacion-corte3` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)

**Input**: Especificación aprobada `specs/002-ampliacion-corte3/spec.md`, Anexo 1 del corte 3 y ADRs `0019`/`0020`.

## Summary

Implementar la ampliación del corte 3 sobre el núcleo `v1.0-nucleo`:

- **A2 — Historial y tendencia de precios:** endpoint público de serie de 90 días por producto/establecimiento, construido sobre el registro append-only `reporte_precio`; incluye origen (`usuario`, `comercio`, `semilla`), estado de confiabilidad (`aceptado`, `dudoso`), datos demo y una gráfica accesible con tabla alternativa. No se modifica la lógica certificada de comparación, vigencia, sello, orden, anomalía ni riesgo.
- **B1 — Observabilidad con SLO:** instrumentación OpenTelemetry de los flujos de registro y comparación, exportación OTLP a Grafana Cloud Free (o endpoint nativo equivalente), tablero como código, SLO de `EC-04` (99 % en 7 días, presupuesto de error 1 %), alerta y simulacro de latencia para `EC-11`.

El enfoque reutiliza la base de datos y la caché existentes; no introduce un almacén de eventos ni un servicio de grafos. La única migración es un índice aditivo para la consulta de serie. La observabilidad es transversal y desactivable; un fallo del exportador no afecta la API.

## Technical Context

**Language/Version**: Python 3.12 (backend, `uv`) y TypeScript 5.6 + Next.js 14 (frontend).

**Primary Dependencies**:
- *Backend*: FastAPI, Pydantic v2 (`extra='forbid'`), SQLAlchemy 2 asíncrono, `asyncpg`, `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-asyncpg`, `opentelemetry-instrumentation-httpx`.
- *Frontend*: Next.js 14, React 18, Tailwind CSS, `recharts` (carga dinámica, solo en la ficha de producto) y tabla HTML accesible como alternativa.
- *Testing*: `pytest`, `pytest-asyncio`, `hypothesis`, `schemathesis`, Playwright + `axe-core`, k6, exportador OTel en memoria.

**Storage**:
- PostgreSQL 16 + PostGIS en Supabase; se reutilizan `reporte_precio` (append-only) y `precio_vigente` (proyección).
- Migración aditiva `0005_historial_precios.sql` con índice para la serie; no se crean tablas nuevas. Se aplicó antes que la del módulo comercial, que tomó `0006_modulo_comercial.sql`; la migración de Fase 2 (`supervisor_ia`) pasará a `0007` cuando se implemente.
- Telemetría: backend externo OTLP (Grafana Cloud Free o equivalente); no se persiste telemetría en PostgreSQL.

**Testing**:
- Dominio puro de la serie con TDD y cobertura ≥ 95 %.
- Integración de historial, cambio oficial, estados, demo, ausencia de PII y truncado.
- Contrato OpenAPI del endpoint de historial.
- Frontend: unitarias/componente, E2E Playwright, axe WCAG 2.2 AA.
- Observabilidad: exportador en memoria, atributos prohibidos, exportador caído, simulacro EC-11 con k6.

**Target Platform**:
- Backend en Railway/Render (contenedor) y frontend en Vercel.
- Observabilidad en Grafana Cloud Free vía OTLP/HTTP; alternativa: endpoint OTLP nativo del proveedor.

**Project Type**: Monolito modular con frontend Next.js y backend FastAPI en el mismo repositorio.

**Performance Goals**:
- Historial: p95 ≤ 500 ms para 90 días y 100 puntos; no degradar el p95 de comparación de `EC-04` (≤ 2 s).
- `EC-11`: alerta en ≤ 5 minutos y traza con el componente responsable.
- Instrumentación: sin impacto perceptible en disponibilidad ni latencia; exportador por lotes.

**Constraints**:
- Ley 1581: sin `lat`/`lng`, identidad, IP, correo, alias, `huella_red`, foto ni cabeceras de autorización en historial o telemetría.
- Costo cero: Grafana Cloud Free o equivalente; muestreo y retención controlados.
- Sin Docker local; sin nuevos servicios obligatorios para el desarrollo.
- Sin cambios en la lógica certificada de `EC-03` ni `EC-06`.
- Dinero entero en COP; `Decimal` para cantidades; fechas UTC ISO 8601.
- Migraciones solo hacia adelante; no editar migraciones aplicadas.

**Scale/Scope**:
- Catálogo actual (~150 productos, ~30 establecimientos); series de 90 días con decenas o cientos de puntos por producto/establecimiento.
- Dos flujos instrumentados: `POST /v1/reportes` y `GET /v1/productos/{id}/comparacion`.
- Un tablero, un SLO, una alerta y un simulacro.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principio I (Mobile-first, registro ≤ 15 s, cola offline e idempotencia - EC-01):** A2 no altera el flujo de registro ni la cola offline; la gráfica es responsive y accesible. B1 no interviene en el flujo de captura. Cumple.
- [x] **Principio II (Privacidad y Ley 1581):** el historial excluye `reportante_id`, alias, foto, IP y coordenadas; la telemetría usa lista de atributos prohibidos y prueba automatizada. Cumple.
- [x] **Principio III (Neutralidad comercial - EC-06):** el historial es informativo y no altera el orden de comparación; el origen oficial se muestra etiquetado y las promociones no entran en la serie. Cumple.
- [x] **Principio IV (Dominio puro con TDD):** las reglas de la serie viven en `backend/app/dominio/serie_precios.py`, se escriben con prueba primero, cobertura ≥ 95 % y `mypy --strict`. Cumple.
- [x] **Principio V (Cero constantes mágicas, sin Docker local y costo cero):** no se añaden umbrales de negocio cableados; el SLO y el muestreo son configuración operativa externa; Grafana Cloud Free; el desarrollo local no requiere Docker. Cumple.
- [x] **Separación de responsabilidades:** FastAPI calcula la serie y la expone; Next.js solo renderiza la respuesta tipada. Cumple.
- [x] **Manejo de tiempo, moneda y medidas:** fechas UTC ISO 8601, precios enteros COP, `Decimal` para cantidades y precios por unidad. Cumple.
- [x] **Seguridad y privilegios mínimos:** Pydantic `extra='forbid'`, consultas parametrizadas, RLS sin cambios, sin secretos en el repositorio. Cumple.
- [x] **Convenciones de nomenclatura e idioma:** identificadores `snake_case` en español sin tildes; comentarios y UI en `es-CO`. Cumple.
- [x] **Flujo SDD:** spec aprobada, plan y tareas antes de implementar; ADRs `0019`/`0020`; artefactos confirmados en Git antes del primer commit de código. Cumple.

**Post-design re-check:** la solución no introduce nuevas tablas, no modifica el dominio certificado y no añade un almacén de grafos; los riesgos se limitan a la dependencia del historial oficial del módulo comercial y a la cuota de observabilidad. Cumple sin violaciones.

## Project Structure

### Documentation (this feature)

```text
specs/002-ampliacion-corte3/
├── plan.md              # Este plan
├── spec.md              # Especificación aprobada
├── impacto.md           # Análisis de impacto (plantilla 8.3)
├── research.md          # Fase 0: decisiones y alternativas
├── data-model.md        # Fase 1: entidades, DTOs, consulta e índice
├── quickstart.md        # Fase 1: validación ejecutable
├── contracts/
│   └── api-historial.md # Contrato del endpoint y variables OTLP
├── checklists/
│   └── requirements.md  # Calidad de la especificación
└── tasks.md             # Fase 2: tareas (siguiente paso)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── dominio/
│   │   └── serie_precios.py              # NUEVO: reglas puras de la serie (TDD)
│   ├── compartido/
│   │   ├── telemetria.py                # NUEVO: OTel, sanitización, degradación
│   │   └── logging_cfg.py               # MOD: trace_id/span_id
│   ├── modulos/precios/
│   │   ├── api.py                       # MOD: endpoint de historial
│   │   ├── esquemas.py                  # MOD: DTOs de serie
│   │   ├── repositorio.py               # MOD: consulta de 90 días
│   │   ├── servicio_historial.py        # NUEVO: orquestación de la serie
│   │   ├── servicio.py                  # MOD: span de registro
│   │   └── servicio_comparacion.py      # MOD: span de comparación
│   └── main.py                          # MOD: inicialización OTel
├── tests/
│   ├── unitarias/test_serie_precios.py  # NUEVO: TDD del dominio
│   ├── integracion/test_historial_precios.py  # NUEVO: EC-08
│   └── integracion/test_telemetria.py   # NUEVO: EC-11/privacidad
supabase/migrations/
└── 0005_historial_precios.sql           # NUEVO: índice aditivo
frontend/
├── src/
│   ├── app/producto/[id]/page.tsx       # MOD: integra la gráfica
│   ├── components/GraficaHistorialPrecios.tsx  # NUEVO
│   └── lib/api/clienteApi.ts            # MOD: llamada al historial
└── tests/e2e/historial_precios.spec.ts  # NUEVO: E2E + axe
infra/observabilidad/
├── grafana/dashboards/                  # NUEVO: tablero como código
└── grafana/alertas/                     # NUEVO: reglas de alerta
docs/
├── observabilidad.md                    # NUEVO: runbook
└── despliegue.md                        # MOD: variables OTLP
```

**Structure Decision**: Se mantiene el monolito modular existente. A2 se implementa dentro del módulo `precios` y del dominio puro; B1 se implementa como infraestructura transversal en `compartido/telemetria.py` y archivos de observabilidad versionados. No se crean módulos nuevos ni tablas nuevas.

## Phase 0: Research

Ver [research.md](./research.md). Decisiones principales:

- Fuente del historial: `reporte_precio` append-only, sin Event Sourcing (`ADR-0019`).
- Precio oficial: cada cambio se agrega a `reporte_precio` con `fuente='comercio'`; se coordina con `T-63`.
- Estados: se muestran `aceptado` y `dudoso`; `rechazado` se excluye como precio válido.
- Gráfica: `recharts` con carga dinámica y tabla HTML alternativa; auditoría axe.
- Observabilidad: OpenTelemetry + OTLP/HTTP a Grafana Cloud Free; muestreo 100 % errores / 20 % éxitos (`ADR-0020`).
- SLO: SLI de comparación ≤ 2 s y sin 5xx; 99 % en 7 días; presupuesto 1 %.
- Migración: `0005_historial_precios.sql`; la migración de Fase 2 pasa a `0006`.

## Phase 1: Design & Contracts

- [data-model.md](./data-model.md): entidades, DTOs, consulta SQL, índice, atributos de telemetría y SLO.
- [contracts/api-historial.md](./contracts/api-historial.md): contrato del endpoint y variables de observabilidad.
- [escenarios.md](./escenarios.md): escenarios EC-08 y EC-11 refinados en la plantilla 8.2 del anexo.
- [quickstart.md](./quickstart.md): escenarios ejecutables para EC-08 y EC-11.

## Implementation Strategy

### Orden recomendado

1. **Fundaciones (T-100 a T-103):** dependencias, variables, migración, esqueleto de telemetría.
2. **A2 (T-110 a T-119):** TDD del dominio → repositorio → servicio → API → frontend → datos demo → EC-08.
3. **B1 (T-120 a T-129):** instrumentación → tablero → SLO/alerta → simulacro → privacidad → runbook → EC-11.
4. **Cierre (T-130 a T-135):** trazabilidad, horas reales, verificación completa y demo.

A2 y B1 son independientes y pueden ejecutarse en paralelo por dos parejas. A2 tiene una dependencia externa: el módulo comercial debe conservar el historial del precio oficial (`T-63`). B1 tiene una dependencia operativa: la cuenta/endpoint OTLP (`PA-05`).

### MVP

- **MVP A2:** endpoint + dominio + gráfica + datos demo + EC-08.
- **MVP B1:** instrumentación + tablero + SLO + alerta + simulacro + EC-11.
- Las extensiones opcionales (comparar dos establecimientos, segundo SLO de EC-02) quedan al final y no compensan mínimos.

## Testing and Verification Commands

```bash
# Backend
uv --directory backend run pytest tests/unitarias/test_serie_precios.py -q
uv --directory backend run pytest tests/integracion/test_historial_precios.py -q
uv --directory backend run pytest tests/integracion/test_telemetria.py -q
uv --directory backend run pytest --cov=app --cov-report=term-missing
uv --directory backend run ruff check .
uv --directory backend run ruff format --check .
uv --directory backend run mypy --strict app
uv --directory backend run lint-imports

# Frontend
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
npx --prefix frontend playwright test -c frontend/playwright.config.ts tests/e2e/historial_precios.spec.ts

# Carga y simulacro EC-11
k6 run infra/k6/ec04_carga.js
# Con latencia inyectada y OTLP configurado, verificar alerta y traza.
```

## Risks and Mitigations

| Riesgo | Mitigación |
|---|---|
| El módulo comercial no conserva el historial oficial | `ADR-0019`; coordinar `T-63`; si no se implementa, A2 se limita a reportado/semilla y se documenta. |
| Cuota de Grafana Cloud insuficiente | Muestreo, retención corta y alternativa OTLP nativa (`PA-05`). |
| Fuga de PII en telemetría | Lista de prohibidos, prueba automatizada y revisión de atributos. |
| Degradación de EC-04 por instrumentación | Exportador por lotes, muestreo y prueba de no degradación. |
| Datos de 90 días insuficientes | Semilla/script demo con `es_demo=true`; no inventar datos reales. |
| Migración choca con 0004/0006 | Numeración aditiva y coordinación con el plan comercial/AI. |

## Complexity Tracking

> **Violaciones a la Constitución**: Cero. No se requieren excepciones.
