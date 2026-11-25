# Data Model — Ampliación Corte 3 (A2 + B1)

**Feature**: `002-ampliacion-corte3` | **Date**: 2026-11-25

Este documento describe las entidades, los DTOs y las estructuras de datos de la ampliación. No se crean tablas nuevas; se reutiliza `reporte_precio` y se añade un índice.

## 1. Modelo de datos existente reutilizado

### 1.1 `reporte_precio` (fuente de verdad append-only)

| Columna | Tipo | Uso en A2 |
|---|---|---|
| `id` | `uuid` | Identificador del punto de la serie. |
| `producto_id` | `uuid` | Filtro de la serie. |
| `establecimiento_id` | `uuid` | Filtro de la serie. |
| `presentacion_id` | `uuid` | Presentación del punto; opcional en la consulta. |
| `precio_cop` | `integer` | Precio del punto en COP. |
| `cantidad_base_snapshot` | `numeric(14,3)` | Cantidad base congelada; permite recalcular el precio por unidad. |
| `precio_por_base` | `numeric(14,6)` | Precio por unidad base congelado. |
| `fuente` | `fuente_precio` (`usuario`, `comercio`, `semilla`) | Origen del punto. |
| `observado_en` | `timestamptz` | Fecha de observación; orden y ventana de 90 días. |
| `estado` | `estado_confianza` (`aceptado`, `dudoso`, `rechazado`) | Confiabilidad del punto. |
| `es_demo` | `boolean` | Marca de datos de demostración. |
| `reportante_id` | `uuid` | **No se expone** en la API. |
| `huella_red` | `text` | **No se expone** en la API. |
| `foto_prueba_path` | `text` | **No se expone** en la API. |

### 1.2 `precio_vigente` (proyección actual)

No se usa para la serie histórica. Se mantiene para la comparación vigente y no se modifica por A2.

### 1.3 Índice propuesto

```sql
-- 0005_historial_precios.sql
create index if not exists idx_reporte_historial_serie
  on public.reporte_precio (producto_id, establecimiento_id, observado_en desc)
  where estado in ('aceptado', 'dudoso');
```

Justificación: la consulta filtra por producto, establecimiento y ventana de 90 días, y ordena por fecha. El índice parcial reduce el tamaño y excluye los rechazados.

## 2. Entidades de dominio y DTOs

### 2.1 `PuntoSeriePrecio`

Representa una observación histórica visible en la serie.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | `UUID` | Identificador del reporte. |
| `observado_en` | `datetime` (UTC) | Obligatorio; dentro de la ventana. |
| `precio_cop` | `int` | Entero > 0. |
| `precio_por_base` | `Decimal` | > 0, calculado con la cantidad base. |
| `precio_por_unidad` | `PrecioUnidad` | Valor entero y unidad visualizable (`kg`, `l`, `unidad`). |
| `origen` | `OrigenPrecio` | `usuario`, `comercio`, `semilla`. |
| `estado` | `EstadoSerie` | `aceptado`, `dudoso`. |
| `es_demo` | `bool` | Conserva la marca de demostración. |
| `presentacion_id` | `UUID` | Presentación asociada. |
| `cantidad_base` | `Decimal` | Cantidad base de la presentación. |

Invariantes:

- `precio_cop` y `precio_por_base` son consistentes con `cantidad_base`.
- `estado` nunca es `rechazado` en la respuesta.
- No hay campos de identidad, foto, red ni coordenadas.

### 2.2 `SeriePrecios`

| Campo | Tipo | Regla |
|---|---|---|
| `producto` | `ProductoSerie` | `id`, `nombre`, `unidad_base`, `unidad_visualizacion`. |
| `establecimiento` | `EstablecimientoSerie` | `id`, `nombre`, `municipio`. |
| `presentacion` | `PresentacionSerie \| null` | Si se filtró por presentación. |
| `desde` | `datetime` (UTC) | Inicio de la ventana (por defecto `hasta - 90 días`). |
| `hasta` | `datetime` (UTC) | Fin de la ventana (por defecto ahora). |
| `puntos` | `list[PuntoSeriePrecio]` | Ordenados ascendentemente. |
| `total` | `int` | Número de puntos devueltos. |
| `truncado` | `bool` | `true` si hay más de los devueltos. |
| `datos_de_demostracion` | `bool` | `true` si algún punto tiene `es_demo`. |

### 2.3 Enumeraciones

