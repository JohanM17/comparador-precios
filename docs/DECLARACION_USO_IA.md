# Declaración Académica de Uso de Inteligencia Artificial

## 1. Declaración de Transparencia y Ética
En concordancia con los principios de integridad académica, reproducibilidad y rigor en Ingeniería de Software, los autores declaramos el uso asistido de herramientas de **Inteligencia Artificial Generativa** durante el ciclo de vida del proyecto **Plataforma Colaborativa de Comparación de Precios de la Canasta Familiar de Armenia (Quindío)**.

El uso de estas tecnologías se realizó bajo la modalidad de **copiloto / agente ejecutor guiado**, donde el criterio técnico, la arquitectura, las decisiones de compromiso (*trade-offs*) y la validación final permanecen bajo la responsabilidad exclusiva del equipo humano de 4 ingenieros.

---

## 2. Metodología de Trabajo: Spec-Driven Development (SDD)
El desarrollo del proyecto no utilizó generación libre o descontrolada de código. Se implementó una disciplina estricta de **Desarrollo Guiado por Especificaciones (Spec-Driven Development - SDD)** soportada por el marco metodológico **GitHub Spec Kit (`agy`)**:

1. **Constitución Innegociable (`constitution.md`):** Establece los principios rectores que la IA debe acatar sin excepción (neutralidad comercial `EC-06`, privacidad Ley 1581, exactitud aritmética con `Decimal` y dominio puro libre de I/O).
2. **Especificación y Contratos (`spec.md` y `api-v1.md`):** Define los requisitos funcionales (`FR-001` a `FR-026`) y escenarios de calidad (`EC-01` a `EC-06`) antes de escribir una sola línea de código.
3. **Plan y Tareas Secuenciales (`plan.md` y `tasks.md`):** Descompone la construcción en 47 tareas atómicas (`T-00` a `T-55`) con criterios unívocos de aceptación («Hecho cuando...»).

---

## 3. Salvaguardas de Calidad y Validación Humana: TDD
Para garantizar que el código generado no contenga alucinaciones, vulnerabilidades ni sesgos lógicos, se adoptó como regla técnica obligatoria el **Desarrollo Guiado por Pruebas (Test-Driven Development - TDD)**:

- **Dominio Puro:** Todo módulo en `backend/app/dominio/` (`unidades.py`, `vigencia.py`, `sello.py`, `orden.py`, `anomalia.py`, `riesgo.py`, `reputacion.py`) fue desarrollado escribiendo primero la prueba unitaria que falla (`pytest`), luego la implementación mínima y finalmente la refactorización.
- **Análisis Estático Riguroso:** El 100 % del código es auditado automáticamente por:
  * `ruff`: cumplimiento de estilo y buenas prácticas PEP 8.
  * `mypy --strict`: verificación estricta de tipos estáticos sin uso de `Any`.
  * `import-linter`: verificación matemática de barreras arquitectónicas (ej. prohibición absoluta de importación `precios` $\rightarrow$ `comercial`).
  * `tsc --noEmit` y `next lint`: verificación de contratos y tipado estricto en el frontend.

---

## 4. Modelos y Herramientas Empleadas
- **Modelos de Lenguaje:** Google Gemini 2.0 / 2.5 Pro a través del entorno Antigravity IDE / agy CLI.
- **Áreas de Asistencia:** Redacción de borradores de especificación formal, andamiaje de pruebas unitarias, conversión de esquemas OpenAPI a contratos TypeScript y automatización de migraciones SQL.
- **Áreas Exclusivamente Humanas:** Definición de la política de neutralidad comercial, trabajo de campo y entrevistas a consumidores de Armenia, ponderación de riesgos matemáticos y aprobación final de cada commit en Git.

---

## 5. Corte 3: segunda herramienta (noviembre de 2026)
Durante el tercer corte se incorporó una segunda herramienta de IA, que se declara con el mismo
detalle que la primera.

- **Modelo y entorno:** Anthropic Claude (Opus 5) a través de Claude Code.

### 5.1 Áreas de asistencia
- **Rediseño de la interfaz:** sistema de color y tipografía en `tailwind.config.js` y
  `globals.css`, y conversión de las siete pantallas al nuevo lenguaje visual, incluida la
  adaptación de los componentes de historial que llegaron con la ampliación A2.
- **Módulo comercial (`T-60` a `T-66`):** análisis de impacto previo (`docs/calidad/ec05-estimado.md`),
  reglas de dominio `contraste.py` y `promocion.py` con sus pruebas escritas primero, migración
  `0006_modulo_comercial.sql`, las siete rutas del módulo y el puerto `PuertoPromociones` que
  mantiene la frontera de `EC-06`.
- **Accesibilidad:** ampliación de la prueba automatizada para cubrir las ocho pantallas en modo
  claro y oscuro, dieciséis verificaciones con `axe-core`.

### 5.2 Áreas exclusivamente humanas
- Selección de las opciones `A2` (historial de precios) y `B1` (observabilidad con SLO) entre las
  siete que ofrece el Anexo 1.
- Dirección visual del producto, elegida por el equipo tras descartar varias propuestas.
- Validación de las estimaciones de esfuerzo y de los umbrales de calidad frente a la capacidad
  real del equipo.
- Aprobación de cada commit.

### 5.3 Trabajo asistido que se descartó
Antes de conocer que la ampliación del Anexo 1 ya estaba seleccionada e implementada como
`A2 + B1`, se redactó con esta misma herramienta un registro previo para las opciones `A1`
(canasta comparada) y `B2` (entrega continua con controles). Al constatar que el anexo admite
**una** opción por bloque y que la selección del equipo era otra, ese registro se descartó por
completo y no se integró al repositorio. Se deja constancia porque la transparencia del
numeral 1 cubre también el trabajo que no se usó.

Se reitera el compromiso del numeral 1: cada integrante debe estar en capacidad de explicar y
defender las decisiones registradas en los ADR durante la sustentación.
