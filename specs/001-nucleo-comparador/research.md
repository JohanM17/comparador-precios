# Research & Architectural Decisions: Núcleo del Comparador de Precios (001-nucleo-comparador)

**Branch**: `001-nucleo-comparador` | **Feature**: Núcleo del Comparador | **Date**: 2026-11-02

Este documento consolida las investigaciones de ingeniería, decisiones de diseño (**D-01** a **D-14**) y decisiones de arquitectura (**ADR-001** a **ADR-018**) que fundamentan la construcción del Núcleo (Etapa 1).

---

## 1. Decisiones de Estilo y Organización del Código

### 1.1 Estilo Arquitectónico: Monolito Modular (ADR-002)
- **Decisión**: Se adopta un monolito modular organizado por dominios y módulos verticales en un único repositorio Git (`backend/`, `frontend/`, `supabase/`, `docs/`, `scripts/`).
- **Justificación**: El equipo consta de 4 ingenieros trabajando en un alcance académico acotado con alta interdependencia entre módulos. Un monolito modular elimina la sobrecarga operativa de orquestación de red, serialización múltiple, despliegue distribuido y consistencia eventual que imponen los microservicios, pero mantiene fronteras de software limpias mediante contratos e inversión de dependencias.
- **Alternativas descartadas**:
  - *Microservicios*: Descartado por complejidad innecesaria en observabilidad, latencia adicional en red y costo de infraestructura incompatible con el presupuesto de costo cero.
  - *Arquitectura Backend-as-a-Service (BaaS) pura (Supabase directo al frontend)*: Descartada porque violaría el Principio I y II de la Constitución: no permitiría implementar la evaluación determinista de anomalías, el decaimiento exponencial de vigencia, la anonimización de IP por HMAC rotativo ni la neutralidad comercial con garantías verificables en backend.

### 1.2 Stack Backend: Python 3.12 + FastAPI (ADR-003)
- **Decisión**: Se selecciona Python 3.12 con FastAPI, Pydantic v2 y SQLAlchemy 2.0 asíncrono (`asyncpg`), administrado localmente con el gestor de paquetes de alto rendimiento `uv`.
- **Justificación**: FastAPI ofrece validación estricta de esquemas en tiempo de compilación con Pydantic v2 (`extra='forbid'`), generación nativa y automática de especificaciones OpenAPI 3.1, y concurrencia asíncrona nativa de alto rendimiento bajo `uvicorn`. Además, Python permite cálculos matemáticos y estadísticos de precisión exacta con la biblioteca nativa `decimal` y librerías estadísticas, facilitando el desarrollo puro con TDD.
- **Alternativas descartadas**:
  - *Node.js con NestJS / Express*: Descartado por menor ergonomía en modelos estadísticos avanzados de detección de valores atípicos y aritmética exacta con decimales de alta precisión.
  - *Go / Rust*: Descartados por mayor tiempo de iteración para un proyecto académico de 4 integrantes con calendario de entregas estricto.

### 1.3 Stack Frontend: Next.js App Router + TypeScript (ADR-001, ADR-004)
- **Decisión**: Se construye una Progressive Web App (PWA) móvil responsiva basada en Next.js (App Router), TypeScript estricto, Tailwind CSS y componentes de `shadcn/ui`, consumiendo la API mediante un cliente fuertemente tipado generado desde `docs/api/openapi.json`.
- **Justificación**: Evita mantener bases de código móviles duplicadas (Android/iOS) y sortea los tiempos de revisión de las tiendas de aplicaciones. Proporciona instalación en pantalla de inicio con soporte de Service Worker y almacenamiento local (`IndexedDB`) para operar en pasillos de tiendas sin conexión.
- **Alternativas descartadas**:
  - *Aplicación Móvil Nativa (Flutter / React Native)*: Descartada por costos de publicación, fricción de instalación para consumidores ocasionales y duplicidad de esfuerzo.

---

## 2. Persistencia, Rendimiento y Presupuesto Costo Cero

