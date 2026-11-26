# EC-05 — Análisis de impacto y estimación previa del módulo comercial

**Tarea:** `T-60` del plan de construcción. **Entregable 10, parte 1.**
**Fecha de registro:** 26 de noviembre de 2026.
**Regla:** este archivo debe estar confirmado en Git **antes** del commit de `T-61`
(migración `0004_modulo_comercial.sql`). El historial es la evidencia.

> EC-05 mide la capacidad de la arquitectura para evolucionar: «se incorpora el módulo comercial
> sobre el núcleo construido en el corte 2; se registran los componentes modificados y el
> esfuerzo real frente al estimado; el núcleo no requiere rediseño estructural». Este documento
> fija la predicción. El documento `ec05-resultado.md` (`T-69`) la contrasta con lo que pasó.

---

## 1. Qué dejó preparado el núcleo

El núcleo se diseñó dejando exactamente **tres ganchos** y ninguna tabla comercial (decisión
`D-14`, `ADR-013`). Antes de estimar se verificó que los tres existen y funcionan:

| Gancho | Dónde está hoy | Estado verificado |
| :--- | :--- | :--- |
| Puerto `PoliticaPrecioReferencia` | `backend/app/puertos/politica_precio.py` | Protocolo definido, con `SoloUsuarios` como implementación de Etapa 1. Ya se inyecta por constructor en `ServicioPrecios` y en `servicio_casos`, con valor por omisión. |
| Columna `establecimiento.comercio_id` | `supabase/migrations/0002`, línea 82; clave foránea en `0003`, línea 21 | Columna anulable con clave foránea a `perfil(id)` y `on delete set null`. |
| Arreglo `promociones` separado | `backend/app/modulos/precios/servicio_comparacion.py`, línea 244 | Se emite `promociones=[]` desde el núcleo, ya separado de `resultados`. |

Además, y esto reduce el esfuerzo estimado de forma apreciable, el núcleo ya sembró:

- Los valores `oficial` y `en_disputa` en el enumerado `sello_precio`.
- Los valores `verificacion_comercio` y `disputa_precio` en el enumerado `tipo_caso`.
- El enumerado `estado_verificacion` (`sin_dueno`, `pendiente`, `verificado`) y el rol `comercio`.
- El valor `comercio` en el enumerado `fuente_precio`.
- Los parámetros `disputa.min_reportes_y_cuentas` y `disputa.ventana_y_diferencia` en
  `config_parametro` (`0002`, líneas 166 y 167), con los valores que fija `D-01`.
- La presentación de los sellos `oficial` y `en_disputa` en el frontend
  (`SelloConfianza.tsx` y `FilaPrecio.tsx`), incluido el bloque que muestra los dos precios.

**Consecuencia para la estimación:** la Etapa 2 no necesita ningún cambio de tipo enumerado ni
de presentación de sellos. Ese trabajo ya está hecho y no vuelve a pagarse.

---

## 2. Qué cuenta como «rediseño estructural»

La medida de EC-05 dice que el núcleo no debe requerir rediseño estructural. Para que la
afirmación sea verificable y no una opinión, el equipo declara **antes** de construir qué
contaría como rediseño:

1. Modificar o eliminar una columna existente de una tabla del núcleo. Agregar columnas nuevas
   no cuenta: es aditivo.
2. Cambiar la firma del protocolo `PoliticaPrecioReferencia`.
3. Modificar cualquier módulo de `backend/app/dominio/` existente para que el módulo comercial
   funcione.
4. Invertir o romper la dirección de dependencias: que `precios` tenga que importar `comercial`.
5. Cambiar de forma incompatible el contrato de un endpoint ya publicado en `/v1`.

**Predicción del equipo: cero de los cinco.** Si alguno ocurre, se documenta sin maquillarlo; la
guía valora que una decisión inadecuada se identifique y se corrija, no que nunca ocurra.

---

## 3. Registro de análisis de impacto (plantilla 8.3)

### 3.1 Base de datos

