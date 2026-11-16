# Plataforma Colaborativa de Comparación de Precios de la Canasta Familiar (`v1.0-nucleo`)

Plataforma cívica y colaborativa (Armenia, Quindío) para comparar precios reales de productos de la canasta familiar normalizados por unidad base (`g`, `ml`, `unidad`), con captura comunitaria en `< 15 s` (`EC-01`), resiliencia offline mediante `IndexedDB` + `Idempotency-Key`, control estadístico de anomalías y ráfagas (`EC-03`), actualización en `<= 60 s` (`EC-02`), neutralidad comercial estricta (`EC-06`) y cumplimiento de la Ley 1581 de 2012.

## Arquitectura y Principios

- **Backend**: Monolito modular en **FastAPI (Python 3.12)** con arquitectura hexagonal ligera (`backend/app/dominio/` puro con `Decimal`, `puertos/`, `adaptadores/` y `modulos/` aislados).
- **Base de datos**: **PostgreSQL 15 + PostGIS** en Supabase con rol restringido `app_backend`, tablas de evidencia inmutables (`reporte_precio`, `auditoria`) y `config_parametro` editable en caliente.
- **Caché y control de tráfico**: Caché de dos niveles (`L1` en memoria + `L2` Redis en Upstash con invalidación inmediata por producto).
- **Frontend**: **Next.js 14 (App Router)** + Tailwind CSS + PWA (`Serwist`/Service Worker + `IndexedDB`), sin lógica de precios ni ranking en el cliente; tipos autogenerados desde [docs/api/openapi.json](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/api/openapi.json).

## Ejecución Local Reproducible (sin Docker)

Sigue la guía completa en [docs/despliegue.md](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/despliegue.md). Resumen rápido:

```powershell
# 1. Configurar variables de entorno
Copy-Item .env.example .env

# 2. Instalar dependencias del backend con uv y verificar conexión a Supabase
uv --directory backend sync --dev
uv --directory backend run python ../scripts/verificar_conexion.py
uv --directory backend run python ../scripts/migrar.py
uv --directory backend run python ../scripts/semilla.py

# 3. Iniciar backend FastAPI
uv --directory backend run uvicorn app.main:app --reload --port 8000

# 4. Instalar y ejecutar frontend Next.js
npm --prefix frontend install
npm --prefix frontend run dev
```

## Verificación de Calidad y Pruebas

```powershell
# Backend: pruebas unitarias, contrato RBAC e integración + análisis estático
backend\.venv\Scripts\pytest.exe -c backend/pyproject.toml --cov=app
uv --directory backend run ruff check .
uv --directory backend run mypy --strict app
uv --directory backend run lint-imports

# Frontend: tipos, lint, build y pruebas E2E Playwright (WCAG 2.2 AA + flujos núcleo)
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
npx --prefix frontend playwright test -c frontend/playwright.config.ts
```

## Documentación Clave

- **Guía de despliegue local y producción**: [docs/despliegue.md](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/despliegue.md)
- **Documento de Arquitectura v1 (Entregable 5)**: [docs/entregable_5_arquitectura_v1.md](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/entregable_5_arquitectura_v1.md)
- **Plan maestro y especificación**: [docs/PLAN_CONSTRUCCION.md](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/PLAN_CONSTRUCCION.md)
- **Contratos OpenAPI**: [docs/api/openapi.json](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/api/openapi.json)
- **Informes de calidad**:
  - [Entregable 9 — TDD y Análisis Estático](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/calidad/entregable_9_tdd_analisis_estatico.md)
  - [Informe EC-02 (100 repeticiones de actualidad)](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/calidad/informe_ec02.md)
  - [Informe EC-03 (Credibilidad y anti-ráfagas)](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/calidad/informe_ec03.md)
  - [Informe EC-04 (Carga 500 VUs)](file:///c:/Users/CODEBOOK/Desktop/comparador-precios/docs/calidad/informe_ec04.md)

