# Quickstart & Validation Guide: Núcleo del Comparador de Precios (001-nucleo-comparador)

**Branch**: `001-nucleo-comparador` | **Feature**: Núcleo del Comparador | **Date**: 2026-11-02

Esta guía describe el procedimiento reproducible para configurar el entorno local sin Docker, aplicar la persistencia inicial y ejecutar los 6 escenarios de prueba de extremo a extremo que validan la entrega del Núcleo.

---

## 1. Prerrequisitos del Sistema

1. **Python 3.12** instalado y accesible en PATH.
2. **`uv`** (gestor ultra-rápido de paquetes para Python): instalar vía `pip install uv` o `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`.
3. **Node.js 20+** y `npm`.
4. **Proyecto en Supabase ($0)**: Credenciales de base de datos (PostgreSQL), claves `anon` y `service_role`, y bucket privado `pruebas`.
5. **Base de datos en Upstash Redis ($0)**: URI de conexión con TLS (`rediss://default:...`).

---

## 2. Configuración del Entorno Local (Sin Docker)

### Paso 2.1 — Configurar variables de entorno
Copiar `.env.example` como `.env` en la raíz del repositorio y completar las credenciales reales:
```bash
cp .env.example .env
```
Asegurar que `DATABASE_URL`, `MIGRATIONS_DATABASE_URL` y `REDIS_URL` apunten directamente a Supabase y Upstash.

### Paso 2.2 — Configurar entorno virtual con `uv`
En Windows CMD / PowerShell:
```cmd
scripts\dev.cmd
```
O manualmente desde la raíz:
```bash
uv venv .venv
# Activar entorno:
# En Windows: .venv\Scripts\activate
# En Linux/macOS: source .venv/bin/activate
uv pip install -e "./backend[dev]"
```

### Paso 2.3 — Verificar conectividad directa
Ejecutar el script de diagnóstico para certificar la conexión con Supabase y Upstash:
```bash
python scripts/verificar_conexion.py
```
*Resultado esperado*: Ambas conexiones reportan estado `[OK]` en verde.

### Paso 2.4 — Aplicar migraciones SQL y semilla inicial
```bash
# 1. Aplicar migraciones 0001 a 0003
python scripts/migrar.py

# 2. Cargar catálogo semilla y establecimientos de Armenia (~150 productos, ~30 tiendas)
python scripts/semilla.py
```
*Resultado esperado*: Tablas creadas con RLS activa, rol `app_backend` con permisos, 43 parámetros sembrados y catálogo cargado con `es_demo = false` o `true` según procedencia.

---

## 3. Pruebas Automatizadas Rápidas (Calidad y Fronteras)

```bash
# 1. Pruebas unitarias de dominio puro (TDD) con reporte de cobertura
pytest backend/tests/unitarias --cov=backend/app/dominio --cov-report=term-missing

# 2. Chequeo estricto de tipos estáticos
mypy backend/app/dominio --strict

# 3. Verificación de arquitectura y neutralidad comercial (EC-06)
lint-imports --config backend/pyproject.toml
```
*Criterio de aprobación*: 100% de pruebas en verde, cobertura de dominio $\ge 95\%$ y cero contratos violados.

---

## 4. Servidores Locales de Desarrollo

- **Iniciar Backend FastAPI**:
  ```bash
  cd backend
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
  ```
- **Iniciar Frontend Next.js**:
  ```bash
  cd frontend
  npm install
  npm run dev
  ```
  La interfaz queda disponible en `http://localhost:3000` y la API en `http://localhost:8000/v1`.

---

## 5. Escenarios de Validación de Extremo a Extremo (E2E)

### Escenario 1: Verificación de Estado y Diagnóstico
```bash
curl -s http://127.0.0.1:8000/v1/salud/listo
```
*Resultado esperado*: `HTTP 200 OK` con `{ "estado": "listo", "bd": "conectado", "cache": "conectado" }`.

### Escenario 2: Consulta Pública de Comparación por Unidad Base
1. Obtener el `id` de "Arroz blanco" mediante búsqueda:
   ```bash
   curl -s "http://127.0.0.1:8000/v1/productos?q=arroz"
   ```
2. Consultar la comparación de precios del producto:
   ```bash
   curl -s "http://127.0.0.1:8000/v1/productos/<PRODUCTO_ID>/comparacion"
   ```
*Resultado esperado*:
- Responde `HTTP 200 OK` en $< 300$ ms.
- Los establecimientos aparecen ordenados por precio por kilogramo ascendente.
- El arreglo `"promociones": []` viaja separado sin afectar la lista de resultados.
- La cabecera `Cache-Control` y el cálculo de bloques separan vigentes de desactualizados.

### Escenario 3: Reporte de Precio Legítimo e Idempotencia (`EC-01`, `EC-02`)
1. Generar un UUID para `Idempotency-Key` (ej. `d3b07384-d113-4c97-b248-e87f6b92a27a`).
2. Enviar reporte:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/v1/reportes \
     -H "Authorization: Bearer <TOKEN_REPORTANTE>" \
     -H "Idempotency-Key: d3b07384-d113-4c97-b248-e87f6b92a27a" \
     -H "Content-Type: application/json" \
     -d '{"presentacion_id": "<PRES_ID>", "establecimiento_id": "<TIENDA_ID>", "precio_cop": 2600, "observado_en": "2026-11-02T18:00:00Z"}'
   ```
*Resultado esperado*:
- Primera petición: `HTTP 201 Created` con `{ "estado_visible": "recibido" }`.
- Segunda petición con misma llave: `HTTP 200 OK` inmediato con la respuesta original sin duplicar registros.
- La consulta de comparación refleja el nuevo precio vigente en menos de 60 segundos (`EC-02`).

### Escenario 4: Detección Automática de Anomalía (`EC-03`)
Enviar un reporte con valor divergente ($900 COP cuando la mediana es $2.600 COP):
```bash
curl -s -X POST http://127.0.0.1:8000/v1/reportes \
  -H "Authorization: Bearer <TOKEN_REPORTANTE>" \
  -H "Idempotency-Key: 99999999-0000-0000-0000-000000000001" \
  -H "Content-Type: application/json" \
  -d '{"presentacion_id": "<PRES_ID>", "establecimiento_id": "<TIENDA_ID>", "precio_cop": 900, "observado_en": "2026-11-02T18:05:00Z"}'
```
*Resultado esperado*:
- Al usuario se le responde `HTTP 201 Created` con `{ "estado_visible": "en_revision" }` (sin revelar señales internas).
- El precio público vigente en `GET .../comparacion` **NO** se modifica con el valor anómalo.
- En la bandeja de moderador (`GET /v1/moderacion/casos`), aparece un nuevo caso `reporte_dudoso` clasificado con z-score modificado.

### Escenario 5: Ejercicio de Supresión de Cuenta (Ley 1581)
Solicitar el borrado de cuenta del usuario de prueba:
```bash
curl -s -X DELETE http://127.0.0.1:8000/v1/mi-cuenta \
  -H "Authorization: Bearer <TOKEN_REPORTANTE>"
```
*Resultado esperado*:
- `HTTP 200 OK` confirmando la anonimización.
- En la base de datos, los reportes históricos conservan `precio_cop` pero pasan a `reportante_id = null` y `foto_prueba_path = null`.
- El alias pasa a `eliminado_<hash>` y el usuario queda eliminado de Supabase Auth.
