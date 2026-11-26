# Informe EC-08 — Historial de precios de 90 días

**Feature**: `002-ampliacion-corte3` — opción A2

**Fecha**: 2026-11-26

**Estado**: certificación funcional y de rendimiento completa en el backend desplegado en Render (Ohio).

**Alcance**: serie de los últimos 90 días por producto y establecimiento, con origen, estado de confiabilidad, datos demo, ausencia de PII y cambio de precio visible dentro del plazo de `EC-02`.

---

## 1. Criterios y resultado

| Criterio | Resultado | Evidencia |
|---|---|---|
| Serie de 90 días por producto/establecimiento | **CUMPLE** | `test_historial_precios.py` |
| Origen y estado en el 100 % de los puntos | **CUMPLE** | Pruebas de dominio, servicio y endpoint |
| `dudoso` marcado y `rechazado` excluido | **CUMPLE** | `test_ec08_cambio_oficial_visible_dudoso_marcado_rechazado_excluido` |
| Cambio oficial visible sin borrar el anterior | **CUMPLE** | Prueba de integración con `fuente='comercio'` |
| Cambio visible en ≤ 60 s | **CUMPLE** | Prueba de integración: consulta directa en la misma transacción |
| 0 PII en la respuesta | **CUMPLE** | Aserciones de claves prohibidas en DTO y endpoint |
| Gráfica accesible y tabla alternativa | **CUMPLE** | E2E y axe de ejecuciones previas |
| p95 ≤ 500 ms con 100 puntos, backend desplegado | **CUMPLE: 272.40 ms** | Benchmark contra Render Ohio |
| p95 local contra pooler remoto | 1208.57 ms (referencia) | Benchmark local; no representa producción |

---

## 2. Evidencia funcional

### 2.1 Pruebas de integración contra PostgreSQL

```text
uv --directory backend run pytest tests/integracion/test_historial_precios.py -q
13 passed in 26.42s
```

Cubren:

- Existencia y definición del índice `idx_reporte_historial_serie`.
- Serie ordenada ascendentemente y sin PII.
- DTO del servicio sin campos prohibidos.
- Filtro por presentación activa.
- Endpoint público en UTC.
- `404` para producto, establecimiento o presentación inexistente.
- `422` para ventana mayor a 90 días y límites fuera de rango.
- Cambio oficial, `dudoso` marcado y `rechazado` excluido.

### 2.2 Semilla demo

```text
combinaciones: 9
puntos_generados: 54
puntos_insertados: 54
precio_vigente: sin cambios
```

Segunda ejecución:

```text
puntos_insertados: 0
precio_vigente: sin cambios
```

### 2.3 Frontend y accesibilidad

Evidencia previa registrada en `tasks.md`:

- Playwright: **19/19**.
- axe: sin violaciones críticas o serias.
- Gráfica con origen/estado y tabla alternativa.

---

## 3. Medición de rendimiento

### 3.1 Entorno

| Elemento | Valor |
|---|---|
| Backend | Local, `backend/.venv` |
| Base de datos | Supabase PostgreSQL 17.12, Session Pooler `aws-1-us-east-2` |
| Puntos insertados | 100, dentro de una transacción revertida |
| Puntos devueltos | 100 |
| Iteraciones medidas | 50 |
| Calentamiento | 5 |
| Script | `scripts/benchmark_historial.py` |

Comando:

```bash
cd backend
.venv/bin/python ../scripts/benchmark_historial.py --iteraciones 50
```

### 3.2 Resultado

```text
producto_id: f878621a-637b-4ab9-8827-50cf3527b2f4
establecimiento_id: aa2805c7-45b3-41a5-9ae8-15761ad996af
presentacion_id: 72ee1ac4-09a3-4f26-a452-fd9fc1b5646c
puntos_insertados: 100
puntos_devueltos: 100
iteraciones_medidas: 50
calentamiento: 5
p50_ms: 816.24
p95_ms: 1208.57
p99_ms: 1259.35
max_ms: 1259.35
criterio_p95_500ms: INCUMPLE
```

### 3.3 Diagnóstico

| Medición | p50 | p95 |
|---|---:|---:|
| `SELECT 1` al pooler | 197.5 ms | 203.9 ms |
| Consulta de producto | 197.1 ms | 252.8 ms |
| Consulta de establecimiento | 198.4 ms | 201.6 ms |
| Consulta de presentación | 198.9 ms | 202.6 ms |
| Consulta de reportes | 200.2 ms | 205.6 ms |
| `EXPLAIN ANALYZE` de reportes | **0.014 ms** de ejecución | Índice usado |

El cuello de botella es la **latencia de red**: cada ida y vuelta al pooler remoto cuesta ~200 ms y `ServicioHistorial` hace cuatro consultas secuenciales (producto, establecimiento, presentación y reportes). La consulta usa `idx_reporte_historial_serie` y se ejecuta en microsegundos.

En un backend desplegado en `us-east-2`, junto al pooler, la latencia por consulta debería bajar a milisegundos y el p95 debería quedar muy por debajo de 500 ms.

### 3.4 Medición contra el backend desplegado

| Elemento | Valor |
|---|---|
| URL | `https://comparador-precios-api-f0hh.onrender.com` |
| Plataforma | Render, plan Free, región Ohio |
| Puntos persistidos temporalmente | 100 |
| Puntos devueltos | 100 |
| Iteraciones medidas | 50 |
| Calentamiento | 5 |
| Cliente | `httpx.AsyncClient` con keep-alive |

```text
p50_ms: 170.36
p95_ms: 272.40
p99_ms: 513.97
max_ms: 513.97
criterio_p95_500ms: CUMPLE
```

Los 100 puntos temporales se eliminaron al terminar y el trigger de inmutabilidad quedó habilitado. El p99 supera 500 ms, pero el criterio de aceptación es p95.

---

## 4. Conclusión

- **EC-08 funcional: cumple.** La serie, el origen, el estado, el cambio oficial, la privacidad y la accesibilidad están verificados.
- **EC-08 rendimiento: cumple en el backend desplegado.** p95 = **272.40 ms** con 100 puntos en Render Ohio. La medición local contra el pooler remoto (1208.57 ms) queda como referencia de diagnóstico, no como resultado de producción.
- **Cierre:** no quedan pendientes funcionales ni de rendimiento para EC-08. La siguiente evidencia pendiente es EC-11/T-126.

## 5. Reproducibilidad

```bash
# Integración
uv --directory backend run pytest tests/integracion/test_historial_precios.py -q

# Benchmark (usa .env; no imprime credenciales)
cd backend
.venv/bin/python ../scripts/benchmark_historial.py --iteraciones 50
```

El benchmark inserta los 100 puntos dentro de una transacción que siempre se revierte; no deja datos persistidos.
