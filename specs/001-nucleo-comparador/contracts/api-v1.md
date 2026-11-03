# API Contracts: Núcleo del Comparador de Precios (v1)

**Branch**: `001-nucleo-comparador` | **Feature**: Núcleo del Comparador | **Date**: 2026-11-02

Este documento describe el contrato formal de la API REST expuesta en `/v1`, sus esquemas JSON de entrada y salida, convenciones de serialización, manejo de errores bajo RFC 9457 y la matriz de control de acceso por roles.

---

## 1. Convenciones Globales de la API

1. **Protocolo y Versión**: Todos los endpoints se exponen bajo el prefijo `/v1`.
2. **Formato de Cadenas Temporales**: Todas las fechas se envían y reciben como cadenas en formato ISO 8601 en UTC (`YYYY-MM-DDTHH:MM:SSZ`).
3. **Formato Monetario**: Todo precio se expresa como un número entero estricto en pesos colombianos (`precio_cop: int`), con todos los impuestos incluidos. Prohibido el uso de flotantes.
4. **Formato de Error Estándar (RFC 9457 - `application/problem+json`)**:
   ```json
   {
     "type": "https://comparador.armenia.gov.co/errores/precio-fuera-de-rango",
     "title": "Precio Fuera De Rango",
     "status": 422,
     "detail": "El precio 35 debe estar entre 50 y 2000000 COP.",
     "instance": "/v1/reportes",
     "codigo": "PRECIO_FUERA_DE_RANGO",
     "request_id": "req-9f8e7d6c-5b4a-3c2d"
   }
   ```
5. **Autenticación**: Cabecera `Authorization: Bearer <jwt_token>` validada mediante JWKS o clave simétrica según configuración de Supabase Auth.
6. **Idempotencia**: El endpoint `POST /v1/reportes` exige obligatoriamente la cabecera `Idempotency-Key: <uuid>`.

---

## 2. Endpoints Públicos (Sin Autenticación Requerida)

### 2.1 Salud y Diagnóstico
- **`GET /v1/salud`**
  - *Respuesta 200 OK*:
    ```json
    { "estado": "ok", "version": "1.0.0", "entorno": "local" }
    ```
- **`GET /v1/salud/listo`**
  - Verifica conectividad real con PostgreSQL y Upstash Redis.
  - *Respuesta 200 OK*:
    ```json
    { "estado": "listo", "bd": "conectado", "cache": "conectado" }
    ```

### 2.2 Catálogo de Productos y Búsqueda
- **`GET /v1/categorias`**
  - Lista las 10 categorías de la canasta familiar ordenadas por `orden`.
- **`GET /v1/productos?categoria_id=1&q=arroz&limite=24&pagina=1`**
  - Búsqueda difusa tolerante a errores ortográficos y tildes (`pg_trgm` + `unaccent`).
- **`GET /v1/productos/{id}`**
  - Detalle de un producto con sus presentaciones activas normalizadas.

### 2.3 Comparación de Precios de un Producto (Contrato Nuclear `EC-06`)
- **`GET /v1/productos/{id}/comparacion?presentacion_id=&orden=precio_unitario&municipio=Armenia&lat=4.5350&lng=-75.6750&radio_km=10.0&limite=50`**
  - Parámetros:
    - `orden`: `precio_unitario` (defecto), `precio`, `distancia` (exige `lat` y `lng`).
    - `lat` / `lng`: Opcionales para cálculo Haversine volátil en RAM.
  - *Respuesta 200 OK*:
    ```json
    {
      "datos": {
        "producto": {
          "id": "3b241101-e2bb-4255-8caf-4136c566a962",
          "nombre": "Arroz blanco",
          "categoria_id": 1,
          "unidad_base": "g",
          "unidad_visualizacion": "kg",
          "presentaciones": [
            {
              "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
              "etiqueta": "Arroz Diana 500 g",
              "marca": "Diana",
              "cantidad_base": 500.0
            }
          ]
        },
        "resultados": [
          {
            "establecimiento": {
              "id": "11111111-2222-3333-4444-555555555555",
              "nombre": "Tienda La Esquina",
              "tipo": "tienda_barrio",
              "barrio": "Centro",
              "direccion": "Cra 14 # 18-22",
              "distancia_m": 420
            },
            "presentacion": {
              "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
              "etiqueta": "Arroz Diana 500 g",
              "marca": "Diana",
              "cantidad_base": 500.0
            },
            "precio_cop": 2600,
            "precio_oficial_cop": null,
            "precio_por_unidad": {
              "valor_cop": 5200,
              "por": "kg"
            },
            "sello": "confiable",
            "motivo_sello": null,
            "n_reportes_validos": 4,
            "n_fuentes": 3,
            "ultimo_reporte_en": "2026-11-01T14:20:00Z",
            "con_foto_prueba": true,
            "es_bloque_secundario": false
          }
        ],
        "promociones": [],
        "meta": {
          "criterio_orden": "precio_unitario",
          "texto_neutralidad": "Ordenado por precio por kg. Las promociones no cambian el orden.",
          "bloques": ["vigentes", "dudosos_y_desactualizados"],
          "generado_en": "2026-11-01T14:22:10Z",
          "datos_de_demostracion": false
        }
      }
    }
    ```

