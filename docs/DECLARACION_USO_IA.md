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
