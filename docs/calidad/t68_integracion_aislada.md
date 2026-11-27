# T-68 — Integración EC-02/EC-06 en base aislada

**Fecha**: 27 de noviembre de 2026
**Commit**: `45aedc5` (`develop`)
**Entorno**: Supabase `comparador_pruebas`, base aislada del proyecto oficial; sin Docker.

## Comando

```bash
backend/.venv/bin/python scripts/integracion_aislada.py --recrear --con-semilla
```

El runner valida que la URL de BD y `SUPABASE_URL` pertenezcan al mismo proyecto
(`dohoqojhrxlduswekkwn`), crea la base `comparador_pruebas`, aplica las migraciones,
ejecuta `scripts/semilla.py` y corre toda la suite `backend/tests/integracion/`.

## Preparación

| Elemento | Resultado |
| :--- | :--- |
| Migraciones | `0001`, `0002`, `0003`, `0005`, `0006`, `0007` (0004 no existe por renumeración de A2) |
| Categorías | 10 |
| Productos | 128 |
| Presentaciones | 156 |
| Alias | 56 |
| Establecimientos | 30 |
| `precio_vigente` | 624 |

## Resultado de la suite

| Métrica | Resultado |
| :--- | :--- |
| Pruebas | **107 passed, 1 skipped, 0 failed** |
| Tiempo de pytest | **1 379,58 s (22:59)** |
| Skip | `test_semilla_historial_idempotente_en_bd` (opt-in que escribe datos demo) |
| Avisos | 1 warning externo de Starlette/httpx |

## EC-02 — actualidad con precio oficial

`backend/tests/integracion/test_ec02_ec06_etapa2.py` ejecuta 100 comparaciones
reales con un precio oficial activo y caché invalidada en cada iteración.

| Métrica | Resultado | Límite |
| :--- | :--- | :--- |
| Cumplimiento | 100/100 | 100 % |
| p95 | **2 174,08 ms** | 60 000 ms |
| Máximo | 2 620,92 ms | — |
| Sello | `oficial` y `precio_oficial_cop` en las 100 | — |

## EC-06 — neutralidad con promociones activas

El mismo archivo siembra tres promociones vigentes (porcentaje, precio especial y
pague/ lleve) y compara la respuesta con y sin ellas.

| Comprobación | Resultado |
| :--- | :--- |
| Orden de `resultados` | Idéntico: `[1000, 1250, 1500, 2000]` |
| Contenido de `resultados` | Idéntico, incluidos sello, motivo y precios |
| Bloque `promociones` | Separado, con `es_promocion = true` |
| `import-linter` | 3 contratos, 0 roto (`precios` no importa `comercial`) |

## Migración `0007`

La prueba de integración verifica que un contraste válido de $1.000 contra
$200.000 persiste `diferencia_pct = 199.0000` en `precio_vigente` sin
`numeric field overflow`. La columna quedó en `numeric(14,4)` y la migración
está aplicada en la base compartida:

```
0001, 0002, 0003, 0005, 0006, 0007
```

## Limpieza

La suite terminó en verde. El runner no eliminó automáticamente la base porque
el guard detectó 3 conexiones idle de Supavisor; se eliminó manualmente con
`DROP DATABASE ... WITH (FORCE)`. Es una limitación del runner, no un fallo de
T-68. Queda como follow-up que `--force` use `WITH (FORCE)` para el cierre.

## Residuales documentados (no bloquean T-68)

- Carrera de actualización entre publicación oficial y reporte comunitario en la
  ruta batch de reconstrucción; el siguiente recálculo la corrige.
- Primera publicación de una tienda sin ningún `precio_vigente` y baja lógica de
  un precio oficial: pendientes de producto/UI.
- Límites y zona horaria de promociones, paginación de reclamos, índice único
  parcial para casos de disputa duplicados, N+1 de reputación, `commit()` del
  refresco de disputa y borrado de Auth best-effort.
- Operación: staging con `SIMULAR_LATENCIA_MS=3000`, contact point de la alerta
  SLO y panel de latencia de BD.

## Conclusión

T-68 queda **verde**: EC-02 con precio oficial cumple 100/100 y p95 muy por
debajo de 60 s; EC-06 con promociones activas conserva el orden y separa las
promociones; la migración `0007` elimina el overflow. La promoción puede pasar
al gate final de `main`.
