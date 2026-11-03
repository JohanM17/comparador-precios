# Constitución del Proyecto — Plataforma Colaborativa de Comparación de Precios

## Core Principles

### I. Mobile-first y registro en 15 segundos o menos con cola offline e idempotencia (EC-01)
El sistema **MUST** priorizar de manera absoluta la experiencia de uso móvil en el pasillo de compras (*mobile-first*). Todo el flujo de registro de precios frente a la góndola **MUST** completarse en 15 segundos o menos en al menos el 80 % de los casos bajo conectividad móvil limitada (`EC-01`), utilizando una interfaz simplificada de máximo tres controles (`establecimiento`, `presentación` y `precio_cop`). La aplicación PWA **MUST** implementar una cola persistente en `IndexedDB` (`cola_reportes`) que capture reportes y fotos aun sin acceso a internet y los sincronice automáticamente al reanudar la conexión en el orden estricto establecido (primero subida de foto a URL firmada y luego envío del reporte). Toda solicitud de creación de reporte **MUST** exigir una cabecera `Idempotency-Key` (UUIDv4) y el backend **MUST** responder con el registro original sin duplicar transacciones si la petición se reintenta. Las fotografías de prueba **MUST** comprimirse en el cliente a formato WebP (máximo 300 KB) eliminando metadatos sensibles.

### II. Privacidad por diseño y cumplimiento de la Ley 1581 de 2012
El sistema **MUST** aplicar rigurosamente el principio de privacidad por diseño en concordancia con el régimen colombiano de protección de datos personales (Ley 1581 de 2012 y Decreto 1074 de 2015). Ningún usuario podrá reportar precios ni registrarse sin autorización previa, expresa e informada. Las coordenadas geográficas (`lat`, `lng`) del consumidor **MUST NOT** almacenarse bajo ninguna circunstancia en la base de datos ni quedar registradas en archivos de registro (*logs*); su uso **MUST** limitarse exclusivamente a operaciones volátiles en memoria RAM para el cálculo de distancia Haversine y filtrado por radio. Las direcciones IP **MUST NOT** persistirse en texto plano: el sistema **MUST** calcular una `huella_red = HMAC-SHA256(ip_cliente, clave_secreta_diaria)` y purgarla de manera automática e irreversible tras 30 días de retención. Al ejercer el derecho de supresión de cuenta (`DELETE /v1/mi-cuenta`), el sistema **MUST** anonimizar de inmediato los registros históricos (`reportante_id = null`, `foto_prueba_path = null`), eliminar las fotos del almacenamiento y ofuscar el alias. Las señales y reglas internas de detección de anomalías o fraude **MUST NOT** exponerse jamás al reportante.

### III. Neutralidad comercial absoluta en el orden de resultados (EC-06)
El sistema **MUST** garantizar neutralidad e imparcialidad comercial total en la presentación y ordenamiento de precios (`EC-06` al 100 %). El ordenamiento de resultados por defecto **MUST** regirse única y exclusivamente por el precio normalizado por unidad de medida base (`g`, `ml`, `unidad`), agrupado en dos bloques funcionales: primero las ofertas vigentes y confiables (`Bloque 1`), y al final los datos dudosos o desactualizados (`Bloque 2`). Ningún comercio verificado ni pago de pauta podrá alterar, ponderar ni comprar posiciones privilegiadas en el escalafón orgánico. La información comercial y publicitaria **MUST** almacenarse en esquemas independientes y viajar como una colección separada (`promociones`), jamás dentro de la lista de `resultados`. Una regla de arquitectura automatizada (`import-linter`) **MUST** asegurar que el módulo de precios no importe ni dependa directa o indirectamente del módulo comercial.

