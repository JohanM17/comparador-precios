# ADR-002: Monolito Modular frente a Microservicios y frente a BaaS sin Backend

## Estado
Aceptado

## Contexto
El sistema gestiona múltiples capacidades funcionales: catálogo normalizado, reporte de precios, detección de anomalías, moderación, autenticación y módulo comercial. Una arquitectura de microservicios introduce sobrecostos de red, transacciones distribuidas y complejidad operativa innecesaria para un equipo pequeño. Por otro lado, un Backend-as-a-Service (BaaS) directo desde el cliente (cliente web directo a Supabase) expone la lógica de negocio a manipulaciones y dificulta la neutralidad comercial y el cálculo de métricas complejas.

## Alternativas consideradas
1. **Microservicios (servicios separados de catálogo, precios, moderación):** Alta complejidad de despliegue, latencia inter-servicio perjudicial para `EC-02` (< 60 s) y costo en nube fuera de la restricción de presupuesto cero.
2. **Arquitectura BaaS directa (Next.js conectando directo a Supabase PostgREST):** Imposibilita la neutralidad comercial en el cliente, fragmenta las validaciones de anomalías y dispersa la lógica en funciones SQL complejas difíciles de auditar con TDD.
3. **Monolito Modular Hexagonal (FastAPI con módulos desacoplados):** Un único proceso de despliegue con límites modulares estrictos verificados por `import-linter`, dominio puro aislado de I/O y base de datos relacional compartida.

## Decisión
Construir un **Monolito Modular** en FastAPI organizado en módulos de aplicación (`catalogo`, `precios`, `confianza`, `moderacion`, `cuentas`, `comercial`) que se comunican mediante puertos y servicios internos de dominio, sin llamadas HTTP internas ni acoplamiento directo entre módulos comerciales y de precios (`EC-06`).

## Consecuencias
### Positivas
- Despliegue simple y de bajo costo en una única instancia de contenedor.
- Cero sobrecosto de latencia de red entre módulos para cálculos de comparación.
- Garantía de fronteras arquitectónicas verificables estáticamente con `import-linter`.
- Transaccionalidad ACID nativa en PostgreSQL para la actualización de `precio_vigente`.

### Negativas
- Escalamiento horizontal del monolito completo en lugar de módulos individuales (mitigado por la caché L1/L2 en Redis).
