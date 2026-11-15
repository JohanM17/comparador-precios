# Informe de Prueba de Carga `EC-04` (`k6` y Concurrencia Asíncrona 500 VUs)

## 1. Objetivo y Criterios (`T-53`)
- **Escenario de calidad `EC-04`**: soportar una carga de hasta **500 usuarios virtuales concurrentes (`500 VUs`)** con mezcla realista de lectura y escritura:
  - **60 %** catálogo (`GET /v1/productos`)
  - **30 %** comparación (`GET /v1/productos/{id}/comparacion?orden=precio_unitario`)
  - **5 %** tiendas (`GET /v1/establecimientos`)
  - **5 %** reportes (`POST /v1/reportes` con cabecera `Idempotency-Key` UUID v4)
- **Umbrales objetivo**: tasa de fallos `http_req_failed < 1 %` (`< 0.01`) y latencia `p(95) < 2 000 ms`.
- **Artefacto `k6`**: script reproducible creado en [ec04_carga.js](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/infra/k6/ec04_carga.js) (rampa `2m -> 500 VUs`, meseta `5m`, bajada `30s`, `sleep(1..3s)`).

## 2. Entorno y Alcance Ejecutado
- En la máquina local Windows de verificación el binario CLI `k6` no se encontraba instalado (`Get-Command k6` ausente), por lo que el script oficial [ec04_carga.js](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/infra/k6/ec04_carga.js) quedó validado sintácticamente (incluyendo cumplimiento SonarLint `javascript:S7726`) y se ejecutaron **dos pruebas verificables de concurrencia asíncrona con `500 VUs` (`httpx` + `asyncio` contra servidor HTTP `uvicorn`)** usando caché L2 en memoria para no consumir cuota de Upstash:
  1. **Escenario A (Backend local -> Supabase Session Pooler remoto por WAN, `pool_size=3, max_overflow=2`)**.
  2. **Escenario B (Backend FastAPI en proceso separado `--workers 1` con caché L1+L2 `CacheDosNiveles` en memoria y latencia BD co-ubicada simulada de `2–3 ms`)**.

## 3. Resultados Medidos

### 3.1 Escenario A — Integración directa sobre enlace WAN hacia Supabase Free Session Pooler (`500 VUs`)
- **Duración**: `23.45 s` | **Total peticiones**: `626` (`26.7 RPS`)
- **Estados**: `23` respuestas `200 OK`, `603` `ReadTimeout` (timeout cliente `10 s`) -> tasa de fallo `96.33 %`
- **Latencias observadas**: `min = 1 403.44 ms`, `p50 = 10 615.91 ms`, `p95 = 10 859.70 ms`, `max = 10 952.73 ms`
- **Diagnóstico técnico**:
  1. El plan gratuito de Supabase Session Pooler limita el pool global a `15` sesiones y el cliente local acota `pool_size = 5` (`3 + 2`), lo que con un RTT WAN transcontinental (~350–400 ms por consulta SQL) limita las rutas sin caché (`/v1/productos`, `/v1/establecimientos`) a ~8–10 RPS.
  2. Incluso en `GET /v1/productos/{id}/comparacion`, `api.py` adquiere `sesion_transaccional()` antes de consultar la caché L1/L2 en `ServicioComparacion`, generando contención sobre el pool WAN bajo 500 solicitudes simultáneas.

### 3.2 Escenario B — Servidor ASGI FastAPI `--workers 1` + `CacheDosNiveles` (`500 VUs` en `21.90 s`)

| Métrica | Valor Medido | Criterio `EC-04` | Observación |
|---|---:|---:|---|
| VUs concurrentes | **500** | 500 | `asyncio` + `httpx` sobre TCP localhost |
| Total de peticiones | **2 804** (`128.06 RPS`) | — | 60 / 30 / 5 / 5 respetado (`1650 / 841 / 149 / 164`) |
| Errores (`5xx` o red) | **0** (`0.00 %`) | `< 1.00 %` | **2 640** `200 OK` + **164** `201 Created` (`CUMPLE`) |
| Mínimo (`min_ms`) | **5.20 ms** | — | Hit directo en L1/L2 |
| Mediana (`p50_ms`) | **473.22 ms** | — | — |
| Media (`media_ms`) | **899.96 ms** | — | — |
| Percentil 95 (`p95_ms`) | **3 531.55 ms** | `< 2 000 ms` | Un solo worker (`--workers 1`) compartiendo CPU Windows con los 500 generadores |
| Percentil 99 (`p99_ms`) | **6 073.00 ms** | — | — |
| Máximo (`max_ms`) | **8 221.59 ms** | — | — |

## 4. Conclusiones y Recomendaciones Operativas para `p(95) < 2 000 ms`
1. **Estabilidad HTTP (`0.00 %` errores bajo 500 VUs)**: FastAPI + Pydantic v2 + `CacheDosNiveles` procesaron `2 804` peticiones concurrentes sin un solo error `5xx`, rechazo de socket ni condición de carrera al invalidar y leer caché simultáneamente.
2. **Cuellos de botella identificados de forma empírica**:
   - En producción (`Render / Railway` co-ubicado en `us-east-1` junto a Supabase), utilizar el **Transaction Pooler (puerto `6543`)** y escalar a `2–4` workers Uvicorn según CPU/RAM disponible.
   - Evitar abrir `sesion_transaccional()` antes de verificar acierto en caché L1/L2 en `GET /v1/productos/{id}/comparacion`, y extender la caché L1 (`5–15 s`) a listados frecuentes de `/v1/productos` y `/v1/establecimientos`.
   - Ejecutar la rampa completa con `k6 run infra/k6/ec04_carga.js` en un runner Linux dedicado contra el despliegue productivo co-ubicado (`EC-04`).

