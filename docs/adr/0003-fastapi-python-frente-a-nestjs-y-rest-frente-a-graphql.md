# ADR-003: FastAPI con Python frente a NestJS y API REST frente a GraphQL

## Estado
Aceptado

## Contexto
El núcleo requiere un framework de backend con alto rendimiento asíncrono, tipado estricto, soporte de algoritmos numéricos para detección de anomalías (*z-score*, MAD, medias ponderadas) y contratos de API explícitos para integración con el frontend. Asimismo, se debe elegir el estilo arquitectónico de la interfaz externa (REST vs. GraphQL).

## Alternativas consideradas
1. **Stack Tecnológico: NestJS (Node.js/TypeScript) frente a FastAPI (Python):**
   - *NestJS:* Buen tipado pero las librerías matemáticas y estadísticas de Node.js son limitadas y fragmentadas frente al ecosistema científico de Python (`numpy`, `statistics`, `hypothesis`).
   - *FastAPI:* Rendimiento asíncrono nativo con `uvicorn`/`asyncpg`, tipado estricto con Pydantic v2, generación automática de OpenAPI 3.1 y ecosistema robusto para algoritmos de confianza y TDD con `pytest`.

2. **Estilo de API: GraphQL frente a REST con OpenAPI 3.1:**
   - *GraphQL:* Permite al cliente solicitar campos arbitrarios, pero introduce alta complejidad para:
     * **Caché en Redis (`EC-02` <= 60 s):** Dificulta el almacenamiento en caché de respuestas completas mediante claves deterministas por URL (`cmp:{producto_id}`).
     * **Rendimiento bajo alta concurrencia (`EC-04` con 500 VUs):** El análisis del árbol de consultas (*query parsing/AST*) y problemas de N+1 saturan la CPU del backend gratuito.
     * **Protección y Rate-Limiting (`EC-03`):** Limitar ráfagas por verbo y ruta HTTP (`POST /v1/reportes`) es inmediato en REST, mientras que en GraphQL requiere análisis de complejidad de consultas.
     * **Tipado cliente:** REST con OpenAPI 3.1 permite generar tipos TypeScript estáticos en un solo paso con herramientas estándar de la industria (`openapi-typescript`).

## Decisión
Adoptar **FastAPI (Python 3.12)** con arquitectura asíncrona y una **API REST estandarizada con OpenAPI 3.1**, modelos Pydantic v2 para validación, respuestas de error RFC 9457 (`application/problem+json`) y generación estática de contratos tipados para el frontend.

## Consecuencias
### Positivas
- Validación automática de peticiones y serialización ultra-rápida en C++ (Pydantic Core).
- Facilidad para almacenar en caché consultas por URL en Redis L2 (`GET /v1/productos/{id}/comparacion`).
- Pruebas unitarias matemáticas con `pytest` y pruebas de propiedades con `hypothesis`.
- Rate-limiting y auditoría por ruta HTTP transparentes para seguridad y cumplimiento legal.

### Negativas
- Múltiples endpoints específicos para operaciones complejas en lugar de un único endpoint flexible de GraphQL.
