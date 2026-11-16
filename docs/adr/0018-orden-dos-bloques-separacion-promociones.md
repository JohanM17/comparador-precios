# ADR-018: Ordenamiento en Dos Bloques y Separación Estructural de Promociones (EC-06)

## Estado
Aceptado

## Contexto
El objetivo esencial de la plataforma es brindar transparencia de precios de la canasta familiar a los consumidores de Armenia, sin permitir que comercios paguen o coloquen ofertas que desplacen del primer lugar a los establecimientos con precios reales más económicos. El escenario `EC-06` exige que el ordenamiento de resultados sea 100 % neutral y que ninguna promoción comercial altere la posición de los resultados orgánicos. Asimismo, los precios no confirmados o antiguos no deben confundirse con precios frescos y confiables.

## Alternativas consideradas
1. **Lista única ordenada solo por precio nominal:** Muestra precios desactualizados o dudosos al mismo nivel que precios verificados, induciendo al consumidor a errores y viajes inútiles a tiendas.
2. **Mezclar promociones comerciales en los primeros lugares de la grilla:** Viola el principio innegociable de neutralidad comercial y destruye la confianza ciudadana en la herramienta.
3. **Ordenamiento en Dos Bloques por `precio_por_base` con Promociones en Bloque Separado:**
   - **Bloque 1 (Precios Principales y Confiables):** Agrupa establecimientos con sellos `confiable`, `pocos_datos`, `oficial` y `en_disputa`. Se ordenan estrictamente por precio por unidad de medida base (`precio_por_base`: kg, litro o unidad).
   - **Bloque 2 (Precios Secundarios o en Revisión):** Agrupa establecimientos con sellos `dudoso` y `desactualizado` (antigüedad entre 8 y 30 días). Se presentan al final, claramente diferenciados con advertencias visuales.
   - **Bloque `promociones` independiente:** Las ofertas comerciales vigentes se entregan en un arreglo JSON independiente (`"promociones": [...]`), sin alterar ni intercalar filas en `"resultados": [...]`.

## Decisión
Implementar el ordenamiento de comparación en **dos bloques cerrados** clasificados por el valor normalizado `precio_por_base`. Las promociones comerciales se confinan a un bloque JSON separado (`promociones`) con `es_promocion = true`, garantizando el cumplimiento del escenario `EC-06` verificado automáticamente con `import-linter` y pruebas de contrato.

## Consecuencias
### Positivas
- Cumplimiento estricto del principio de neutralidad comercial ciudadana.
- Claridad visual para el consumidor entre precios vigentes confiables y precios desactualizados o sospechosos.
- Comparabilidad justa entre presentaciones de distinto tamaño (ej. bolsa de 500 g vs. bulto de 1 kg).

### Negativas
- Establecimientos con precios desactualizados se desplazan al Bloque 2 hasta que un usuario o comercio actualice el reporte.
