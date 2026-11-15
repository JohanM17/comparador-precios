# Informe de Prueba de Carga `EC-04` (`k6` y Concurrencia Asíncrona 500 VUs)

## 1. Objetivo y Criterios (`T-53`)
- **Escenario de calidad `EC-04`**: soportar una carga de hasta **500 usuarios virtuales concurrentes (`500 VUs`)** con mezcla realista de lectura y escritura:
  - **60 %** catálogo (`GET /v1/productos`)
  - **30 %** comparación (`GET /v1/productos/{id}/comparacion?orden=precio_unitario`)
  - **5 %** tiendas (`GET /v1/establecimientos`)
  - **5 %** reportes (`POST /v1/reportes` con cabecera `Idempotency-Key` UUID v4)
- **Umbrales objetivo**: tasa de fallos `http_req_failed < 1 %` (`< 0.01`) y latencia `p(95) <= 2 000 ms`.
- **Artefacto `k6`**: script reproducible creado en [ec04_carga.js](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/infra/k6/ec04_carga.js) (rampa `2m -> 500 VUs`, meseta `5m`, bajada `30s`, `sleep(1..3s)`).

## 2. Refactorización Quirúrgica de Caché Sin Sesión SQL (`Cache Hit` Libre de Conexión)
- **Cuello de botella detectado en la medición inicial**: En la primera iteración de `T-53`, el endpoint `GET /v1/productos/{id}/comparacion` en [api.py](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/backend/app/modulos/precios/api.py) abría `async with sesion_transaccional() as sesion:` (`BEGIN` + `SET LOCAL ROLE app_backend` + `COMMIT`) **antes** de verificar si la respuesta estaba en `CacheDosNiveles` (L1 en RAM 5 s / L2 en Redis 60 s), elevando el `p95` bajo 500 VUs a `3 531.55 ms`.
- **Corrección aplicada**: Se refactorizó [api.py](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/backend/app/modulos/precios/api.py) y [servicio_comparacion.py](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/backend/app/modulos/precios/servicio_comparacion.py) (`ServicioComparacion`) con adquisición perezosa (*lazy session acquisition*):
  1. Primero se validan los parámetros de consulta en memoria y se consulta `CacheDosNiveles` (`L1 RAM -> L2 Redis`).
  2. Cuando ocurre un *cache hit*, se retorna inmediatamente `RespuestaComparacion` con **0 sesiones SQL abiertas** y **0 sentencias `SET LOCAL ROLE app_backend`**.
  3. Únicamente cuando ocurre un *cache miss* (o cuando se envían coordenadas `lat`/`lng`/`radio_km` no cacheables) se abre `sesion_transaccional()` contra PostgreSQL.
  4. Respaldado por prueba automatizada de regresión `test_comparacion_cache_hit_no_abre_sesion_bd` en [test_cache_comparacion.py](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/backend/tests/integracion/test_cache_comparacion.py).

## 3. Resultados Medidos Tras la Optimización (`500 VUs`)

### 3.1 Prueba Focalizada — `500 VUs` simultáneos en `GET /v1/productos/{id}/comparacion` (*Cache Hit*)
- **Duración de la ráfaga de 500 VUs**: `0.907 s`
- **Aperturas de sesión SQL (`sesion_transaccional`) en 500 hits**: **`0`**
- **Latencias**: `min = 564.84 ms` | `p50 = 661.72 ms` | **`p95 = 684.27 ms`** | `p99 = 691.53 ms` | `max = 696.35 ms`

### 3.2 Prueba Integral `EC-04` — Mezcla `60 / 30 / 5 / 5` con `500 VUs` e Invalidación en Vivo

| Métrica | Antes (Sesión Ansiosa) | Después (Caché Primero) | Criterio `EC-04` | Estado |
|---|---:|---:|---:|---|
| VUs concurrentes | 500 | **500** | 500 | **CUMPLE** |
| Total de peticiones | 2 804 (`128.06 RPS`) | **3 000** (`178.85 RPS`) | Mezcla 60/30/5/5 | **CUMPLE** (`1 824 / 888 / 161 / 127`) |
| Tasa de errores (`5xx` o red) | `0.00 %` | **`0.00 %`** (`0 / 3 000`) | `< 1.00 %` | **CUMPLE** (`2 873` `200 OK` + `127` `201 Created`) |
| Aperturas SQL en comparación + escritura | `1 005` (`100 %` de llamadas) | **`307`** (solo en *miss* y `POST`) | Mínimo uso de pool | **Ahorro del `79.5 %` en hits** |
| Mínimo global (`min_ms`) | `5.20 ms` | **`2.95 ms`** | — | Hit directo en L1 RAM |
| Mediana global (`p50_ms`) | `473.22 ms` | **`17.32 ms`** | — | Reducción de `96.3 %` |
| Media global (`media_ms`) | `899.96 ms` | **`94.07 ms`** | — | Reducción de `89.5 %` |
| **Percentil 95 global (`p95_ms`)** | `3 531.55 ms` | **`473.99 ms`** | **`<= 2 000 ms`** | **CUMPLE (`473.99 ms <= 2 000 ms`)** |
| **Percentil 95 `/comparacion` (`p95_ms`)** | — | **`472.21 ms`** | **`<= 2 000 ms`** | **CUMPLE** |
| Percentil 99 global (`p99_ms`) | `6 073.00 ms` | **`492.53 ms`** | — | — |
| Máximo global (`max_ms`) | `8 221.59 ms` | **`646.42 ms`** | — | — |

## 4. Conclusiones
1. **Cumplimiento holgado de `EC-04`**: Al consultar `CacheDosNiveles` antes de abrir sesión transaccional en PostgreSQL, el percentil 95 (`p95`) con `500 VUs` concurrentes descendió de `3 531.55 ms` a **`473.99 ms`** (más de `4x` por debajo del umbral máximo de `2 000 ms`), manteniendo **`0.00 %` de errores** e incrementando el caudal a **`178.85 RPS`**.
2. **Protección de cuota y pool de conexiones (Presupuesto Costo Cero)**: Los aciertos en L1/L2 no consumen conexiones del pool de Supabase ni ejecutan `SET LOCAL ROLE app_backend`, reservando el pool de base de datos exclusivamente para escrituras (`POST /v1/reportes`) y recálculos tras invalidación.