### IV. Dominio puro desarrollado con TDD estricto antes del código (NON-NEGOTIABLE)
Toda la lógica central del negocio encapsulada en `backend/app/dominio/` **MUST** ser código puro: libre de operaciones de entrada/salida (I/O), sin llamadas a bases de datos ni clientes de red, sin dependencias de frameworks web y sin acceso directo al reloj del sistema (utilizando el protocolo abstracto `Reloj`). El desarrollo de cualquier componente de este dominio **MUST** construirse bajo un ciclo estricto de Desarrollo Guiado por Pruebas (TDD): primero la prueba automatizada en `pytest` que falla (`test:`), segundo la implementación mínima que la satisface (`feat:`), y tercero la refactorización limpia (`refactor:`). La cobertura de código en `backend/app/dominio/` **MUST** alcanzar un mínimo de 95 % de líneas y ramas, verificada con pruebas basadas en propiedades (`hypothesis`) y chequeo de tipos estricto sin excepciones (`mypy --strict`).

### V. Cero constantes mágicas en código, entorno local sin Docker y presupuesto costo cero
Queda estrictamente prohibido cablear números mágicos o constantes de negocio en el código fuente; todo umbral, dispersión, ventana temporal, ponderador de riesgo o límite operativo **MUST** residir centralizado en la tabla `config_parametro` y leerse a través de caché en memoria de 60 segundos. El entorno de desarrollo local y las pruebas de integración **MUST** operar conectándose directamente a los servicios gestionados en la nube (PostgreSQL + PostGIS, Auth y Storage en Supabase vía MCP y variables en `.env`, y caché en Upstash Redis), o utilizar mocks en memoria para pruebas unitarias y de carga local, eliminando completamente la necesidad de instalar o ejecutar Docker Desktop o `docker-compose` en la máquina del desarrollador. El `Dockerfile` multi-etapa se **MUST** reservar exclusivamente para el empaquetado y despliegue del backend en la nube en `T-50`. La solución técnica **MUST** mantenerse viable dentro del presupuesto de Costo Cero ($0 USD), salvaguardando las cuotas mensuales gratuitas de Supabase, Upstash y Vercel mediante una estrategia de caché de dos niveles (L1 en RAM de 5 s y L2 en Redis de 60 s) y limitadores de tasa en memoria.

## Restricciones Técnicas, Arquitectura y Calidad

### Separación de Responsabilidades
El backend en FastAPI **MUST** concentrar toda la lógica del negocio: cálculo de precios por unidad de medida base, evaluación de vigencia por decaimiento exponencial, cálculo de sellos de confianza, detección determinista de anomalías y ordenamiento en dos bloques. El frontend en Next.js **MUST** limitarse exclusivamente a renderizar la respuesta de la API utilizando el cliente tipado generado automáticamente desde `docs/api/openapi.json`. Ningún cálculo de negocio, reordenamiento orgánico ni inferencia de sellos se ejecutará en el cliente web.

### Manejo de Tiempo, Moneda y Medidas
- Fechas y marcas de tiempo **MUST** persistirse en PostgreSQL como `timestamptz` en UTC y serializarse en la API como cadenas ISO 8601 en UTC (`YYYY-MM-DDTHH:MM:SSZ`).
- Toda cifra monetaria **MUST** manipularse como número entero estricto en pesos colombianos (`precio_cop: int`), incluyendo siempre todos los impuestos de ley.
- Los cálculos de precios por unidad de medida base y cantidades normalizadas **MUST** utilizar aritmética de precisión fija (`decimal.Decimal` en Python y `numeric` en PostgreSQL), prohibiendo terminantemente el uso de tipos de coma flotante (`float`) para dinero o conversiones de volumen y masa.

### Seguridad y Privilegios Mínimos
- Todos los esquemas de transferencia de datos de entrada **MUST** definirse con Pydantic v2 configurando `model_config = ConfigDict(extra='forbid')`.
- Todas las consultas a la base de datos **MUST** ser parametrizadas.
- En ejecución ordinaria, el backend **MUST** autenticarse ante PostgreSQL empleando el rol con privilegios mínimos `app_backend`, el cual tiene revocado el permiso de eliminación sobre tablas de evidencia.
- Las tablas `reporte_precio` y `auditoria` **MUST** ser inmutables (*append-only*), protegidas contra eliminación y alteración mediante triggers y políticas a nivel de base de datos.
- Las extensiones de seguridad Row Level Security (RLS) en Supabase **MUST** permanecer habilitadas sin políticas de acceso anónimo público para evitar lecturas directas desde el frontend sin pasar por FastAPI.

