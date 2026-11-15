# Informe de Certificación `EC-02` — Actualidad del Precio en Comparación (`<= 60 s`)

## 1. Objetivo y Criterio de Aceptación (`T-54`)
- **Escenario de calidad `EC-02`**: tras aceptar un nuevo reporte de precio o resolver un caso en moderación (`descartar` reporte dudoso para incorporarlo al precio vigente), la caché de comparación debe invalidarse y reflejar el nuevo precio en la vista pública de comparación (`GET /v1/productos/{id}/comparacion`) en **<= 60 segundos** en el **100 %** de las repeticiones.
- **Umbral objetivo**: `max_ms <= 60 000 ms` y `100 / 100` repeticiones exitosas.

## 2. Diseño del Experimento Automatizado
- **Archivo ejecutable**: [test_ec02_actualidad.py](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/backend/tests/integracion/test_ec02_actualidad.py) con helpers en [ayudantes_ec02.py](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/backend/tests/integracion/ayudantes_ec02.py).
- **Cobertura de rutas de actualización (`100` pares independientes)**:
  - **Repeticiones 1–50 (`POST /v1/reportes`)**: el sistema parte con un precio vigente en caché L1/L2 (`5000 COP`), recibe un reporte aceptado (`4800 COP`), recalcula `precio_vigente`, invalida las cachés L1 (memoria local TTL `60 s`) y L2 (`RedisMemoriaEC02` en memoria para no consumir cuota de Upstash) y consulta `GET /v1/productos/{id}/comparacion` hasta observar la transición exacta `5000 -> 4800`.
  - **Repeticiones 51–100 (`POST /v1/moderacion/casos/{id}/resolver`)**: parte con `5000 COP` cacheado y un reporte en estado `dudoso` (`4700 COP`), ejecuta la decisión de moderación `descartar`, promueve el reporte a `aceptado`, recalcula `precio_vigente`, invalida caché L1/L2 y verifica la transición `5000 -> 4700`.
- **Base de datos**: PostgreSQL en Supabase (`Session Pooler IPv4`, sin mocks de SQL).

## 3. Resultados Observados (`100 / 100` Repeticiones)

| Métrica | Valor Medido | Umbral `EC-02` | Estado |
|---|---:|---:|---|
| Repeticiones ejecutadas | **100** | 100 | CUMPLE |
| Cumplimiento `<= 60 s` | **100.0 %** | 100 % | CUMPLE |
| Mínimo (`min_ms`) | **3 802.71 ms** (3.80 s) | `<= 60 000 ms` | CUMPLE |
| Media (`media_ms`) | **5 103.31 ms** (5.10 s) | `<= 60 000 ms` | CUMPLE |
| Percentil 95 (`p95_ms`) | **6 536.82 ms** (6.54 s) | `<= 60 000 ms` | CUMPLE |
| Percentil 99 (`p99_ms`) | **6 709.91 ms** (6.71 s) | `<= 60 000 ms` | CUMPLE |
| Máximo (`max_ms`) | **6 941.85 ms** (6.94 s) | `<= 60 000 ms` | CUMPLE |

## 4. Conclusión
- La invalidación síncrona por producto (`CacheDosNiveles.invalidar_producto`) elimina tanto la caché L1 en proceso como las entradas de comparación L2 inmediatamente después del recálculo en `SoloUsuarios.recalcular_par`, manteniendo un margen superior a **53 segundos** por debajo del límite máximo permitido de `60 s`, incluso contemplando la latencia de red hacia el Pooler remoto de Supabase.

