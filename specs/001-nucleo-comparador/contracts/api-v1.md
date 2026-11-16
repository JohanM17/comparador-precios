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
5. **Autenticación**: Cabecera `Authorization: Bearer <jwt_token>` validada mediante JWKS (`SUPABASE_JWKS_URL`) o clave simétrica (`SUPABASE_JWT_SECRET`) según configuración de Supabase Auth (`PA-02`). El rol se lee exclusivamente desde la tabla `perfil` (`FR-005`).
6. **Idempotencia y Sincronización Offline (Flujo `F4`)**: El endpoint `POST /v1/reportes` exige obligatoriamente la cabecera `Idempotency-Key: <uuid>`. En la cola offline `IndexedDB` (`cola_reportes`), el sincronizador ejecuta primero la obtención de URL firmada (`POST /v1/fotos/url-subida`) y la subida del blob WebP ($\le 300$ KB sin EXIF), persiste `foto_ruta_remota` en `IndexedDB`, y solo después invoca `POST /v1/reportes` con la `Idempotency-Key`.

### 1.1 Catálogo Completo de Códigos de Error (`application/problem+json` — RFC 9457)

| Código (`codigo`) | Estado HTTP | Cuándo se devuelve |
| :--- | :---: | :--- |
| `VALIDACION` | `422` | Esquema inválido, campo extra no permitido (`extra='forbid'`), falta `Idempotency-Key` o se pide `orden=precio` sin `presentacion_id`. |
| `PRECIO_FUERA_DE_RANGO` | `422` | `precio_cop` es menor que `precio.min_cop` (50) o mayor que `precio.max_cop` (2.000.000). |
| `FECHA_INVALIDA` | `422` | `observado_en` está en el futuro ($> 60$ s) o tiene más de `observado.max_antiguedad_horas` (24 h). |
| `UNIDADES_INCOMPATIBLES` | `422` | La `unidad` de la presentación no es convertible a la `unidad_base` del producto. |
| `ARCHIVO_INVALIDO` | `422` | La fotografía supera `foto.max_kb` (300 KB) o su tipo MIME no está en `foto.tipos`. |
| `NO_AUTENTICADO` | `401` | Falta cabecera `Authorization: Bearer`, token malformado, firma inválida o token expirado. |
| `PROHIBIDO` | `403` | El rol en `perfil.rol` no tiene permiso para el endpoint o el comercio intenta operar un establecimiento ajeno. |
| `AUTORIZACION_REQUERIDA` | `403` | El usuario autenticado aún no ha registrado su aceptación de datos en `POST /v1/mi-cuenta/autorizacion`. |
| `CUENTA_SUSPENDIDA` | `403` | `perfil.estado` es `'suspendida'` o `'bloqueada'`. |
| `NO_ENCONTRADO` | `404` | El recurso (`producto`, `presentacion`, `establecimiento`, `caso`) no existe o está inactivo. |
| `CONFLICTO` | `409` | Duplicado en restricción única (`alias` ya usado, `codigo_barras` repetido o presentación duplicada). |
| `LIMITE_EXCEDIDO` | `429` | Se superó el límite de peticiones por usuario o por IP; incluye cabecera obligatoria `Retry-After`. |
| `SERVICIO_NO_DISPONIBLE` | `503` | La base de datos PostgreSQL no responde en `/v1/salud/listo`. |

---

## 2. Endpoints Públicos (Sin Autenticación Requerida)

### 2.1 Salud y Diagnóstico
- **`GET /v1/salud`**
  - *Respuesta 200 OK*:
    ```json
    { "estado": "ok", "version": "1.0.0", "entorno": "local" }
    ```
- **`GET /v1/salud/listo`**
  - Verifica conectividad real con PostgreSQL (`200 OK` o `503 SERVICIO_NO_DISPONIBLE`) e informa el estado de Redis (`conectado`/`ok` o `degradado`).
  - *Respuesta 200 OK*:
    ```json
    { "estado": "listo", "bd": "conectado", "cache": "conectado" }
    ```

### 2.2 Catálogo de Productos y Búsqueda
- **`GET /v1/categorias`**
  - Lista las 10 categorías de la canasta familiar ordenadas por `orden`.
- **`GET /v1/productos?categoria_id=1&q=arroz&limite=24&cursor=`**
  - Búsqueda difusa y listado paginado por `cursor` tolerante a errores ortográficos, tildes y fracciones (`pg_trgm` + `unaccent` + `unidades.parsear_cantidad`).
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

### 2.4 Establecimientos, Solicitud Pública de Corrección y Legal
- **`GET /v1/establecimientos?q=&tipo=&municipio=Armenia&lat=4.5350&lng=-75.6750&radio_km=5.0`**
  - Filtra por cercanía con PostGIS y calcula `distancia_m` en memoria sin persistir ni registrar `lat`/`lng` en logs.
