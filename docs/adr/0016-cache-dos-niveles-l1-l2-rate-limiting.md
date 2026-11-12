# ADR-016: Caché de Dos Niveles (L1 5s + L2 Redis 60s) y Límites de Uso en Memoria

## Estado
Aceptado

## Contexto
Upstash Redis ofrece un plan gratuito generoso pero limitado a **10.000 comandos diarios** y **500.000 mensuales**. En una prueba de carga con 500 usuarios concurrentes (`EC-04`) o ante un pico de tráfico real en la ciudad de Armenia, si cada consulta `GET /v1/productos/{id}/comparacion` ejecuta un comando `GET` directo a Redis, la cuota diaria gratuita se agotaría en menos de 15 minutos, deteniendo el servicio para el resto de la jornada.

## Alternativas consideradas
1. **Caché únicamente en Redis L2:** Agota la cuota gratuita de comandos bajo tráfico concurrente sostenido o ataques de scraping.
2. **Caché solo en memoria local del proceso (L1) con TTL largo (60 s):** Dificulta la invalidación coordinada si se ejecutan múltiples réplicas del contenedor y consume demasiada memoria RAM.
3. **Estrategia de Caché de Dos Niveles (L1 en RAM + L2 en Redis) + Rate Limiting en Memoria:**
   - **Nivel 1 (L1 - Proceso Local):** Almacenamiento en memoria ultrarrápido con TTL ultra-corto de **5 segundos**. Absorbe ráfagas inmediatas de usuarios simultáneos sin emitir comandos de red.
   - **Nivel 2 (L2 - Upstash Redis):** Caché distribuida con TTL de **60 segundos** (`EC-02`). Solo se consulta si ocurre un fallo en L1 (1 comando cada 5 s por producto caliente).
   - **Límites de uso (*Rate Limiting*) en memoria:** Protección contra abuso por IP (`huella_red`) en memoria del servidor web sin consumir comandos en Redis.

## Decisión
Implementar un adaptador de **caché de dos niveles** (`cache_dos_niveles.py`): L1 en memoria del proceso ASGI con TTL de 5 segundos y L2 en Upstash Redis con TTL de 60 segundos. Adicionalmente, el rate-limiting de peticiones abusivas se procesa en memoria del proceso con un algoritmo de ventana deslizante token-bucket sin cargar la cuota de Redis.

## Consecuencias
### Positivas
- Reducción del $\approx 85\,\%$ en la cantidad de comandos emitidos hacia Upstash Redis bajo alta concurrencia.
- Blindaje de la cuota mensual gratuita de Upstash sin necesidad de tarjeta de crédito.
- Latencias de respuesta inferiores a 5 ms para peticiones servidas desde L1.

### Negativas
- Retardo de hasta 5 segundos en propagar una invalidación si existen múltiples instancias en paralelo (perfectamente dentro del límite de 60 segundos de `EC-02`).
