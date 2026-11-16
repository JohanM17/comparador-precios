# ADR-015: Servicios Externos Fuera del Camino Crítico con Circuit Breaker

## Estado
Aceptado

## Contexto
El comparador se integra con servicios de terceros (Open Food Facts para enriquecer datos nutricionales del catálogo y Gemini Flash para reconocimiento visual de etiquetas). Las APIs externas están sujetas a variabilidad de red, caídas imprevistas y latencias elevadas. Si una petición síncrona a un servicio externo se ejecuta en el hilo principal de una consulta pública o de un reporte de precio, una degradación externa provocaría el colapso del comparador.

## Alternativas consideradas
1. **Llamadas síncronas bloqueantes sin límite de tiempo:** Una lentitud en Open Food Facts agotaría las conexiones del servidor ASGI (`uvicorn`), provocando tiempos de respuesta superiores a 30 segundos y error 504.
2. **Tareas en cola en segundo plano pesadas (Celery + RabbitMQ):** Requiere infraestructura adicional incompatible con la restricción de presupuesto cero.
3. **Servicios fuera del camino crítico con Timeout estricto y Circuit Breaker:**
   - La consulta o reporte del usuario **nunca espera** una respuesta externa obligatoria.
   - Las llamadas a servicios externos tienen un límite de tiempo (*timeout*) improrrogable de **3 segundos**.
   - Si el servicio externo falla consecutivamente en 5 ocasiones, el *Circuit Breaker* se abre durante 60 segundos, respondiendo inmediatamente con valores por defecto o degradación elegante sin intentar llamadas a la red.

## Decisión
Aislar todas las integraciones externas (Open Food Facts y proveedores de IA) fuera del camino crítico de la API de comparación y reporte, envolviéndolas en adaptadores con un **timeout estricto de 3 segundos** y un patrón **Circuit Breaker** (estado cerrado, abierto y semi-abierto) que garantiza la degradación elegante y el funcionamiento ininterrumpido del sistema central.

## Consecuencias
### Positivas
- Resiliencia del sistema central frente a fallos parciales de infraestructura externa.
- Preservación de la latencia sub-segundo en los endpoints de usuario final.
- Cero consumo innecesario de sockets o recursos de red ante caídas prolongadas de terceros.

### Negativas
- Posible ausencia temporal de datos nutricionales enriquecidos si Open Food Facts está en mantenimiento.