### 2.1 Persistencia: Supabase PostgreSQL 16 + PostGIS (ADR-005, ADR-012)
- **Decisión**: Uso de PostgreSQL 16 gestionado en Supabase con extensiones `postgis`, `pg_trgm`, `unaccent` y `pgcrypto`. Se deshabilita el acceso anónimo directo activando Row Level Security (RLS) en todas las tablas (`revoke all on all tables in schema public from anon, authenticated`) y canalizando el tráfico exclusivamente a través de FastAPI con el rol de privilegios mínimos `app_backend` creado con `LOGIN` (`create role app_backend with login`), al cual se le revoca expresamente `DELETE` sobre `reporte_precio` y `UPDATE, DELETE` sobre `auditoria`.
- **Conectividad IPv4 en Windows (Supavisor Pooler)**: Dado que el host directo de Supabase resuelve por defecto sobre IPv6 en la capa gratuita, para conexiones desde redes IPv4 en Windows se soporta el **Session Pooler (puerto `5432` en `pooler.supabase.com`)** para `MIGRATIONS_DATABASE_URL` y el **Transaction Pooler (puerto `6543` con `statement_cache_size=0` en `asyncpg`)** o **Session Pooler (puerto `5432`)** para `DATABASE_URL`.
- **Justificación**: PostgreSQL provee integridad referencial estricta, soporte geoespacial nativo de alto desempeño para búsquedas por radio (`geography(Point, 4326)`), indexación de texto con trigramas para búsquedas difusas tolerantes a errores ortográficos y triggers para garantizar la inmutabilidad de la evidencia histórica.
- **Alternativas descartadas**:
  - *Bases de Datos NoSQL (MongoDB / Firebase)*: Descartadas por carecer de soporte ACID transaccional nativo para el recálculo atómico de precios vigentes y por la dificultad de asegurar inmutabilidad y neutralidad en esquemas no relacionales.

### 2.2 Estrategia de Caché de Dos Niveles (ADR-006, ADR-016)
- **Decisión**: Se implementa una caché híbrida de dos niveles:
  - **L1 (Memoria de proceso)**: Implementada con `cachetools.TTLCache` con vida útil de 5 segundos.
  - **L2 (Redis en Upstash)**: Instancia Serverless en la nube con TTL de 60 segundos por producto (`cmp:{producto_id}`).
- **Justificación**: Upstash Free otorga 500.000 comandos mensuales. En fines de semana de quincena, 500 usuarios concurrentes saturarían la cuota en horas si cada consulta golpeara directamente a Redis. La caché L1 en RAM absorbe las ráfagas en milisegundos sin consumir comandos de Upstash. Al modificarse un precio, el backend ejecuta invalidación inmediata (`DEL cmp:{producto_id}`), garantizando la meta de actualidad $\le 60$ s de `EC-02`.
- **Alternativas descartadas**:
  - *Caché únicamente en Redis*: Riesgo inminente de agotar la cuota mensual gratuita.
  - *Sin caché (consultas directas a PostgreSQL)*: Incumpliría el escenario `EC-04` ($p95 \le 2$ s con 500 usuarios) bajo los límites de CPU de la capa gratuita de Supabase.

### 2.3 Entorno de Desarrollo Local sin Docker
- **Decisión**: El entorno local del desarrollador utiliza `uv` para Python y conexiones de red directas vía TLS hacia los proyectos reales de Supabase y Upstash en la nube (o mock en memoria para pruebas unitarias y de carga), prescindiendo totalmente de Docker Desktop local.
- **Justificación**: Minimiza el consumo de memoria y CPU en las máquinas de los integrantes, elimina fallos de virtualización en Windows y acelera el arranque del servidor en menos de 1 segundo. El `Dockerfile` se reserva exclusivamente para el despliegue multi-etapa en la nube en T-50.

---

## 3. Algoritmos de Dominio y Calidad de Datos

