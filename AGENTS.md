# Reglas del Agente — Plataforma Colaborativa de Comparación de Precios

## 1. Fuentes de verdad (Lectura obligatoria al iniciar sesión)
- Contexto funcional, actores, etapas y decisiones de diseño: `PROYECTO.md`
- Especificación técnica detallada, esquema SQL, contratos de API y tareas: `docs/PLAN_CONSTRUCCION.md`
- Principios innegociables del proyecto (SDD): `.specify/memory/constitution.md`

## 2. Flujo de trabajo SDD con GitHub Spec Kit
- Toda funcionalidad sigue estrictamente el flujo: `constitution` -> `specify` -> `plan` -> `tasks` -> `implement` -> `converge`.
- Antes de escribir o modificar código, lee el plan activo indicado en el bloque `SPECKIT` al final de este archivo y los criterios de la tarea correspondiente en `docs/PLAN_CONSTRUCCION.md`.
- Ejecuta una sola tarea `T-xx` a la vez. No avances a la siguiente hasta comprobar que todos los puntos de su criterio «Hecho cuando...» y las pruebas automáticas estén en verde.
- Si encuentras un requisito ambiguo o un dato externo no confirmado, no lo inventes: regístralo en `docs/PREGUNTAS_ABIERTAS.md`.

## 3. Reglas técnicas innegociables
- **Dominio puro con TDD:** Todo código en `backend/app/dominio/` es puro (sin I/O, sin base de datos, sin HTTP, sin reloj del sistema) y se desarrolla escribiendo primero la prueba en `pytest` que falla, luego la implementación mínima y finalmente refactorización.
- **Separación de responsabilidades:** FastAPI resuelve toda la lógica (precios por unidad base, vigencia, sellos de confianza, detección de anomalías y ordenamiento). El frontend en Next.js solo renderiza la respuesta de la API usando el cliente generado desde `docs/api/openapi.json`.
- **Neutralidad comercial (EC-06):** El módulo `precios` jamás importa ni consulta al módulo `comercial`. Las promociones viajan en un bloque separado y nunca alteran el orden de los resultados.
- **Privacidad y seguridad (Ley 1581):** Jamás guardes ni registres en logs las coordenadas `lat`/`lng` del usuario. Nunca expongas `huella_red` ni las señales internas de detección al usuario.
- **Dinero, tiempo y parámetros:** Precios siempre como entero en pesos (`precio_cop`), cálculos unitarios con `Decimal`, fechas en UTC (ISO 8601) y todos los umbrales de negocio en la tabla `config_parametro`.
- **Idioma del código:** Comentarios, docstrings e identificadores de negocio en español sin tildes ni `ñ` (`snake_case` en Python/SQL, `camelCase`/`PascalCase` en TypeScript).

<!-- SPECKIT START -->
<!-- SPECKIT END -->