### Convenciones de Nomenclatura e Idioma
- Comentarios de código, docstrings, documentación OpenAPI y textos visibles de la interfaz **MUST** redactarse en español estándar de Colombia (`es-CO`).
- Identificadores de negocio en Python y PostgreSQL **MUST** usar `snake_case` en español sin tildes ni caracteres especiales como la letra `ñ` (ej. `precio_cop`, `establecimiento`, `cantidad_base`).
- Identificadores en TypeScript y React **MUST** emplear `camelCase` para variables, funciones y propiedades, y `PascalCase` para componentes y definiciones de tipos.
- Conceptos técnicos universales **MUST** conservar sus términos estándar en inglés (`cache`, `token`, `middleware`, `router`, `healthcheck`, `payload`).

## Flujo de Trabajo y Puertas de Calidad (Quality Gates)

### Ciclo SDD (Spec-Driven Development)
Toda funcionalidad del proyecto **MUST** desarrollarse siguiendo rigurosamente las etapas del flujo Spec Kit: `constitution` -> `specify` -> `plan` -> `tasks` -> `implement` -> `converge`. El desarrollo se ejecutará mediante tareas atómicas numeradas (`T-xx`) en estricto orden secuencial. Ninguna tarea podrá considerarse terminada ni se avanzará a la siguiente hasta que todos los criterios de su columna «Hecho cuando…» y las pruebas de regresión asociadas estén totalmente en verde.

### Modo Docente y Guía Manual
En cada tarea `T-xx`, el agente de desarrollo **MUST** actuar como un profesor experto en Ingeniería de Software: al finalizar cada paso explicará en lenguaje conciso y pedagógico qué patrón de diseño o decisión arquitectónica se aplicó y cuál es su justificación. Si la tarea exige acciones manuales en servicios de terceros o configuraciones externas en el navegador (Supabase, Upstash, GitHub, Vercel o servidores MCP), el agente **MUST** detenerse y proporcionar primero una guía instructiva paso a paso para el desarrollador.

### Integridad de Requisitos y Preguntas Abiertas
Si durante el desarrollo surge una ambigüedad, contradicción o dependencia externa no confirmada, el agente **MUST NOT** inventar o asumir supuestos; **MUST** suspender la tarea actual y registrar el caso estructurado en `docs/PREGUNTAS_ABIERTAS.md`.

## Gobernanza

1. **Supremacía Constitucional:** Esta Constitución representa el marco normativo supremo del proyecto. Ningún plan de tareas, especificación funcional ni convención informal de código prevalecerá sobre los principios aquí establecidos. En caso de conflicto, rige el siguiente orden de precedencia: (1) Ley colombiana y privacidad > (2) Escenarios de calidad (`EC-01` a `EC-06`) > (3) Esta Constitución > (4) Especificaciones y planes de tareas (`docs/PLAN_CONSTRUCCION.md`) > (5) Preferencias de estilo.
2. **Procedimiento de Enmienda:** Cualquier modificación a los principios o restricciones de este documento requerirá una justificación técnica formal, consenso del equipo, actualización del versionamiento semántico y un registro de decisión arquitectónica (ADR) cuando implique impacto estructural.
   - **MAJOR (X.0.0):** Modificación, supresión o redefinición incompatible de principios fundamentales o garantías de calidad.
   - **MINOR (x.Y.0):** Adición de nuevos principios, secciones o directrices técnicas materiales no conflictivas con los principios preexistentes.
   - **PATCH (x.y.Z):** Correcciones de redacción, ortografía, clarificaciones de términos o refinamientos no semánticos.
3. **Control de Cumplimiento:** Todo cambio de código mediante Pull Request y cada entrega de incremento **MUST** ser auditada frente a los principios de esta Constitución.

**Version**: 1.0.0 | **Ratified**: 2026-11-02 | **Last Amended**: 2026-11-02
