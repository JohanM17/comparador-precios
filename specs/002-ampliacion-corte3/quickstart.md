# Quickstart — Ampliación Corte 3 (A2 + B1)

**Feature**: `002-ampliacion-corte3` | **Date**: 2026-11-25

Guía ejecutable para validar A2 (historial de precios) y B1 (observabilidad/SLO) de extremo a extremo.

## 1. Prerrequisitos

- Python 3.12 + `uv`.
- Node.js 20 + `npm`.
- Acceso al proyecto Supabase y a Upstash definidos en `.env`.
- Para B1: endpoint OTLP y credenciales de Grafana Cloud (o proveedor equivalente); confirmar `PA-05`.
- Para el simulacro: `k6` instalado.
- Migraciones `0001` a `0003` aplicadas; la ampliación requiere `0005_historial_precios.sql`, que no depende del módulo comercial (`0006_modulo_comercial.sql`) y puede aplicarse sin él.

## 2. Preparación

```bash
# Dependencias backend
uv --directory backend sync --dev

# Dependencias frontend
npm --prefix frontend install

# Migraciones (incluye la nueva 0005)
uv --directory backend run python ../scripts/migrar.py

# Semilla/datos demo con historia de 90 días
uv --directory backend run python ../scripts/semilla.py
```

## 3. A2 — Validación del historial (EC-08)

### 3.1 Pruebas TDD del dominio

```bash
uv --directory backend run pytest tests/unitarias/test_serie_precios.py -q
uv --directory backend run pytest tests/unitarias/test_serie_precios.py --cov=app.dominio.serie_precios --cov-report=term-missing
```

Esperado: todas las pruebas en verde y cobertura ≥ 95 %.

### 3.2 Pruebas de integración

```bash
uv --directory backend run pytest tests/integracion/test_historial_precios.py -q
```

Escenarios:

1. Serie con reportes en días 1, 30, 60 y 90: orden ascendente, origen y estado correctos.
2. Cambio oficial: insertar una fila `fuente='comercio'` y verificar que aparece en ≤ 60 s sin borrar la anterior.
3. `dudoso` marcado y `rechazado` excluido.
4. Ventana > 90 días: `422 VALIDACION`.
5. Sin datos: serie vacía, sin ceros.
6. Datos demo: `datos_de_demostracion = true` y aviso visible.
7. Respuesta sin `reportante_id`, alias, foto, IP, `huella_red`, `lat` o `lng`.
8. `truncado = true` cuando hay más puntos que el límite.

### 3.3 Validación manual del endpoint

```bash
curl "http://127.0.0.1:8000/v1/productos/<PRODUCTO_ID>/historial-precios?establecimiento_id=<ESTABLECIMIENTO_ID>&limite=200"
```

Verificar:

- `datos.puntos` ordenados por `observado_en`.
- Cada punto con `origen`, `estado`, `es_demo` y `precio_por_unidad`.
- `datos.datos_de_demostracion` coherente.
- Sin campos prohibidos.

### 3.4 Frontend

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend run dev
```

Abrir `/producto/<id>`, seleccionar establecimiento/presentación y verificar:

- Gráfica con puntos, leyenda de origen y estado.
- Tabla alternativa accesible.
- Estados de carga, vacío y error.
- Aviso de datos demo cuando corresponda.
- Sin depender solo del color.

### 3.5 E2E y accesibilidad

```bash
npx --prefix frontend playwright test -c frontend/playwright.config.ts tests/e2e/historial_precios.spec.ts
```

Esperado: flujo de historial y auditoría axe sin violaciones críticas o serias.

## 4. B1 — Validación de observabilidad y SLO (EC-11)

### 4.1 Configuración

Definir en el entorno de prueba:

```ini
OTEL_SDK_DISABLED=false
OTEL_SERVICE_NAME=comparador-precios-backend
OTEL_EXPORTER_OTLP_ENDPOINT=https://<endpoint-otlp>
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <credencial>
OTEL_TRACES_SAMPLER_ARG=0.2
SIMULAR_LATENCIA_MS=0
```

No commitear credenciales. En producción, `SIMULAR_LATENCIA_MS` debe ser `0`.

### 4.2 Pruebas de instrumentación y privacidad

```bash
uv --directory backend run pytest tests/integracion/test_telemetria.py -q
```

Esperado:

- Se crean spans para registro y comparación.
- Los atributos permitidos están presentes y los prohibidos ausentes.
- Un exportador caído no rompe la petición.
- `OTEL_SDK_DISABLED=true` deja la API operativa.

### 4.3 Tablero y SLO

1. Abrir el tablero de Grafana (`infra/observabilidad/grafana/dashboards/`).
2. Verificar paneles: tasa de peticiones, p50/p95/p99, errores, caché, base de datos, SLO y presupuesto de error.
3. Confirmar que el SLO muestra 99 % / 7 días y el presupuesto de error.

### 4.4 Simulacro EC-11

```bash
# Terminal 1: backend con OTLP configurado
uv --directory backend run uvicorn app.main:app --reload --port 8000

# Terminal 2: carga con latencia inyectada
SIMULAR_LATENCIA_MS=3000 k6 run infra/k6/ec04_carga.js
```

Verificar:

- La latencia supera el SLO.
- La alerta se dispara en ≤ 5 minutos.
- La traza más lenta identifica el span del componente con latencia.
- Guardar capturas de tablero, alerta y traza.
- Restablecer `SIMULAR_LATENCIA_MS=0`.

## 5. Verificación completa antes de cerrar

```bash
uv --directory backend run pytest --cov=app --cov-report=term-missing
uv --directory backend run ruff check .
uv --directory backend run ruff format --check .
uv --directory backend run mypy --strict app
uv --directory backend run lint-imports

npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
npx --prefix frontend playwright test -c frontend/playwright.config.ts

k6 run infra/k6/ec04_carga.js
```

Criterios:

- `EC-08`: 90 días, origen y estado en el 100 % de los puntos, cambio visible ≤ 60 s.
- `EC-11`: alerta ≤ 5 min y traza con componente responsable.
- `EC-04`: p95 ≤ 2 s y error < 1 % sin degradación por la instrumentación.
- 0 violaciones críticas o serias de accesibilidad.
- 0 datos personales en historial o telemetría.

## 6. Problemas comunes

| Síntoma | Causa probable | Acción |
|---|---|---|
| Serie vacía | No hay reportes en la ventana o el establecimiento no coincide | Verificar datos y filtros. |
| No aparece el precio oficial | El módulo comercial no escribe en `reporte_precio` | Revisar `T-63` y `ADR-0019`. |
| El endpoint devuelve 422 | Rango > 90 días o `limite` fuera de rango | Ajustar parámetros. |
| No hay trazas | `OTEL_SDK_DISABLED=true` o endpoint/credenciales incorrectos | Revisar variables y logs de exportación. |
| La alerta no se dispara | Regla mal configurada o ventana sin datos | Revisar la regla y el simulacro. |
| Se filtran datos personales | Atributo no permitido | Bloquear, añadir prueba y revisar spans. |
