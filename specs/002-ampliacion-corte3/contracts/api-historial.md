# API Contract — Historial de Precios y Observabilidad (v1)

**Feature**: `002-ampliacion-corte3` | **Date**: 2026-11-25

Este contrato es aditivo: no modifica los endpoints existentes ni el contrato de comparación.

## 1. Endpoint de historial

### `GET /v1/productos/{id}/historial-precios`

Devuelve la serie histórica de los últimos 90 días de un producto en un establecimiento.

**Autenticación**: pública, igual que la comparación. No requiere JWT.

**Parámetros de ruta**:

| Parámetro | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `id` | UUID | Sí | Identificador del producto. |

**Parámetros de consulta**:

| Parámetro | Tipo | Obligatorio | Defecto | Descripción |
|---|---|---|---|---|
| `establecimiento_id` | UUID | Sí | — | Establecimiento de la serie. |
| `presentacion_id` | UUID | No | — | Filtra una presentación; si se omite, incluye todas las del producto. |
| `desde` | ISO 8601 UTC | No | `hasta - 90 días` | Inicio de la ventana. |
| `hasta` | ISO 8601 UTC | No | ahora | Fin de la ventana. |
| `limite` | int | No | 200 | Máximo de puntos; rango 1 a 500. |

**Reglas**:

- La ventana máxima es de 90 días; un rango mayor devuelve `422 VALIDACION`.
- `desde` no puede ser posterior a `hasta`.
- `establecimiento_id` y `producto_id` deben existir y estar activos; si no, `404 NO_ENCONTRADO`.
- La serie incluye `aceptado` y `dudoso`; excluye `rechazado`.
- La respuesta no incluye datos personales ni coordenadas.
- La respuesta no se cachea por defecto; si se añade caché, TTL ≤ 60 s.

**Respuesta 200 OK**:

```json
{
  "datos": {
    "producto": {
      "id": "3b241101-e2bb-4255-8caf-4136c566a962",
      "nombre": "Arroz blanco",
      "unidad_base": "g",
      "unidad_visualizacion": "kg"
    },
    "establecimiento": {
      "id": "11111111-2222-3333-4444-555555555555",
      "nombre": "Tienda La Esquina",
      "municipio": "Armenia"
    },
    "presentacion": null,
    "desde": "2026-08-27T00:00:00Z",
    "hasta": "2026-11-25T00:00:00Z",
    "puntos": [
      {
        "id": "9f8e7d6c-5b4a-3c2d-1e0f-123456789abc",
        "observado_en": "2026-09-01T14:20:00Z",
        "precio_cop": 2600,
        "precio_por_unidad": { "valor_cop": 5200, "por": "kg" },
        "origen": "usuario",
        "estado": "aceptado",
        "es_demo": false,
        "presentacion_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "cantidad_base": 500.0
      }
    ],
    "total": 1,
    "truncado": false,
    "datos_de_demostracion": false
  }
}
```

**Errores** (`application/problem+json`, RFC 9457):

| Código | HTTP | Cuándo |
|---|---:|---|
| `VALIDACION` | 422 | Parámetros inválidos, rango > 90 días, `desde > hasta`, `limite` fuera de rango. |
| `NO_ENCONTRADO` | 404 | Producto, establecimiento o presentación inexistente o inactivo. |
| `SERVICIO_NO_DISPONIBLE` | 503 | PostgreSQL no responde. |

**Ejemplo de error**:

```json
{
  "type": "https://comparador.armenia.gov.co/errores/validacion",
  "title": "Validación",
  "status": 422,
  "detail": "La ventana máxima del historial es de 90 días.",
  "instance": "/v1/productos/3b241101-e2bb-4255-8caf-4136c566a962/historial-precios",
  "codigo": "VALIDACION",
  "request_id": "req-9f8e7d6c-5b4a-3c2d"
}
```

**OpenAPI**: regenerar `docs/api/openapi.json` con `scripts/exportar_openapi.py` y el cliente tipado con `npm --prefix frontend run gen:api`.

## 2. Contrato de observabilidad (variables de entorno)

No es un endpoint público; es la configuración operativa de B1.

| Variable | Obligatoria | Defecto | Descripción |
|---|---|---|---|
| `OTEL_SDK_DISABLED` | No | `false` | Desactiva toda la telemetría si es `true`. |
| `OTEL_SERVICE_NAME` | No | `comparador-precios-backend` | Nombre del servicio. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Sí (si B1 activo) | — | Endpoint OTLP/HTTP (Grafana Cloud o equivalente). |
| `OTEL_EXPORTER_OTLP_HEADERS` | Sí (si B1 activo) | — | Cabeceras de autenticación; secreto fuera del repositorio. |
| `OTEL_TRACES_SAMPLER` | No | `parentbased_traceidratio` | Estrategia de muestreo. |
| `OTEL_TRACES_SAMPLER_ARG` | No | `0.2` | Proporción de éxitos muestreados; errores al 100 %. |
| `OTEL_METRICS_EXPORTER` | No | `otlp` | Exportador de métricas. |
| `OTEL_LOGS_EXPORTER` | No | `otlp` | Exportador de logs (si se habilita). |
| `SIMULAR_LATENCIA_MS` | No | `0` | Latencia artificial para el simulacro EC-11; solo en entornos de prueba. |
| `ENTORNO` | No | `local` | Si es `production`, la latencia artificial se ignora. |

**Privacidad**: las cabeceras de autorización nunca se registran; los atributos permitidos/prohibidos están en `data-model.md` y se validan con una prueba automatizada.

**Degradación**: si el endpoint OTLP no responde, el exportador usa lotes y timeouts; la API sigue operando. El fallo se registra localmente sin incluir secretos.

## 3. Contrato del simulacro EC-11

1. Configurar `OTEL_EXPORTER_OTLP_*` y `SIMULAR_LATENCIA_MS=3000` en un entorno de prueba.
2. Ejecutar `k6 run infra/k6/ec04_carga.js` o el escenario de comparación.
3. Verificar en el tablero que la latencia supera el SLO y que la alerta se dispara en ≤ 5 minutos.
4. Abrir la traza más lenta y confirmar el span del componente con la latencia inyectada.
5. Guardar captura del tablero, de la alerta y de la traza.
6. Restablecer `SIMULAR_LATENCIA_MS=0`.
