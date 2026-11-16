# Entregable 2: Estudio de Benchmarking de Comparadores de Precios y Modelos de Confiabilidad

## 1. Alcance y Soluciones Evaluadas
Se realizó un análisis comparativo y de ingeniería inversa conceptual sobre 4 plataformas y modelos existentes de consulta y comparación de precios, contrastando sus fortalezas y vulnerabilidades frente a los requerimientos de la canasta familiar en Armenia (Quindío):

1. **Open Prices (Open Food Facts):** Iniciativa global colaborativa abierta para recolección de precios mediante fotos de tiquetes y código de barras.
2. **SIPSA - DANE (Colombia):** Sistema de Información de Precios y Abastecimiento del Sector Agropecuario, enfocado en centrales mayoristas (ej. Mercar en Armenia).
3. **Catálogos Digitales de Cadenas Minoristas (Éxito, Olímpica, D1, Ara):** Portales de e-commerce y folletos comerciales propietarios.
4. **Apps Colaborativas Comerciales (ej. TuMercado / Comparadores Locales):** Aplicaciones móviles comerciales de crowdsourcing.

---

## 2. Matriz Comparativa Estructurada

| Criterio de Comparación | Open Prices (OFF) | SIPSA - DANE | Portales de Cadena | Plataforma Armenia (Propuesta) |
| :--- | :--- | :--- | :--- | :--- |
| **Cobertura en tiendas pequeñas** | Baja (enfocada en Europa/EE.UU.). | Nula (solo mayoristas / plazas de mercado). | Nula (solo sus propios locales). | **Alta (tiendas de barrio y minimercados de Armenia).** |
| **Normalización de precios** | Parcial (extrae precio total del tiquete). | Precio por bulto/kilo mayorista sin desglose de marca. | Precio nominal por empaque comercial sin normalizar. | **Total (`FR-001`, `FR-002`): Precio exacto por unidad base (`g`, `ml`, `u`).** |
| **Modelo de confiabilidad** | Revisión comunitaria manual asíncrona. | Muestreo estadístico presencial mensual/semanal. | Precio oficial del comercio sin contraste independiente. | **Híbrido determinista (`D-01` a `D-03`): z-score, MAD, reputación bayesiana y sellos.** |
| **Frecuencia de actualización** | Esporádica según aportes voluntarios. | Semanal o quincenal (desfasada de la inflación diaria). | Diaria en sus canales propios. | **En tiempo real (`EC-02` $\le 60$ s) con decaimiento a 48 h / 72 h (`D-02`).** |
| **Neutralidad comercial** | Alta (fundación sin ánimo de lucro). | Alta (estatal). | Nula (diseñados para promocionar sus marcas). | **Innegociable (`EC-06`): Prohibición de pagos por visibilidad y ranking orgánico.** |
| **Tolerancia a pérdida de red** | Media (requiere conexión para buscar). | Nula (web institucional pesada). | Nula (falla sin 4G estable). | **Total (`EC-01`): PWA con cola offline en IndexedDB.** |

---

## 3. Justificación de Decisiones Técnicas Cerradas (`D-01` a `D-05`)

1. **`D-01` (Comercio vs. Usuarios):** Portales como Éxito muestran su precio oficial pero no reflejan diferencias en góndola física; Open Prices depende solo de usuarios pero sufre de datos escasos. La solución adopta el puerto `PoliticaPrecioReferencia`: en Etapa 1 prioriza usuarios y en Etapa 2 permite precio oficial contrastado automáticamente con reportes comunitarios (sello `en_disputa` si difieren $\ge 10\,\%$).
2. **`D-02` (Vigencia Dinámica):** SIPSA publica datos con desfase de días que no sirven para el mercado del día. Se aprueba la fórmula de vida media exponencial: peso 100 % en 48 h, decaimiento cada 72 h y exclusión a los 30 días.
3. **`D-03` (Detección de Falsos):** Open Prices sufre de reportes malintencionados sin filtrar. Se aprueba la detección determinista en 5 pasos (z-score modificado y MAD) para evitar manipulación de medianas.
4. **`D-04` (Catálogo Cerrado en 2 Niveles):** Open Prices permite crear nombres libres de producto, generando duplicados inmanejables (ej. "Arroz Roa 1k", "Roa 1000g"). Se adopta catálogo normalizado en dos niveles (`producto` + `presentacion`).
5. **`D-05` (Semilla Idempotente Inicial):** Para resolver el problema del "arranque en frío" (*cold start*) que mató a otras apps colaborativas, se inicia con semilla CSV de ~150 productos y ~30 tiendas de Armenia georreferenciadas bajo licencia ODbL.