### 3.1 Detección Determinista de Anomalías de Precio (ADR-011, D-03)
- **Decisión**: Evaluación matemática determinista en 5 capas:
  1. *Filtro de Rango Duro*: Precios fuera de $[50, 2.000.000]$ COP se rechazan de entrada (`422 PRECIO_FUERA_DE_RANGO`).
  2. *Conjunto de Referencia Jerárquico*: Evalúa secuencialmente 3 niveles con ventana de 14 días (`presentacion_tienda` $\rightarrow$ `presentacion` $\rightarrow$ `producto_unitario`). Requiere al menos $n \ge 3$ reportes aceptados.
  3. *Métricas Estadísticas Robustas*:
     - Si $n \ge 5$ y $\text{MAD} > 0$: Calcula *z-score* modificado $M = 0.6745 \cdot (x - m) / \text{MAD}$ con umbral $|M| > 3.5$.
     - Si $n \in \{3, 4\}$ o $\text{MAD} = 0$: Calcula desviación porcentual $|x - m| / m$ con umbral $30\%$.
     - Regla de salvaguarda de error de digitación: Factor extremo de $5\times$ o $1/5$ frente a la mediana (`ratio_extremo`).
  4. *Riesgo de Contexto*: Suma ponderada de señales (`sin_foto`: 0.15, `cuenta_nueva`: 0.25, `rafaga`: 0.40, `reputacion_baja`: 0.20) con umbral de duda en $0.60$.
  5. *Comportamiento sin Referencia*: Si $n < 3$ en todos los niveles, adopta el estado `sin_referencia` y no declara anomalía numérica, permitiendo poblar productos nuevos sin falsos positivos.
- **Justificación**: Métricas como la media y desviación estándar tradicional son vulnerables a valores extremos. La mediana y la Desviación Absoluta respecto a la Mediana (MAD) ofrecen el punto de ruptura más alto posible ($50\%$), haciendo al sistema resistente contra envenenamiento de datos.

### 3.2 Vigencia con Decaimiento Exponencial (D-02)
- **Decisión**: Los reportes mantienen el 100% de su peso temporal durante 48 horas frescas y reducen su peso a la mitad cada 72 horas (vida media). Se consideran vigentes entre los días 1 y 7; pasan a `desactualizado` (segundo bloque) entre los días 8 y 30; y expiran de la comparación activa tras 30 días.
- **Justificación**: Refleja con precisión la dinámica inflacionaria y de rotación de inventarios en tiendas de barrio colombianas sin aplicar cortes artificiales abruptos.

### 3.3 Reputación Bayesiana del Usuario (D-10)
- **Decisión**: Fórmula bayesiana con distribución Beta a priori:
  $$\text{reputacion} = \frac{A + 2}{A + 3M + 4}$$
  donde $A$ son reportes corroborados y $M$ son reportes descartados/malos confirmados por moderación.
- **Justificación**: Otorga un arranque neutral de $0.500$ a cuentas nuevas, premia la consistencia con convergencia asintótica y penaliza severamente los reportes fraudulentos ($3M$ en denominador) para desincentivar ataques de reputación.

### 3.4 Sincronización Offline e Idempotencia (ADR-010, EC-01)
- **Decisión**: La PWA utiliza `IndexedDB` (`cola_reportes`) y ejecuta el orden estricto de sincronización **Flujo F4**: (1) solicita URL firmada, (2) sube la imagen WebP $\le 300$ KB sin EXIF y guarda la ruta remota, (3) envía el reporte a `POST /v1/reportes` con cabecera `Idempotency-Key` (UUIDv4).
- **Justificación**: Asegura que fallos de red a mitad de camino no dejen transacciones inconsistentes ni dupliquen reportes ante reintentos.

---

## 4. Privacidad y Seguridad (Ley 1581 de 2012)

### 4.1 Geolocalización y Dirección IP (ADR-014, D-11)
- **Decisión**:
  - Las coordenadas `lat` y `lng` enviadas en peticiones públicas jamás se insertan en tablas SQL ni se imprimen en logs; el cálculo Haversine ocurre en la memoria del hilo de la petición y las variables se descartan de inmediato.
  - La dirección IP del cliente se convierte en `huella_red = HMAC-SHA256(ip_cliente, clave_secreta_diaria)` y se anula a `null` automáticamente tras 30 días mediante el job `limpiar_huellas`.
- **Justificación**: Cumple estrictamente con el principio de necesidad y proporcionalidad de la Ley Estatutaria 1581 de 2012, impidiendo la trazabilidad de la ubicación física de los ciudadanos o la reconstrucción de sus hábitos de desplazamiento.
