# ADR-007: Patrón Strategy para Proveedores de IA con Gemini Flash en Fase 2

## Estado
Aceptado

## Contexto
En la Fase 2 (extensión inteligente) se prevén dos capacidades asistidas por Inteligencia Artificial: (A) extracción de producto y precio a partir de fotografías de etiquetas en góndola para acelerar el reporte del usuario (`FR-026`), y (B) un supervisor analítico diario que detecta patrones anómalos complejos y genera reportes consultivos. El sistema no debe acoplarse rígidamente a un modelo o proveedor específico (Gemini, Claude, OpenAI) ni bloquear el flujo central si la API de IA presenta latencia o caída.

## Alternativas consideradas
1. **Llamadas directas al SDK de Google Generative AI en el módulo de precios:** Acoplamiento fuerte, imposibilidad de simular respuestas deterministas en pruebas unitarias y falla en cascada del reporte si la API externa cae.
2. **Microservicio externo de inferencia:** Sobrecosto de infraestructura y latencia añadida.
3. **Patrón Strategy con Puerto Hexagonal (`PuertoProveedorIA`) y Circuit Breaker:** Definición de una interfaz abstracta en el dominio. El adaptador concreto `AdaptadorGeminiFlash` implementa la extracción visual con timeout estricto de 3 segundos; si falla, se conmuta al formulario manual sin interrumpir la operación del usuario.

## Decisión
Diseñar el soporte de IA aplicando el **patrón Strategy** mediante el puerto `PuertoProveedorIA`. Se selecciona **Gemini 1.5 Flash** como proveedor inicial de referencia por su ventana de contexto multimodal, velocidad de inferencia (< 1.5 s en imágenes) y cuota gratuita mensual. Cualquier salida de IA es estrictamente consultiva y requiere confirmación manual de un toque en pantalla por parte del usuario antes de guardarse (`FR-026`).

## Consecuencias
### Positivas
- Sustitución transparente del proveedor de IA cambiando una variable de entorno sin tocar código de negocio.
- Aislamiento total: la caída del servicio de IA no impide el funcionamiento manual del comparador.
- Cero publicación de precios falsos generados por alucinación de modelos sin revisión humana.

### Negativas
- Dependencia de conectividad a internet para la función de autocompletado inteligente por fotografía.
