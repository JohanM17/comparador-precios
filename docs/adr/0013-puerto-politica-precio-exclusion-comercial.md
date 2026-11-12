# ADR-013: Puerto PoliticaPrecioReferencia y Exclusión Comercial en el Núcleo (EC-05)

## Estado
Aceptado

## Contexto
El escenario de calidad `EC-05` (evaluado en el Corte 2) exige que la incorporación completa del Módulo Comercial (precios oficiales publicados por supermercados y promociones) se desarrolle sin modificar la arquitectura base del núcleo, sin rediseñar la base de datos de precios y con un esfuerzo real $\le 1.25 \times$ el esfuerzo estimado. Si el núcleo nace acoplado al concepto de comercios o promociones, la neutralidad comercial se compromete desde el inicio.

## Alternativas consideradas
1. **Modelar precios oficiales y promociones desde la Etapa 1:** Contamina el núcleo con lógica no validada, dificulta la medición objetiva del cambio en `EC-05` y viola el principio de desarrollo incremental SDD.
2. **Crear una bifurcación de código separada para la Etapa 2:** Deuda técnica severa y duplicidad de mantenimiento.
3. **Diseñar puntos de extensión limpios en el núcleo (Arquitectura Hexagonal):**
   - Puerto `PoliticaPrecioReferencia` en el dominio: en Etapa 1 usa la estrategia `SoloUsuarios` (ignora comercio). En Etapa 2 se inyecta la estrategia `OficialConContraste` (`D-01`) sin tocar el cálculo de vigencia ni el ordenamiento.
   - En base de datos: columna nula `establecimiento.comercio_id` y arreglo `"promociones": []` reservado en el contrato OpenAPI.
   - Prohibición arquitectónica: el módulo `precios` jamás importa a `comercial` (`EC-06`).

## Decisión
Excluir las tablas comerciales (`comercio`, `promocion`) del esquema de la Etapa 1 y definir en el dominio puro el puerto abstracto **`PoliticaPrecioReferencia`**. En la Etapa 1 se provee la implementación **`SoloUsuarios`**. El núcleo queda sellado para permitir la integración posterior de la Etapa 2 mediante herencia de estrategias y migraciones puramente aditivas.

## Consecuencias
### Positivas
- Medición objetiva del impacto de cambio arquitectónico para el escenario `EC-05`.
- Aislamiento total de la lógica de precios respecto a intereses comerciales.
- Verificación estática con `import-linter` en el pipeline de CI para asegurar neutralidad (`EC-06`).

### Negativas
- Requiere abstracciones adicionales (puertos y fábricas de políticas) en el dominio desde la fase inicial.
