# ADR-014: Huella de Red con HMAC-SHA256 Diario y Purga a los 30 Días

## Estado
Aceptado

## Contexto
Para mitigar ataques coordinados de reportes masivos falsos (ej. múltiples cuentas creadas desde la misma conexión de internet para alterar el precio de una tienda), el sistema necesita correlacionar reportes provenientes del mismo origen de red. Sin embargo, conforme a la **Ley Estatutaria 1581 de 2012** (régimen colombiano de protección de datos personales), las direcciones IP constituyen datos personales identificables que no pueden almacenarse en texto plano sin autorización expresa y con fines desproporcionados.

## Alternativas consideradas
1. **Almacenar la dirección IP en texto plano en `reporte_precio`:** Violación directa del principio de minimización de datos de la Ley 1581 y riesgo legal para el equipo.
2. **Hash estático simple (`SHA-256(IP)`):** Vulnerable a ataques de diccionario inverso mediante tablas arcoíris (*rainbow tables*), dado el espacio reducido de direcciones IPv4.
3. **Huella criptográfica efímera con clave rotativa diaria (`HMAC-SHA256(IP, clave_diaria)`):**
   - La clave secreta se deriva dinámicamente cada día y no se persiste permanentemente.
   - Dos reportes del mismo día con la misma IP producen la misma huella, permitiendo detectar ráfagas en ventanas de 30 minutos (`EC-03`).
   - Al cambiar el día, la misma IP genera una huella diferente, imposibilitando el seguimiento o rastreo del usuario a largo plazo.
   - Purga física: una tarea programada anula `huella_red = null` para cualquier registro con más de 30 días de antigüedad (`FR-015`).

## Decisión
Implementar el cálculo de origen de red mediante **`HMAC-SHA256` con clave rotativa diaria** (`huella.py`) y registrar un job diario en GitHub Actions (`limpiar_huellas`) que ejecuta la purga física pasando a `NULL` el campo `huella_red` en registros que superen los 30 días de antigüedad.

## Consecuencias
### Positivas
- Cumplimiento estricto del régimen de protección de datos personales colombiano (Ley 1581 de 2012).
- Capacidad matemática efectiva para detectar ráfagas coordinadas en tiempo real sin vulnerar la privacidad.
- Imposibilidad técnica de reconstruir la dirección IP del usuario una vez rota la clave del día.

### Negativas
- No se pueden correlacionar ráfagas que abarquen más de un día calendario (compensado por el sistema de reputación bayesiana acumulada).