- **`GET /v1/establecimientos/{id}`**
  - Ficha del establecimiento, sus precios vigentes paginados y sus promociones activas.
- **`POST /v1/establecimientos/{id}/solicitudes-correccion`**
  - Formulario público con *honeypot* (`{ "correo": "...", "mensaje": "...", "sitio_web_trampa": "" }`) para reportar datos erróneos del negocio. Genera un caso de moderación `solicitud_correccion`.
- **`GET /v1/legal/politica-tratamiento`**
  - Devuelve la versión vigente de la política de tratamiento de datos personales (Ley 1581 de 2012), su texto íntegro y el correo oficial de contacto (`CONTACTO_LEGAL_EMAIL`).

---

## 3. Endpoints Autenticados (Reportantes y Titulares de Datos)

### 3.1 Gestión de Cuenta y Ley 1581
- **`POST /v1/mi-cuenta/autorizacion`**
  - Crea `perfil` y registra el consentimiento previo, expreso e informado en `autorizacion_datos`. Exigido antes de cualquier reporte (`403 AUTORIZACION_REQUERIDA` si falta).
  - *Cuerpo*: `{ "alias": "juan_armenia", "version_politica": "1.0", "acepta": true }`
- **`GET /v1/mi-cuenta`**: Consulta datos personales del perfil, reputación, contadores ($A$, $M$) y fecha de autorización (Ley 1581 art. 8).
- **`PATCH /v1/mi-cuenta`**: Modifica alias `{ "alias": "nuevo_alias" }`.
- **`DELETE /v1/mi-cuenta`**: Derecho de supresión (`FR-007`). Anonimiza reportes (`reportante_id = null`, `foto_prueba_path = null`), borra fotos del bucket, asigna alias `'eliminado_' || left(id::text, 8)`, cambia `estado = 'eliminada'`, marca `revocada_en = now()` en `autorizacion_datos` y borra la credencial en Supabase Auth.

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

## 6. Matriz de Control de Acceso por Roles (RBAC — Verificada en `T-51`)

| Grupo de Endpoints | Anónimo (sin JWT) | Reportante (sin autorizar Ley 1581) | Reportante (`activa`) | Comercio (`activa` y `verificado`) | Moderador (`activa`) | Cuenta `suspendida` o `bloqueada` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `GET /v1/salud*`, `/categorias`, `/productos/*`, `/establecimientos/*`, `/legal/*` | `200` | `200` | `200` | `200` | `200` | `200` |
| `POST /v1/establecimientos/{id}/solicitudes-correccion` | `201` | `201` | `201` | `201` | `201` | `201` |
| `POST /v1/mi-cuenta/autorizacion` | `401` | `201` | `200` | `200` | `200` | `403 CUENTA_SUSPENDIDA` |
| `GET /v1/mi-cuenta`, `PATCH /v1/mi-cuenta` | `401` | `403 AUTORIZACION_REQUERIDA` | `200` | `200` | `200` | `403 CUENTA_SUSPENDIDA` (`GET` `200`) |
| `DELETE /v1/mi-cuenta` | `401` | `403 AUTORIZACION_REQUERIDA` | `200` | `200` | `200` | `200` (Derecho de Ley) |
| `POST /v1/reportes`, `/fotos/url-subida`, `/sugerencias-presentacion` | `401` | `403 AUTORIZACION_REQUERIDA` | `201` | `201` | `201` | `403 CUENTA_SUSPENDIDA` |
| `GET /v1/mis-reportes` | `401` | `403 AUTORIZACION_REQUERIDA` | `200` | `200` | `200` | `403 CUENTA_SUSPENDIDA` |
| `POST /v1/comercio/reclamos` *(Etapa 2)* | `401` | `403 AUTORIZACION_REQUERIDA` | `201` | `201` | `201` | `403 CUENTA_SUSPENDIDA` |
| `/v1/comercio/establecimientos/{id}/*` *(Etapa 2)* | `401` | `403 PROHIBIDO` | `403 PROHIBIDO` | `200 / 201` (si es dueño, sino `404`) | `403 PROHIBIDO` | `403 CUENTA_SUSPENDIDA` |
| `/v1/moderacion/*` | `401` | `403 PROHIBIDO` | `403 PROHIBIDO` | `403 PROHIBIDO` | `200 / 201` | `403 CUENTA_SUSPENDIDA` |
| `POST /internal/jobs/{nombre}` | `401` (sin `X-Job-Token`) | `401` | `401` | `401` | `401` | `200` (solo con `X-Job-Token` válido) |
