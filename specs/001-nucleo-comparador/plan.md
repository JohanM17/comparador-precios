# Implementation Plan: Núcleo del Comparador de Precios (001-nucleo-comparador)

**Branch**: `001-nucleo-comparador` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-nucleo-comparador/spec.md` and master architecture from `docs/PLAN_CONSTRUCCION.md`

## Summary

Implementación integral de la **Etapa 1 (Núcleo)** de la Plataforma Colaborativa de Comparación de Precios para Armenia y Quindío. El sistema permite a consumidores consultar y comparar precios normalizados por unidad de medida base (`kg`, `l`, `unidad`) con sellos de confiabilidad y ordenamiento neutral en dos bloques; a reportantes capturar precios frente a la góndola en $\le 15$ segundos con soporte de cola offline (`IndexedDB`) e idempotencia estricta; y a moderadores auditar reportes anómalos o ráfagas coordinadas filtradas mediante evaluación determinista jerárquica. La arquitectura es un monolito modular con backend en Python (FastAPI + uv), persistencia directa en Supabase (PostgreSQL + PostGIS, Auth, Storage) y caché de dos niveles (L1 RAM + L2 Upstash Redis), frontend PWA en Next.js (App Router), operando bajo presupuesto de costo cero sin requerir Docker local.

## Technical Context

**Language/Version**: Python 3.12 (Backend con `uv` como gestor de paquetes y entornos virtuales) y TypeScript 5.5+ / Node.js 20+ (Frontend Next.js 14 App Router).

**Primary Dependencies**:
- *Backend*: `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`, `pydantic>=2.9.0` (`model_config = ConfigDict(extra='forbid')`), `pydantic-settings>=2.5.0`, `sqlalchemy[asyncio]>=2.0.35`, `asyncpg>=0.29.0`, `redis>=5.1.0` (cliente asíncrono Upstash), `httpx>=0.27.0`, `pyjwt[crypto]>=2.9.0`, `pillow>=10.4.0` (limpieza EXIF), `cachetools>=5.5.0` (caché L1).
- *Frontend*: `next>=14.2.0`, `react>=18.3.0`, `tailwindcss>=3.4.0`, `shadcn/ui`, `lucide-react`, `idb` (cola IndexedDB en cliente).

**Storage**:
- Supabase PostgreSQL 16 + PostGIS 3.4 (conexión directa con pool y rol de privilegios mínimos `app_backend`, RLS activa sin políticas anónimas).
- Upstash Redis Free (L2 para caché de comparación con TTL de 60 s e invalidación transaccional inmediata `DEL cmp:{producto_id}`; mock en memoria para pruebas unitarias y de carga local).
- Supabase Storage (Bucket privado `pruebas` con URLs firmadas de corta duración y compresión WebP sin EXIF).

**Testing**:
- *Backend*: `pytest>=8.3.0`, `pytest-asyncio>=0.24.0`, `pytest-cov>=5.0.0` (cobertura $\ge 95\%$ en `app/dominio/`), `hypothesis>=6.112.0` (pruebas basadas en propiedades), `schemathesis>=3.36.0` (pruebas de contrato OpenAPI), `ruff>=0.6.0`, `mypy>=1.11.0` (`--strict`), `import-linter>=2.1` (fronteras arquitectónicas y neutralidad `EC-06`).
- *Frontend*: `playwright>=1.47.0`, `@axe-core/playwright>=4.9.0` (auditoría automática WCAG 2.2 AA).

**Target Platform**:
- *Desarrollo Local*: Windows 11 nativo con `uv` y CMD/PowerShell, conectándose directamente a Supabase y Upstash sin Docker Desktop.
- *Producción*: Backend containerizado multi-etapa en Railway / Render Free / Fly.io (T-50); Frontend en Vercel Hobby; Tareas programadas en GitHub Actions.

**Project Type**: Monolito modular (repositorio unificado `backend/`, `frontend/`, `supabase/`, `docs/`, `scripts/`, `specs/`).

**Performance Goals**:
- `EC-04`: Percentil 95 ($p95$) $\le 2.0$ segundos y tasa de error $< 1\%$ con 500 usuarios concurrentes.
- Lectura de comparación en caliente desde caché: $< 50$ ms; en frío desde PostgreSQL: $< 300$ ms.
- `EC-02`: Actualización y reflejo del precio vigente en $\le 60$ segundos (100% de 100 pruebas automáticas).

**Constraints**:
- Presupuesto Costo Cero ($0 USD): Protección estricta de las cuotas mensuales (Supabase Free, Upstash Redis 500k comandos/mes, Vercel Hobby).
- Privacidad Ley 1581 de 2012: Prohibición absoluta de guardar coordenadas `lat`/`lng` en base de datos o logs; IP procesada mediante `HMAC-SHA256` con clave rotativa diaria y retención de 30 días.
- Neutralidad Comercial Incondicional (`EC-06`): Las promociones viajan en arreglo separado y jamás alteran el ranking orgánico por precio base.
- Dominio Puro: `backend/app/dominio/` sin I/O, sin SQL, sin HTTP, sin reloj del sistema.

**Scale/Scope**:
- Etapa 1: ~150 productos de canasta familiar, ~30 tiendas iniciales en Armenia y Quindío, 7 pantallas de interfaz (`S1` a `S7`), 21 requisitos funcionales (**FR-001** a **FR-021**).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principio I (Mobile-first, registro $\le 15$ s, cola offline e idempotencia - `EC-01`):** Cumplido. Formulario de 3 controles, compresión WebP $\le 300$ KB en cliente, cola `IndexedDB` con subida en dos pasos (foto primero, reporte después) y cabecera `Idempotency-Key` obligatoria.
- [x] **Principio II (Privacidad por diseño y Ley 1581):** Cumplido. `lat`/`lng` se descartan tras el cálculo Haversine en memoria RAM; IP se ofusca como `huella_red` HMAC rotativo a 30 días; fotos sin EXIF; borrado de cuenta en `/v1/mi-cuenta` con anonimización irreversible.
- [x] **Principio III (Neutralidad comercial absoluta - `EC-06`):** Cumplido. Separación estricta de `resultados` y `promociones`; ordenamiento por dos bloques según precio por unidad base; regla `import-linter` prohíbe importar `app.modulos.comercial`.
- [x] **Principio IV (Dominio puro con TDD estricto - NON-NEGOTIABLE):** Cumplido. Lógica en `app/dominio/` 100% pura, con pruebas `pytest` escritas antes del código, cobertura $\ge 95\%$, tipado `mypy --strict` y protocolo abstracto `Reloj`.
- [x] **Principio V (Cero constantes mágicas, entorno local sin Docker y costo cero):** Cumplido. 43 parámetros en `config_parametro` leídos con caché de 60 s; entorno virtual con `uv` y conexión directa a Supabase y Upstash sin Docker local; Dockerfile reservado exclusivamente para despliegue en la nube en T-50.

## Project Structure

### Documentation (this feature)

```text
specs/001-nucleo-comparador/
├── plan.md              # Este plan de implementación técnico
├── research.md          # Fase 0: Decisiones arquitectónicas y alternativas descartadas
├── data-model.md        # Fase 1: Entidades, tipos, esquemas SQL y fórmulas del dominio
├── quickstart.md        # Fase 1: Guía de validación y escenarios ejecutables paso a paso
├── contracts/
│   └── api-v1.md        # Fase 1: Contratos JSON de API v1 y Matriz de Permisos por Rol
└── checklists/
    └── requirements.md  # Validación de calidad de la especificación
