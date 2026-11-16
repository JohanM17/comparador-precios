# Registro de Preguntas Abiertas (`PA-01` a `PA-04`)

Este documento constituye el registro formal y auditable de requisitos ambiguos, dependencias externas o decisiones operativas pendientes de confirmación, conforme al principio de no invención y fidelidad al diseño del proyecto.

---

## Tabla de Estado de Preguntas Abiertas

| ID | Tema | Contexto y Opciones | Decisión / Placeholder Técnico Actual | Estado |
| :--- | :--- | :--- | :--- | :---: |
| **PA-01** | Contacto legal y User-Agent | Nombre del responsable y correo institucional oficial para consultas/reclamos de Ley 1581 y cabecera `User-Agent` requerida por Open Food Facts. | Se utiliza provisionalmente `CONTACTO_LEGAL_EMAIL=contacto-comparador@cue.edu.co` y cabecera `User-Agent: ComparadorPreciosArmenia/1.0 (contacto-comparador@cue.edu.co)`. | `POR CONFIRMAR` |
| **PA-02** | Esquema de firma de JWT en Supabase | Esquema de firma de JWT activo en el proyecto de Supabase (asimétrico `JWKS` ES256/RS256 vs. secreto simétrico legado `HS256`). | **Resuelto en T-03:** `backend/app/compartido/seguridad.py` implementa soporte dual: si `SUPABASE_JWKS_URL` está configurada, valida vía JWKS asimétrico; en su defecto, valida con `SUPABASE_JWT_SECRET` (HS256). | `RESUELTA` |
| **PA-03** | Levantamiento de campo en Armenia | Distribución operativa entre los 4 integrantes para el levantamiento de precios en 5 a 8 tiendas y supermercados de Armenia (`supabase/seed/precios_semilla.csv`). | Estructura CSV y script `scripts/semilla.py` listos; se utiliza carga de prueba con `es_demo = true` mientras se ejecuta el trabajo de campo de la Ola 1. | `POR CONFIRMAR` |
| **PA-04** | Alojamiento definitivo de contenedor | Proveedor definitivo de alojamiento del contenedor backend al agotar los $5 USD de prueba de Railway (Railway Hobby vs. Render Free vs. Fly.io). | El `Dockerfile` multi-etapa se diseñó 100 % agnóstico y portable (`ADR-017`), permitiendo migrar de Railway a Render Free o Fly.io en minutos sin cambiar código. | `POR CONFIRMAR` |

---

## Procedimiento de Resolución
1. Toda nueva duda o ambigüedad detectada durante la implementación de una tarea `T-xx` se añade de inmediato a este archivo con su identificador correlativo `PA-xx`.
2. Una pregunta abierta no detiene las tareas independientes, pero congela cualquier implementación que dependa directamente del valor en disputa.
3. Una vez confirmada la respuesta por el equipo o la fuente externa, el estado pasa a `RESUELTA`, indicando la fecha, el commit y el archivo donde se materializó la decisión.
