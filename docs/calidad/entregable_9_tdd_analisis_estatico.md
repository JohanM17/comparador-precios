# Entregable 9 — Informe de TDD, Cobertura y Análisis Estático (`T-52`)

**Versión certificada:** `v1.0-nucleo` | **Fecha:** 2026-11-14

---

## 1. Trazabilidad del Flujo TDD (`test -> feat -> refactor`) en el Historial Git

El desarrollo del dominio puro (`backend/app/dominio/`, sin I/O, sin BD, sin reloj del sistema y con aritmética `Decimal` + pruebas basadas en propiedades con `hypothesis`) precedió de manera verificable a las capas de aplicación, persistencia y UI en el historial de commits de la rama `001-nucleo-comparador`:

| Fase / Hito | Commit Git | Evidencia y propósito dentro del ciclo TDD |
|---|---|---|
| **Rojo -> Verde -> Refactor (Unidades)** | `8bd299b` | `test(dominio): desarrollar con TDD modulo puro unidades.py con Decimal e hypothesis (T-10)` — define pruebas unitarias y propiedades `hypothesis` para conversión y normalización `g/ml/unidad` antes de integrarlo al catálogo y reportes. |
| **Rojo -> Verde -> Refactor (Motor de Confianza y Comparación)** | `59f7ddd` | `test(dominio): completar con TDD vigencia, sello, orden, anomalia, riesgo y reputacion con cobertura >=95% (T-20, T-30, T-31)` — prueba primero casos borde de mediana ponderada, MAD/`z-score`, sellos, reputación y orden neutral antes de los casos de uso reales. |
| **Capas de Infraestructura y Aplicación (`feat`)** | `1ea33df`, `996d240`, `50c4f91`, `c7d08ef`, `68a5cdc` | Implementación de puertos, adaptadores y endpoints REST (`cuentas`, `precios`, `confianza`, `moderacion`) consumiendo exclusivamente el dominio puro ya cubierto por `pytest`. |
| **Pruebas de Contrato RBAC, Integración y E2E (`T-51`, `T-54`, `T-53`)** | Commits de cierre Ola 5 | Certificación parametrizada de la Matriz de Permisos (`34` celdas), `100/100` repeticiones `EC-02`, carga `EC-04` y E2E Playwright (`13/13` con WCAG 2.2 AA). |

> [!NOTE]
> Cada tarea `T-xx` del dominio consolidó su ciclo interno *prueba que falla -> implementación mínima -> refactorización* en commits por hito (`test(dominio): ...`), precediendo a los commits `feat(...)` de integración con Supabase y FastAPI.

---

## 2. Cobertura del Dominio Puro (`>= 95 %`) y Suite Completa

Ejecución completa ejecutada sobre la versión final del código con `backend\.venv\Scripts\pytest.exe -c backend/pyproject.toml --cov=app --cov-report=term-missing`:

- **Resultado global**: **`143` pruebas aprobadas, `0` fallidas, `0` omitidas** (`Exit code 0`, duración `1 298.60 s`).
- **Cobertura total del backend (`backend/app/`)**: **`78 %`** (`3 228` sentencias, `719` sin cubrir).
- **Cobertura del dominio puro (`backend/app/dominio/`)**: **`99.05 %`** (`420` sentencias, `4` sin cubrir — cumple ampliamente la meta `>= 95 %`):

| Módulo (`backend/app/dominio/`) | Sentencias | No cubiertas | Cobertura | Líneas pendientes |
|---|---:|---:|---:|---|
| `__init__.py` | 0 | 0 | **100 %** | — |
| `anomalia.py` | 60 | 1 | **98 %** | `58` |
| `orden.py` | 40 | 0 | **100 %** | — |
| `parametros.py` | 49 | 0 | **100 %** | — |
| `reputacion.py` | 17 | 0 | **100 %** | — |
| `riesgo.py` | 39 | 1 | **97 %** | `71` |
| `sello.py` | 77 | 0 | **100 %** | — |
| `unidades.py` | 88 | 0 | **100 %** | — |
| `vigencia.py` | 50 | 2 | **96 %** | `71-72` |
| **Subtotal Dominio Puro** | **420** | **4** | **99.05 %** | — |

---

## 3. Contratos Arquitectónicos (`import-linter`)

Ejecución de `uv --directory backend run lint-imports` (`Analyzed 106 files, 458 dependencies`):

| Contrato arquitectónico | Estado | Propósito verificado |
|---|---|---|
| `Dominio es puro y no importa infraestructura ni frameworks` | **KEPT** | Garantiza aislamiento total de `app.dominio` frente a FastAPI, SQLAlchemy, httpx, Redis y adaptadores. |
| `Precios nunca importa el modulo comercial (EC-06)` | **KEPT** | Blindaje estructural de neutralidad comercial entre `app.modulos.precios` y `app.modulos.comercial`. |
| `Modulos no importan adaptadores concretos directamente` | **KEPT** | Mantiene inversión de dependencias mediante interfaces en `app.puertos`. |

**Resumen:** **`3 kept, 0 broken`** (`Exit code 0`).

---

## 4. Resultados de Análisis Estático y Build

| Herramienta / Gate | Comando ejecutado | Resultado | Estado |
|---|---|---|---|
| **Ruff Lint** | `uv --directory backend run ruff check .` | `All checks passed!` (`0` errores) | **PASS** |
| **Ruff Format** | `uv --directory backend run ruff format --check .` | `113 files already formatted` | **PASS** |
| **Mypy Estricto** | `uv --directory backend run mypy --strict app` | `Success: no issues found in 81 source files` | **PASS** |
| **Import Linter** | `uv --directory backend run lint-imports` | `Contracts: 3 kept, 0 broken` | **PASS** |
| **TypeScript Check** | `npm --prefix frontend run typecheck` | `tsc --noEmit` sin errores | **PASS** |
| **ESLint Next.js** | `npm --prefix frontend run lint` | `No ESLint warnings or errors` | **PASS** |
| **Next.js Production Build** | `npm --prefix frontend run build` | `9/9` rutas compiladas (`exit code 0`) | **PASS** |
| **Playwright E2E + Axe WCAG 2.2 AA** | `npx --prefix frontend playwright test -c frontend/playwright.config.ts tests/e2e/flujos_nucleo.spec.ts tests/e2e/accesibilidad.spec.ts` | **`13/13` pruebas aprobadas** (`32.7 s`) | **PASS** |