### 2.4 Establecimientos y Solicitud Pública de Corrección
- **`GET /v1/establecimientos?municipio=Armenia&lat=4.5350&lng=-75.6750&radio_km=5.0`**
- **`GET /v1/establecimientos/{id}`**
- **`POST /v1/establecimientos/{id}/solicitudes-correccion`**
  - Formulario con *honeypot* para reportar datos erróneos del negocio. Genera un caso de moderación `solicitud_correccion`.

---

## 3. Endpoints Autenticados (Reportantes y Titulares de Datos)

### 3.1 Gestión de Cuenta y Ley 1581
- **`POST /v1/mi-cuenta/autorizacion`**
  - Registra el consentimiento informado. Exigido antes de cualquier reporte (`403 AUTORIZACION_REQUERIDA` si falta).
  - *Cuerpo*: `{ "version_politica": "1.0", "alias": "juan_armenia" }`
- **`GET /v1/mi-cuenta`**: Consulta datos personales del perfil.
- **`PATCH /v1/mi-cuenta`**: Modifica alias `{ "alias": "nuevo_alias" }`.
- **`DELETE /v1/mi-cuenta`**: Derecho de supresión. Anonimiza reportes (`reportante_id = null`), borra fotos del bucket, asigna alias `eliminado_<hash>` y borra usuario en Supabase Auth.

### 3.2 Registro de Precios y Evidencias
- **`POST /v1/fotos/url-subida`**
  - Genera URL firmada válida por 5 minutos para subir foto WebP al bucket privado `pruebas`.
  - *Respuesta 201*: `{ "ruta": "fotos/2026/11/abc.webp", "url_firmada": "https://...", "expira_en": 300 }`
- **`POST /v1/reportes`**
  - Cabecera obligatoria: `Idempotency-Key: <uuid>`.
  - *Cuerpo*:
    ```json
    {
      "presentacion_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "establecimiento_id": "11111111-2222-3333-4444-555555555555",
      "precio_cop": 2600,
      "observado_en": "2026-11-01T14:19:00Z",
      "foto_ruta": "fotos/2026/11/abc.webp"
    }
    ```
  - *Respuesta 201 Created* (o 200 OK en reintentos con la misma llave):
    ```json
    {
      "datos": {
        "id": "9f8e7d6c-5b4a-3c2d-1e0f-123456789abc",
        "estado_visible": "recibido",
        "mensaje": "Gracias, tu precio quedó registrado."
      }
    }
    ```
- **`GET /v1/mis-reportes?pagina=1&limite=20`**: Historial del reportante con estado visible (`recibido`, `en_revision`, `rechazado`).
- **`POST /v1/sugerencias-presentacion`**: Sugiere una nueva variante comercial abriendo caso `sugerencia_presentacion`.

---

## 4. Endpoints de Moderación (`rol == 'moderador'`)