- `OrigenPrecio`: `usuario` (reportado), `comercio` (oficial), `semilla` (pública/demostración).
- `EstadoSerie`: `aceptado`, `dudoso`.
- `UnidadVisualizacion`: `kg`, `l`, `unidad`.

### 2.4 Reglas de selección de la serie (dominio puro)

Función principal propuesta:

```python
def construir_serie(
    reportes: Sequence[ReporteSerie],
    *,
    desde: datetime,
    hasta: datetime,
    unidad_base: UnidadBase,
    limite: int,
) -> ResultadoSerie:
    ...
```

Reglas:

1. Incluir solo reportes con `desde <= observado_en <= hasta`.
2. Excluir `estado == "rechazado"`.
3. Incluir `aceptado` y `dudoso`.
4. Ordenar por `observado_en` ascendente y, en empate, por `id` estable.
5. Calcular `precio_por_unidad` con `Decimal` y la unidad base.
6. Aplicar el límite; si hay más, `truncado = True`.
7. Calcular `datos_de_demostracion` si algún punto tiene `es_demo`.
8. No leer ni propagar `reportante_id`, `huella_red`, `foto_prueba_path`, `lat` o `lng`.

Casos de prueba TDD obligatorios:

- Ventana exacta de 90 días: incluye el límite y excluye 90 días + 1 segundo.
- Punto en el futuro: excluido (o rechazado por validación de la consulta).
- `aceptado` y `dudoso` incluidos; `rechazado` excluido.
- Orden ascendente con empate de fecha.
- `truncado` con más puntos que el límite.
- `datos_de_demostracion` con un solo `es_demo`.
- Unidad `g` → `kg`; `ml` → `l`; `unidad` → `unidad`.
- Sin datos → serie vacía, no `None`.
- Entrada con campos prohibidos → no se copian al DTO.

## 3. Contrato de respuesta (resumen)

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

## 4. Modelo de telemetría (B1)

### 4.1 Atributos permitidos

| Atributo | Tipo | Uso |
|---|---|---|
| `http.request.method` | string | Método HTTP. |
| `http.route` | string | Ruta plantilla, no URL concreta. |
| `http.response.status_code` | int | Estado de respuesta. |
| `url.scheme` | string | `http`/`https`. |
| `service.name` | string | `comparador-precios-backend`. |
| `service.version` | string | Versión del backend. |
| `deployment.environment` | string | `local`, `staging`, `production`. |
| `cache_hit` | bool | Acierto de L1/L2 en comparación. |
| `db_ms` | float | Duración de la consulta SQL. |
| `resultados_count` | int | Número de resultados de comparación. |
| `estado` | string | `aceptado`/`dudoso` en el registro. |
| `fuente` | string | `usuario`/`comercio`/`semilla`. |

### 4.2 Atributos prohibidos

`lat`, `lng`, `reportante_id`, `alias`, `email`, `ip`, `huella_red`, `foto_prueba_path`, `authorization`, `cookie`, `set-cookie`, `request.body`, `response.body`.

### 4.3 Métricas mínimas

- `http.server.request.duration` (histograma, segundos) por ruta y estado.
- `http.server.request.count` (contador) por ruta y estado.
- `cache.hit` / `cache.miss` (contador) para comparación.
- `db.query.duration` (histograma) para las consultas de precios.
- `precio.reportes` (contador) por `estado` y `fuente`.

### 4.4 SLO

| Campo | Valor |
|---|---|
| Servicio | `comparador-precios-backend` |
| Indicador (SLI) | Proporción de `GET /v1/productos/{id}/comparacion` con duración ≤ 2 s y estado ≠ 5xx |
| Meta | 99,0 % |
| Ventana | 7 días móviles |
| Presupuesto de error | 1,0 % |
| Alerta | Consumo de presupuesto > 50 % en 1 h o burn rate > 2× en ventanas 5m/1h |
| Notificación | Correo/Slack/Discord del equipo (`PA-05`) |

## 5. Migración y compatibilidad

- `0005_historial_precios.sql`: solo índice; no altera columnas ni datos.
- No se modifica `reporte_precio`, `precio_vigente`, `perfil`, `auditoria` ni `config_parametro`.
- El endpoint es aditivo; no rompe el contrato de comparación.
- La telemetría es opcional y desactivable; no cambia el contrato público.
- La migración de Fase 2 `supervisor_ia` pasa a `0006` cuando se implemente.