| Componente | Tipo de cambio | Est. (h) | Real (h) | Observaciones |
| :--- | :--- | ---: | ---: | :--- |
| `supabase/migrations/0004_modulo_comercial.sql` | nuevo | 4 | | Aditiva: enumerado `tipo_promocion`, tablas `solicitud_verificacion_comercio`, `precio_oficial` y `promocion`, y tres columnas nuevas en `precio_vigente`. No altera ni borra nada existente. |
| `establecimiento.comercio_id` | sin cambio | 0 | | Ya existe desde `0002` con su clave foránea. |
| Enumerados `sello_precio`, `tipo_caso`, `estado_verificacion`, `fuente_precio` | sin cambio | 0 | | Ya contienen todos los valores de Etapa 2. |
| `config_parametro` (parámetros de disputa) | sin cambio | 0 | | Ya sembrados en `0002`. |

### 3.2 Dominio puro

| Componente | Tipo de cambio | Est. (h) | Real (h) | Observaciones |
| :--- | :--- | ---: | ---: | :--- |
| `backend/tests/unitarias/test_contraste.py` | nuevo | 5 | | TDD: se escribe antes que `contraste.py`. |
| `backend/app/dominio/contraste.py` | nuevo | 5 | | Regla `D-01` pura: decide entre precio oficial y mediana comunitaria, y determina el sello. Sin entrada ni salida. |
| `backend/tests/unitarias/test_promocion.py` | nuevo | 4 | | TDD. |
| `backend/app/dominio/promocion.py` | nuevo | 4 | | Validación de la Ley 1480 (condiciones y vigencia) y cálculo informativo del ahorro. No toca el orden. |
| `backend/app/dominio/parametros.py` | modificado | 1 | | Cuatro campos nuevos de disputa leídos de las dos claves compuestas ya sembradas. |
| `sello.py`, `vigencia.py`, `orden.py`, `unidades.py`, `anomalia.py`, `riesgo.py`, `reputacion.py` | **sin cambio** | **0** | | **Ningún módulo de dominio existente se modifica. Es el indicador central de EC-05.** |

### 3.3 Puertos

| Componente | Tipo de cambio | Est. (h) | Real (h) | Observaciones |
| :--- | :--- | ---: | ---: | :--- |
| `backend/app/puertos/politica_precio.py` | modificado | 6 | | Se **agrega** la clase `OficialConContraste`. El protocolo no cambia de firma y `SoloUsuarios` queda intacta. |

### 3.4 Módulo comercial (nuevo)

| Componente | Tipo de cambio | Est. (h) | Real (h) | Observaciones |
| :--- | :--- | ---: | ---: | :--- |
| `backend/app/modulos/comercial/esquemas.py` | nuevo | 3 | | |
| `backend/app/modulos/comercial/repositorio.py` | nuevo | 6 | | |
| `backend/app/modulos/comercial/servicio.py` | nuevo | 8 | | Reclamo, verificación, lote de precios, «Todo sigue igual» y promociones. |
| `backend/app/modulos/comercial/api.py` | nuevo | 6 | | Rutas bajo `/v1/comercio` y la de verificación bajo `/v1/moderacion/comercios`. |

### 3.5 Módulos existentes que se tocan

| Componente | Tipo de cambio | Est. (h) | Real (h) | Observaciones |
| :--- | :--- | ---: | ---: | :--- |
| `backend/app/modulos/moderacion/servicio_casos.py` | modificado | 3 | | Resolución de casos `verificacion_comercio` y `disputa_precio`. |
| `backend/app/modulos/precios/servicio_comparacion.py` | modificado | 4 | | Llena el arreglo `promociones` y el campo `precio_oficial_cop`, ya reservados. |
| `backend/app/modulos/precios/esquemas.py` | modificado | 1 | | Los campos ya estaban en el contrato; se activan. |
| `backend/app/main.py` | modificado | 1 | | Registrar el router comercial. |
| `backend/pyproject.toml` (`import-linter`) | modificado | 1 | | Contrato que prohíbe `precios` → `comercial`, que es lo que protege EC-06. |

### 3.6 Pruebas y contrato

| Componente | Tipo de cambio | Est. (h) | Real (h) | Observaciones |
| :--- | :--- | ---: | ---: | :--- |
| `backend/tests/integracion/test_verificacion_comercio.py` | nuevo | 4 | | `FR-022`. |
| `backend/tests/integracion/test_promociones_ley1480.py` | nuevo | 4 | | `FR-024` y `FR-025`. |
| `backend/tests/integracion/test_ec02_ec06_etapa2.py` | nuevo | 5 | | Reejecuta EC-02 con precio oficial y EC-06 con promociones activas. |
| `backend/tests/contrato/` | modificado | 3 | | Contratos de las rutas nuevas. |
| `docs/api/openapi.json` | modificado | 0,5 | | Regenerado; el CI ya verifica que esté sincronizado. |