```

### Source Code (repository layout)

```text
/
├── AGENTS.md                        # Contexto del agente con reglas innegociables y bloque SPECKIT
├── CLAUDE.md                        # Contexto espejo sincronizado
├── PROYECTO.md                      # Resumen funcional y marco del proyecto
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # Factory create_app(), CORS, RFC 9457 y montaje de routers
│   │   ├── config.py                # Configuracion(BaseSettings) con pydantic-settings
│   │   ├── bd.py                    # AsyncEngine, sessionmaker y dependencia obtener_sesion
│   │   ├── compartido/              # Utilidades transversales sin estado
│   │   │   ├── errores.py           # Excepciones de aplicación y manejador ProblemDetails
│   │   │   ├── reloj.py             # Protocolo Reloj e implementaciones Sistema / Falso
│   │   │   ├── seguridad.py         # Validación JWT (JWKS/HS256) y extracción de perfil
│   │   │   ├── limites.py           # LimitadorVentanaDeslizante en memoria
│   │   │   ├── texto.py             # Normalización de texto (minúsculas sin tildes)
│   │   │   ├── huella.py            # Cálculo HMAC-SHA256 con clave rotativa diaria
│   │   │   └── logging_cfg.py       # Logger JSON filtrando coordenadas y datos personales
│   │   ├── dominio/                 # LÓGICA PURA SIN I/O (mypy --strict, cobertura >= 95%)
│   │   │   ├── unidades.py          # Conversión dimensional, precio_por_base y parsear_cantidad
│   │   │   ├── reputacion.py        # Modelo bayesiano de reputación y banderas de cuenta
│   │   │   ├── anomalia.py          # Selección jerárquica de referencia, z-score modificado y %
│   │   │   ├── riesgo.py            # Señales de contexto, detección de ráfagas y evaluación
│   │   │   ├── vigencia.py          # Factor temporal exponencial y mediana ponderada
│   │   │   ├── sello.py             # Árbol determinista de sello_precio y motivo
│   │   │   └── orden.py             # Partición neutral en dos bloques y desempates
│   │   ├── puertos/                 # Interfaces abstractas (Protocol)
│   │   │   ├── cache.py             # PuertoCache (get, set, delete)
│   │   │   ├── almacenamiento.py    # PuertoAlmacenamientoFotos (url_subida, eliminar)
│   │   │   ├── catalogo_externo.py  # PuertoCatalogoExterno (Open Food Facts)
│   │   │   └── politica_precio.py   # PoliticaPrecioReferencia (SoloUsuarios en Núcleo)
│   │   ├── adaptadores/             # Implementaciones concretas de infraestructura
│   │   │   ├── cache_dos_niveles.py # L1 memoria (5 s) + L2 Redis Upstash (60 s)
│   │   │   ├── storage_supabase.py  # Supabase Storage + limpieza EXIF con Pillow
│   │   │   └── open_food_facts.py   # Cliente HTTP con timeout 3 s y circuit breaker
│   │   ├── modulos/                 # Módulos verticales con api, servicio, repositorio, esquemas
│   │   │   ├── cuentas/             # Autorización Ley 1581, perfil y borrado de cuenta
│   │   │   ├── catalogo/            # Categorías, productos y presentaciones normalizadas
│   │   │   ├── establecimientos/    # Directorio, proximidad PostGIS y solicitudes corrección
│   │   │   ├── precios/             # Reportes, idempotencia, recálculo y comparación
│   │   │   ├── confianza/           # Orquestación de evaluación de reportes y ráfagas
│   │   │   └── moderacion/          # Gestión de casos, sanciones y calibración de parámetros
│   │   └── tareas/
│   │       └── router_jobs.py       # Endpoints internos protegidos con X-Job-Token
│   ├── tests/
│   │   ├── unitarias/               # Pruebas TDD de dominio/ puras (sin BD ni red)
│   │   ├── integracion/             # Pruebas con Supabase PostgreSQL y Upstash Redis reales
│   │   ├── contrato/                # Schemathesis y matriz de permisos por rol
│   │   └── arquitectura/            # Import-linter e inmutabilidad
│   ├── pyproject.toml               # Dependencias y configuración de herramientas
│   └── Dockerfile                   # Multi-etapa reservado para despliegue en la nube (T-50)
├── frontend/
│   ├── src/
│   │   ├── app/                     # Next.js App Router (S1 a S7 + /offline)
│   │   ├── components/              # Los 15 componentes reutilizables especificados
│   │   └── lib/
│   │       ├── api/                 # Cliente tipado generado desde docs/api/openapi.json
│   │       ├── auth/                # Cliente de sesión Supabase Auth
│   │       ├── offline/             # Cola IndexedDB (cola_reportes) y sincronizador F4
│   │       └── imagen/              # Compresión WebP <= 300 KB sin EXIF en <canvas>
│   ├── package.json
│   └── tsconfig.json
├── supabase/
│   ├── migrations/                  # 0001_..., 0002_..., 0003_... (Núcleo)
│   └── seed/                        # Archivos CSV para carga inicial
├── scripts/
│   ├── dev.cmd                      # Automatización local Windows CMD (entorno uv)
│   ├── verificar_conexion.py        # Verificación directa de Supabase y Upstash
│   ├── migrar.py                    # Aplicador de migraciones SQL con MIGRATIONS_DATABASE_URL
│   ├── semilla.py                   # Carga idempotente de catálogos y tiendas
│   └── exportar_openapi.py          # Generador de docs/api/openapi.json sin servidor
└── infra/
    ├── docker-compose.yml           # Referencia opcional (no requerido en desarrollo local)
    └── k6/ec04_carga.js             # Script de prueba de carga 500 VUs
```

**Structure Decision**: Monolito modular con separación tajante entre dominio puro, puertos e infraestructura en backend, desacoplado del frontend Next.js a través del contrato OpenAPI exportado automáticamente.

## Complexity Tracking

> **Violaciones a la Constitución**: Cero. Todos los principios y compuertas de calidad se cumplen estrictamente sin requerir excepciones ni justificaciones especiales.
