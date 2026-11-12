# ADR-004: Frontend en Next.js con Cliente Tipado OpenAPI y Cero Lógica de Negocio

## Estado
Aceptado

## Contexto
El frontend del comparador debe ser veloz, accesible (WCAG 2.2 AA) y confiable en dispositivos móviles de gama baja con conectividad intermitente. Además, existe la regla innegociable de neutralidad comercial y exactitud numérica: el ordenamiento por precio unitario base, el cálculo de sellos de confianza y las validaciones de vigencia no pueden delegarse al navegador del usuario, donde pueden ser alteradas o generar inconsistencias entre clientes.

## Alternativas consideradas
1. **SPA tradicional (Vite + React SPA):** Renderizado exclusivo en cliente, bundle inicial pesado y SEO nulo para la consulta de productos de la canasta familiar.
2. **Frontend con lógica compartida (cálculo de precios en cliente):** Duplicación de reglas de negocio en Python y TypeScript, riesgo de discrepancias numéricas y vulnerabilidad ante manipulación de rankings en el cliente.
3. **Next.js (App Router) con cliente generado desde OpenAPI:** Renderizado del servidor y cliente híbrido, bundle mínimo optimizado, hidratación rápida y consumo de una API REST fuertemente tipada con cero lógica de negocio en cliente.

## Decisión
Utilizar **Next.js 14+ (App Router)** con TypeScript en modo estricto (`"strict": true`) y Tailwind CSS. El frontend opera exclusivamente como una **capa de presentación declarativa**: consume la API de FastAPI a través de un cliente generado desde `docs/api/openapi.json`. Ningún cálculo de precio por unidad, vigencia, sello o anomalía se ejecuta en el navegador; el cliente únicamente renderiza las respuestas del backend.

## Consecuencias
### Positivas
- Cero desincronización entre el modelo matemático del backend y la interfaz visual.
- Rendimiento de carga inicial optimizado (Server Components y First Load JS < 100 kB).
- Detección temprana en tiempo de compilación (`tsc --noEmit`) ante cualquier cambio de contrato en la API.
- Imposibilidad de alterar la neutralidad comercial manipulando scripts en el cliente.

### Negativas
- Dependencia del endpoint `/v1/productos/{id}/comparacion` para cualquier cambio en la vista de resultados.
