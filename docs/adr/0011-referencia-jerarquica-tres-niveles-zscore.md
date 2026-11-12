# ADR-011: Conjunto de Referencia Jerárquico en 3 Niveles y Z-Score Modificado (EC-03)

## Estado
Aceptado

## Contexto
El escenario `EC-03` exige detectar determinísticamente reportes anómalos o intentos de manipulación de precios con una tasa de acierto individual $\ge 90\,\%$, grupal $\ge 70\,\%$ y falsas alarmas $\le 10\,\%$. Un producto nuevo o una presentación poco común puede no contar con suficientes reportes previos en una tienda específica para calcular estadísticas confiables; en tal caso, recurrir a una media simple o descartar el reporte genera sesgos graves.

## Alternativas consideradas
1. **Z-score clásico basado en media aritmética y desviación estándar:** Altamente sensible a valores atípicos extremos (*outliers*); un solo precio falso muy alto distorsiona la media y hace pasar los siguientes como válidos.
2. **Umbrales estáticos fijos por producto:** Imposibles de mantener en una economía inflacionaria con más de 150 productos y variaciones continuas de costos.
3. **Z-score modificado con Mediana y MAD sobre conjunto de referencia jerárquico:**
   - Estadística robusta: $M = 0.6745 \cdot (x - m) / \text{MAD}$, donde $m$ es la mediana y $\text{MAD}$ es la desviación absoluta respecto a la mediana.
   - Jerarquía de 3 niveles evaluados en orden:
     * Nivel 1 (`presentacion_tienda`): Misma presentación en el mismo establecimiento.
     * Nivel 2 (`presentacion`): Misma presentación en todas las tiendas de Armenia.
     * Nivel 3 (`producto_unitario`): Todas las presentaciones del producto normalizadas a precio por unidad base.
     * Respaldo (`sin_referencia`): Si ningún nivel alcanza el mínimo de reportes aceptados en la ventana, se asigna estado de respaldo y el reporte pasa a revisión sin descartarse.

## Decisión
Adoptar la **evaluación jerárquica en 3 niveles más respaldo `sin_referencia`** utilizando el **z-score modificado** ($|M| > 3.5$) cuando $n \ge 5$ y $\text{MAD} > 0$, y desviación porcentual respecto a la mediana cuando $n \in \{3, 4\}$ o $\text{MAD} = 0$, conforme a las reglas deterministas de la Sección 5.3 de `PLAN_CONSTRUCCION.md`.

## Consecuencias
### Positivas
- Resistencia matemática probada contra valores atípicos y ataques de distorsión.
- Cobertura universal de evaluación tanto para productos populares como para productos con pocos datos.
- Cumplimiento de las metas de precisión y bajas falsas alarmas exigidas por `EC-03`.

### Negativas
- Requiere consultas de base de datos optimizadas con índices compuestos para obtener el conjunto de referencia en milisegundos.