- **`GET /v1/moderacion/casos?estado=abierto&tipo=&prioridad=`**: Bandeja priorizada de casos.
- **`GET /v1/moderacion/casos/{id}`**: Detalle, señales de contexto activadas y URL firmada de la fotografía por 10 minutos.
- **`POST /v1/moderacion/casos/{id}/resolver`**:
  - *Cuerpo*: `{ "decision": "confirmar" | "descartar" | "sancionar", "nota": "Explicación", "sancion": { "tipo": "suspension", "dias": 7 } }`
- **`GET /v1/moderacion/usuarios/{id}`**: Historial, reputación bayesiana ($A$ y $M$) y sanciones.
- **`POST /v1/moderacion/sanciones`**: Aplica sanción disciplinaria manual.
- **`POST /v1/moderacion/sanciones/{id}/apelacion`**: Resuelve apelación de un usuario sancionado.
- **`POST` y `PATCH /v1/moderacion/productos`**: Mantenimiento del catálogo base.
- **`POST` y `PATCH /v1/moderacion/presentaciones`**: Alta de presentaciones calculando `cantidad_base`.
- **`POST` y `PATCH /v1/moderacion/establecimientos`**: Mantenimiento del directorio comercial.
- **`GET /v1/moderacion/catalogo-externo?codigo_barras=...`**: Consulta Open Food Facts con timeout de 3 s y circuit breaker.
- **`GET /v1/moderacion/parametros`** y **`PUT /v1/moderacion/parametros`**: Lectura y calibración en caliente de los 43 parámetros con registro en auditoría.
- **`GET /v1/moderacion/auditoria?pagina=1&limite=50`**: Bitácora inmutable.
- **`POST /v1/moderacion/recalcular-precio-vigente`**: Reconstrucción forzada transaccional.

---

## 5. Endpoints Internos para Tareas Programadas (`jobs.yml`)

- **`POST /internal/jobs/{nombre}`**
  - Autenticado exclusivamente con cabecera `X-Job-Token: <JOB_TOKEN>`.
  - Tareas admitidas en el núcleo:
    - `ping_bd`: Ejecuta consulta viva para evitar pausa de inactividad en Supabase Free.
    - `recalcular_reputacion`: Recalcula la reputación bayesiana de los perfiles activos.
    - `reconstruir_precio_vigente`: Reconstrucción nocturna completa del modelo de lectura.
    - `limpiar_huellas`: Anula a `null` las `huella_red` con antigüedad mayor a 30 días (Ley 1581).

---

## 6. Matriz de Control de Acceso por Roles (RBAC)

| Grupo de Endpoints | Anónimo (sin JWT) | Reportante (sin autorizar Ley 1581) | Reportante (`activa`) | Moderador (`activa`) | Cuenta `suspendida` o `bloqueada` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `GET /v1/salud`, `/productos/*`, `/establecimientos/*` | `200` | `200` | `200` | `200` | `200` |
| `POST /v1/establecimientos/{id}/solicitudes-correccion` | `201` | `201` | `201` | `201` | `201` |
| `POST /v1/mi-cuenta/autorizacion` | `401` | `201` | `200` | `200` | `403 CUENTA_SUSPENDIDA` |
| `GET /v1/mi-cuenta`, `PATCH /v1/mi-cuenta` | `401` | `403 AUTORIZACION_REQUERIDA` | `200` | `200` | `403 CUENTA_SUSPENDIDA` |
| `DELETE /v1/mi-cuenta` | `401` | `403 AUTORIZACION_REQUERIDA` | `200` | `200` | `200` (Derecho de Ley) |
| `POST /v1/reportes`, `/fotos/url-subida`, `/sugerencias-*` | `401` | `403 AUTORIZACION_REQUERIDA` | `201` | `201` | `403 CUENTA_SUSPENDIDA` |
| `GET /v1/mis-reportes` | `401` | `403 AUTORIZACION_REQUERIDA` | `200` | `200` | `403 CUENTA_SUSPENDIDA` |
| `/v1/moderacion/*` | `401` | `403 PROHIBIDO` | `403 PROHIBIDO` | `200 / 201` | `403 CUENTA_SUSPENDIDA` |
| `POST /internal/jobs/{nombre}` | `401` (sin `X-Job-Token`) | `401` | `401` | `401` | `200` (solo con token válido) |
