# ADR-006: Caché en Redis (Upstash) con TTL de 60 s para Cumplir EC-02 y EC-04

## Estado
Aceptado

## Contexto
El escenario de calidad `EC-04` exige soportar 500 usuarios concurrentes con $p_{95} \le 2.000$ ms y tasa de error $< 1\,\%$. La consulta `/v1/productos/{id}/comparacion` realiza uniones entre presentaciones, establecimientos y precios vigentes. Si cada petición impacta directamente a PostgreSQL a través del Session Pooler, el pool se satura rápidamente. Asimismo, el escenario `EC-02` exige que ningún precio vigente desactualizado persista por más de 60 segundos tras registrarse un cambio.

## Alternativas consideradas
1. **Sin capa de caché (consultar PostgreSQL en cada petición):** Falla rotundamente en `EC-04` con 500 usuarios concurrentes, agotando los límites de conexión de la capa gratuita de Supabase.
2. **Caché solo en memoria local del proceso FastAPI (L1):** Si el backend se escala horizontalmente o se reinicia en contenedores serverless, las cachés locales quedan desincronizadas.
3. **Caché distribuida en Redis (Upstash) con TTL de 60 s e invalidación explícita:** Almacenamiento clave-valor en memoria con latencias de lectura < 15 ms, compatible con REST/HTTP, respaldado por la capa gratuita de Upstash (10.000 comandos diarios / 500.000 mensuales).

## Decisión
Implementar un adaptador de caché distribuida en **Upstash Redis** para la comparación de precios (`cmp:{producto_id}`), con un tiempo de vida máximo (**TTL**) de **60 segundos** para satisfacer rigurosamente `EC-02`. Cuando se acepta un nuevo reporte o se actualiza un precio oficial, la clave de caché del producto afectado se invalida de forma inmediata mediante el comando `DEL`.

## Consecuencias
### Positivas
- Tiempos de respuesta para `GET .../comparacion` inferiores a 50 ms bajo caché caliente.
- Cumplimiento estricto del límite superior de 60 segundos de frescura (`EC-02`).
- Capacidad demostrada para soportar 500 usuarios concurrentes (`EC-04`).
- Consumo mínimo de cuota de Upstash gracias al TTL y la invalidación dirigida por evento.

### Negativas
- Necesidad de un mecanismo de respaldo (*fallback*) transparente a PostgreSQL si Redis no responde temporalmente.
