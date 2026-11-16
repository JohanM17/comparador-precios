# Entregable 4: Plan de Aseguramiento de Calidad del Software (ISO/IEC 25010:2023, ISO/IEC 25040 y Boehm)

## 1. Justificación del Modelo de Calidad Adoptado
Para la evaluación de la calidad del producto software se adoptó el estándar **ISO/IEC 25010:2023 (Systems and software Quality Requirements and Evaluation - SQuaRE)**, complementado por el proceso de evaluación de **ISO/IEC 25040**.

### Comparativa frente a Modelos Clásicos (Boehm, McCall)
- **Modelo de Barry Boehm (1978):** Aunque pionero en clasificar la calidad en niveles jerárquicos (utilidad primaria, factores y métricas), carece de especificaciones explícitas para sistemas web modernos, arquitecturas cloud, micro-dispositivos móviles y normativas contemporáneas de privacidad y protección de datos personales.
- **ISO/IEC 25010:2023:** Proporciona un marco taxonómico actualizado de 8 características exhaustivas, permitiendo cuantificar contractualmente atributos críticos del comparador como la eficiencia de desempeño bajo ráfagas (`EC-04`), la usabilidad móvil sin red (`EC-01`), la seguridad de privilegios mínimos (`ADR-012`) y la modificabilidad arquitectónica sin acoplamiento comercial (`EC-05`, `EC-06`).
- **ISO/IEC 25040:** Aporta la metodología de 5 pasos para el proceso de evaluación: (1) Establecer requisitos de evaluación, (2) Especificar la evaluación, (3) Diseñar la evaluación, (4) Ejecutar la evaluación y (5) Concluir la evaluación.

---

## 2. Las 8 Características de Calidad del Producto (ISO/IEC 25010:2023)

| Característica SQuaRE | Subcaracterísticas Clave | Requisito / Escenario del Proyecto | Mecanismo de Verificación y Control |
| :--- | :--- | :--- | :--- |
| **1. Adecuación Funcional** | Completitud, corrección y pertinencia. | `FR-001` a `FR-026`, neutralidad comercial `EC-06`. | Pruebas unitarias de dominio con `pytest`, pruebas de contrato OpenAPI y `import-linter`. |
| **2. Eficiencia de Desempeño** | Comportamiento temporal y utilización de recursos. | `EC-02` (vigencia $\le 60$ s), `EC-04` (500 VUs, $p_{95} \le 2.000$ ms, error $< 1\,\%$). | Caché L1/L2 (Redis 60 s), pruebas de carga con `k6` (`infra/k6/ec04_carga.js`). |
| **3. Compatibilidad** | Coexistencia e interoperabilidad. | PWA multiplataforma (Android, iOS, Desktop), API REST OpenAPI 3.1. | Validación en Chrome, Firefox, Safari y clientes tipados TypeScript generados. |
| **4. Usabilidad** | Reconocibilidad, aprendizaje y accesibilidad. | `EC-01` (captura en góndola $\le 15$ s con 3 controles), WCAG 2.2 AA. | Pruebas de usabilidad con 10 usuarios reales (`entregable_7`) y auditoría con `axe-core`. |
| **5. Confiabilidad** | Madurez, disponibilidad y tolerancia a fallos. | Resiliencia ante caída de Redis/Open Food Facts, cola offline `IndexedDB`. | Circuit Breaker con timeout de 3 s (`ADR-015`), fallback transparente de Redis a PostgreSQL. |
| **6. Seguridad** | Confidencialidad, integridad y autenticidad. | RLS sin políticas públicas, rol `app_backend`, mitigación ráfagas `EC-03`, Ley 1581. | Pruebas SQL de aislamiento (`test_seguridad_bd.py`), HMAC diario y borrado seguro de cuentas. |
| **7. Mantenibilidad** | Modularidad, reusabilidad, analizabilidad y modificabilidad. | `EC-05` (incorporación de Etapa 2 con esfuerzo real $\le 1.25\times$ estimado). | Arquitectura Hexagonal, dominio puro desacoplado de I/O, `mypy --strict` y 0 dependencias cíclicas. |
| **8. Flexibilidad (Portabilidad)** | Adaptabilidad, facilidad de instalación y reemplazabilidad. | `ADR-017` (portabilidad de contenedor entre Railway, Render y Fly.io). | `Dockerfile` multi-etapa estándar y configuración exclusiva por variables de entorno. |

---

## 3. Umbrales de Aceptación del Plan de Calidad
1. Cobertura de código en `backend/app/dominio/`: $\ge 95\,\%$.
2. Cobertura en módulos de aplicación e infraestructura: $\ge 80\,\%$.
3. Violaciones críticas o serias en accesibilidad WCAG 2.2 AA (`axe-core`): exactamente $0$.
4. Errores de tipos en backend (`mypy --strict`) y frontend (`tsc --noEmit`): exactamente $0$.
