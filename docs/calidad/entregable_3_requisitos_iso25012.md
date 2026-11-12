# Entregable 3: Especificación de Calidad de Datos según ISO/IEC 25012

## 1. Alcance y Contexto Normativo
El estándar internacional **ISO/IEC 25012 (Data Quality Model)** define un marco de calidad para datos almacenados en sistemas de información, dividiendo las características en inherentes (intrínsecas a los datos) y dependientes del sistema. En el comparador de precios de la canasta familiar, la calidad del dato es el activo crítico sobre el cual descansa la confianza ciudadana y la prevención de la especulación comercial.

---

## 2. Las 7 Características Críticas de Calidad de Datos

| Característica ISO 25012 | Prioridad | Definición en el Contexto del Comparador | Mecanismo Técnico de Control y Validación | Métrica y Umbral de Aceptación |
| :--- | :---: | :--- | :--- | :--- |
| **1. Credibilidad (Accuracy / Trust)** | Crítica (1) | Grado en que los precios reflejan valores verdaderos y creíbles para el consumidor. | Algoritmo determinista en 5 pasos (`D-03`), z-score modificado ($|M| \le 3.5$), reputación bayesiana del reportante y fotos de prueba sin EXIF. | $\ge 90\,\%$ de anomalías detectadas en simulación `EC-03`; $\le 10\,\%$ de falsas alarmas. |
| **2. Actualidad (Currentness)** | Crítica (2) | Vigencia temporal del precio respecto al momento de consulta en góndola. | Función de decaimiento exponencial ($t_{1/2} = 72$ h), clasificación en dos bloques (7 y 30 días) e invalidación de caché en $\le 60$ s (`EC-02`). | Peor tiempo de actualización en caché $\le 60$ s verificado en 100 pruebas continuas (`EC-02`). |
| **3. Exactitud (Syntactic Accuracy)** | Crítica (3) | Precisión numérica y conformidad de formato de los precios y cantidades. | Restricción de tipo entero estricto para `precio_cop`, rango duro en `config_parametro` y `Decimal` para cantidades base. | 100 % de precios dentro del rango $[100, 5.000.000]$ COP; cero uso de punto flotante binario en cálculos. |
| **4. Consistencia (Consistency)** | Crítica (4) | Ausencia de contradicciones entre presentaciones del mismo producto y tiendas. | Normalización matemática obligatoria a `unidad_base` (`g`, `ml`, `u`), jerarquía de referencia en 3 niveles y ratio extremo ($5\times$). | $0\,\%$ de inconsistencias dimensionales; error de conversión en `dominio.unidades` $= 0$. |
| **5. Completitud (Completeness)** | Alta (5) | Suficiencia de datos requeridos para efectuar una comparación representativa. | Catálogo semilla de ~150 productos y ~30 tiendas de Armenia; asignación del sello `pocos_datos` cuando $n < 3$. | $\ge 95\,\%$ de productos de la canasta básica con al menos un precio reportado en Armenia. |
| **6. Trazabilidad (Traceability)** | Alta (6) | Capacidad de auditar el origen, autoría y cambios de cada dato de precio. | Historial inmutable en tabla `reporte_precio` (*append-only* protegida por triggers) y bitácora en `auditoria`. | 100 % de cambios de estado o precio vigente respaldados por un registro de auditoría inmutable. |
| **7. Confidencialidad (Confidentiality)** | Alta (7) | Garantía de que datos sensibles o identificables no se expongan indebidamente. | RLS sin políticas públicas, coordenadas GPS eliminadas de base de datos/logs, `huella_red` con HMAC diario y anonimización Ley 1581. | 0 fugas de coordenadas GPS en logs de servidor; 0 accesos directos de roles `anon`/`authenticated`. |

---

## 3. Matriz de Monitoreo Continuo
Cada una de las 7 características se monitorea a través de pruebas automatizadas en el pipeline de CI (`pytest`), scripts de simulación periódica (`scripts/evaluar_ec03.py`) y revisiones de auditoría en la bandeja del moderador.
