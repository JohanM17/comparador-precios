# ADR-010: Cola Offline en IndexedDB e Idempotencia Obligatoria (EC-01)

## Estado
Aceptado

## Contexto
El escenario de calidad `EC-01` exige que un usuario frente a la góndola pueda registrar un precio en 15 segundos o menos con solo 3 controles, incluso si la señal celular se pierde completamente dentro del supermercado o tienda de barrio. Además, al recuperarse la conectividad, los reintentos automáticos de la red móvil no deben crear reportes duplicados que distorsionen las medianas de precios ni alteren la reputación.

## Alternativas consideradas
1. **Bloquear la aplicación cuando no hay red:** Experiencia frustrante en sótanos y áreas de mala cobertura comercial; incumple el requerimiento esencial de usabilidad `EC-01`.
2. **Almacenar en `localStorage`:** Límite estricto de 5 MB, no soporta almacenamiento binario eficiente de imágenes y bloquea el hilo principal de JavaScript (*I/O sincrónico*).
3. **Cola transaccional en `IndexedDB` con protocolo en dos pasos e `Idempotency-Key`:**
   - Base de datos asíncrona en el navegador con capacidad de decenas de megabytes.
   - Generación de UUIDv4 del lado cliente como `Idempotency-Key`.
   - Protocolo estricto de dos fases al sincronizar: primero se sube la foto comprimida a la URL pre-firmada de Supabase Storage; una vez confirmada la subida, se envía el reporte JSON a `/v1/reportes` con la llave de idempotencia.

## Decisión
Implementar una **cola offline en `IndexedDB`** gestionada por el cliente Next.js. El usuario completa el formulario y la captura se guarda localmente en estado `pendiente`. Al detectarse conectividad (`online`), el sincronizador ejecuta el orden: (1) subir imagen comprimida a URL firmada, (2) enviar reporte con `Idempotency-Key`. Si el backend recibe la misma llave, devuelve `200 OK` con la respuesta original sin duplicar registros (`FR-008`).

## Consecuencias
### Positivas
- Cumplimiento de `EC-01`: el reporte se completa localmente en $< 15$ s sin esperar a la red.
- Cero duplicación de datos por reintentos de red o pulsaciones múltiples en el botón.
- Resiliencia ante desconexiones a mitad de la subida.

### Negativas
- Complejidad adicional en la gestión del ciclo de vida de la cola y reintentos con retroceso exponencial.