### 3.7 Frontend

| Componente | Tipo de cambio | Est. (h) | Real (h) | Observaciones |
| :--- | :--- | ---: | ---: | :--- |
| `frontend/src/lib/api/esquema.d.ts` y `clienteApi.ts` | modificado | 2 | | Cliente tipado regenerado del contrato. |
| `frontend/src/app/gestion/page.tsx` | modificado | 4 | | Tres pestañas nuevas visibles solo con rol `comercio`. |
| `frontend/src/components/comercio/PestanaMisTiendas.tsx` | nuevo | 4 | | |
| `frontend/src/components/comercio/PestanaPreciosRapido.tsx` | nuevo | 7 | | Modo rápido (`D-06`) con el botón «Todo sigue igual». Es la pantalla con más interacción del módulo. |
| `frontend/src/components/comercio/PestanaPromociones.tsx` | nuevo | 6 | | Formulario con las condiciones que exige la Ley 1480. |
| `frontend/src/components/BloquePromociones.tsx` | modificado | 2 | | Ya existe; se conecta a datos reales. |
| `SelloConfianza.tsx`, `FilaPrecio.tsx` | **sin cambio** | **0** | | Ya muestran `oficial` y `en_disputa`, incluido el contraste de los dos precios. |
| `frontend/tests/e2e/flujo_comercio.spec.ts` | nuevo | 4 | | Criterio de `T-67`: 20 precios en modo rápido en menos de un minuto. |

### 3.8 Total

| Bloque | Est. (h) | Real (h) |
| :--- | ---: | ---: |
| Base de datos | 4 | |
| Dominio puro | 19 | |
| Puertos | 6 | |
| Módulo comercial | 23 | |
| Módulos existentes | 10 | |
| Pruebas y contrato | 16,5 | |
| Frontend | 29 | |
| **Total** | **107,5** | |

Para 4 integrantes son unas 27 horas-persona. El módulo comercial es, por sí solo, más grande
que toda la ampliación del Anexo 1 (88,5 h estimadas), y conviene tenerlo presente al repartir
el trabajo de las dos semanas.

---

## 4. Riesgos identificados antes de construir

| Riesgo | Prob. | Impacto | Mitigación |
| :--- | :--- | :--- | :--- |
| La política `OficialConContraste` duplica el SQL de `SoloUsuarios` y las dos se desincronizan | alta | medio | Extraer el `UPSERT` de `precio_vigente` a una función compartida del adaptador antes de escribir la segunda política. |
| El módulo comercial y la canasta (A1) tocan `precios/esquemas.py` y `api.py` a la vez | alta | medio | Ramas cortas y orden acordado: comercial primero, canasta después, porque la canasta lee el precio oficial y no al revés. |
| Un comercio publica un precio oficial falso y bajo para aparecer primero | media | alto | La regla `D-01` ya lo cubre: tres reportes de dos cuentas con 10 % de diferencia bastan para pasar a `en_disputa` y posicionar con el precio de la comunidad. |
| Recalcular el precio vigente en lotes de 200 precios bloquea la tabla | media | medio | Un lote por transacción con `UPSERT` y recálculo por par; se mide en `test_ec02_ec06_etapa2.py`. |
| Las promociones alteran el orden por un descuido | baja | muy alto | `import-linter` impide la importación y la prueba de EC-06 compara el orden con y sin promociones. |

---

## 5. Cierre: contraste estimado contra real

Se diligencia en `ec05-resultado.md` (`T-69`).

| Indicador | Predicción | Real |
| :--- | :--- | :--- |
| Esfuerzo total | 107,5 h | |
| Columnas del núcleo modificadas o eliminadas | 0 | |
| Cambios en la firma del puerto | 0 | |
| Módulos de dominio existentes modificados | 0 | |
| Importaciones `precios` → `comercial` | 0 | |
| Rupturas de contrato en `/v1` | 0 | |
