# Feature Specification: Núcleo del Comparador de Precios (Etapa 1)

**Feature Branch**: `001-nucleo-comparador`

**Created**: 2026-11-02

**Status**: Ready for Planning

**Input**: User description: "Crear la especificación funcional del núcleo (001-nucleo-comparador) en español tomando exactamente las Historias de Usuario US-1 a US-5, los casos borde, los requisitos funcionales FR-001 a FR-021 y los criterios de éxito EC-01 a EC-06 de docs/PLAN_CONSTRUCCION.md y PROYECTO.md."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar y comparar precios por unidad de medida (Priority: P1)

Como consumidor sin cuenta, quiero buscar un producto de la canasta familiar y comparar su precio entre establecimientos de Armenia y Quindío ordenado por precio por unidad de medida base (kg, litro o unidad), observando con claridad qué tan confiable y reciente es cada dato para tomar decisiones informadas de ahorro.

**Why this priority**: Es la funcionalidad nuclear que entrega valor directo e inmediato al usuario final. Sin consulta y comparación transparente, el sistema no cumple su propósito de visibilizar asimetrías de precios ni empoderar el presupuesto de los hogares.

**Independent Test**: Puede probarse de forma totalmente independiente consultando un producto con distintas presentaciones en varios establecimientos y verificando que el ordenamiento ubique en primer lugar el precio más económico por unidad de medida base, separando claramente en dos bloques los datos vigentes de los desactualizados.

**Acceptance Scenarios**:

1. **Given** que en el producto "Arroz blanco" el establecimiento A ofrece la presentación de 1 kg a $5.000 COP ($5.000/kg) y el establecimiento B ofrece la presentación de 500 g a $2.800 COP ($5.600/kg), ambos con precios vigentes, **When** el consumidor consulta la comparación con el ordenamiento por defecto (`precio_unitario`), **Then** el establecimiento A se posiciona primero en los resultados por tener menor precio por unidad base.
2. **Given** que un establecimiento cuenta únicamente con reportes cuya antigüedad está entre 8 y 30 días, **When** el consumidor consulta la comparación de dicho producto, **Then** dicho establecimiento se muestra en el bloque secundario al final de la lista identificado con el sello `desactualizado`.
3. **Given** que un reporte tiene más de 30 días desde su observación, **When** se consulta la comparación activa de precios, **Then** ese dato queda excluido de la comparación activa y permanece únicamente visible en el historial.

---

### User Story 2 - Registrar un precio rápidamente frente a la góndola (Priority: P1)

Como reportante autenticado que ha aceptado la política de tratamiento de datos personales, quiero registrar el precio de una presentación en un establecimiento en 15 segundos o menos con un formulario mínimo de 3 controles, incluso bajo condiciones de conectividad móvil intermitente o ausente en el interior del local comercial.

**Why this priority**: La viabilidad de una plataforma colaborativa depende de la facilidad y rapidez con la que los usuarios aportan datos en el punto físico de compra sin fricción.

**Independent Test**: Puede probarse de forma independiente completando el formulario de reporte con 3 campos en modo en línea y en modo avión, comprobando que en ambos casos el dato se capture y que la cola de envío sincronice de forma idempotente sin duplicar registros.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado con autorización de datos vigente en la pantalla de reporte, **When** selecciona establecimiento, presentación, digita el precio de $2.600 COP y pulsa «Guardar precio» con una clave de idempotencia (`Idempotency-Key`) única, **Then** el sistema confirma la creación con éxito (`201 Created`) y actualiza el precio vigente en menos de 60 segundos (`EC-02`).
2. **Given** que el dispositivo móvil pierde conectividad antes del envío, **When** el reportante pulsa «Guardar precio» y posteriormente se restablece la conexión reintentando la petición dos veces con la misma clave de idempotencia, **Then** el sistema almacena un único registro en la base histórica y responde confirmación exitosa (`200 OK`) en los reintentos posteriores sin duplicar filas.
3. **Given** que el usuario adjunta una fotografía como prueba, **When** el dispositivo recupera la red, **Then** el sincronizador sube primero la fotografía a su URL firmada y, solo tras completar la carga, envía el reporte con la referencia remota de la imagen.

---

### User Story 3 - Filtrar reportes anómalos o ataques coordinados (Priority: P1)

Como moderador de la plataforma, quiero que el sistema evalúe determinísticamente cada reporte ingresado para impedir que errores de digitación, precios atípicos o ráfagas coordinadas de cuentas falsas alteren el precio vigente sin revisión previa, presentándolos en una bandeja priorizada para auditoría humana.

**Why this priority**: Protege la integridad y credibilidad de la plataforma frente a información errónea o intentos de manipulación malintencionada por parte de actores con intereses comerciales.

**Independent Test**: Puede probarse enviando precios extremos fuera de rango o divergentes frente a la mediana de referencia, y simulando envíos desde una misma huella de red con múltiples cuentas, verificando que los reportes queden en estado de revisión y no modifiquen el precio público vigente.

**Acceptance Scenarios**:

1. **Given** una presentación de producto que cuenta con 6 reportes recientes cuya mediana es de $2.600 COP, **When** un usuario reporta un valor atípico de $900 COP (|M| > 3.5 mediante z-score modificado), **Then** el reporte se clasifica automáticamente con estado `dudoso`, no altera el precio vigente del establecimiento, genera un caso en la bandeja de moderación y al usuario reportante se le informa "Recibido, en revisión".
2. **Given** que 3 cuentas de usuario distintas envían reportes hacia el mismo establecimiento desde la misma huella de red en un lapso inferior a 30 minutos, **When** ingresa el tercer reporte, **Then** el sistema activa la señal `rafaga`, reclasifica hacia atrás a estado `dudoso` los reportes de esa ventana hacia ese establecimiento, recalcula el precio vigente y abre un caso prioritario de moderación.
3. **Given** un reporte marcado como `dudoso` por el motor determinista, **When** un moderador humano lo revisa y confirma su invalidez, **Then** el reporte se descarta definitivamente, se actualiza la reputación del usuario y queda constancia inmutable en la bitácora de auditoría.

---

### User Story 4 - Ejercer derechos de Ley 1581 de 2012 (Priority: P2)

Como titular de datos personales registrado en la plataforma, quiero tener la facultad de consultar mis datos, modificar mi alias público o solicitar la supresión definitiva de mi cuenta, garantizando que mis reportes históricos queden completamente anonimizados y mis fotos eliminadas.

**Why this priority**: Es un mandato legal ineludible en Colombia que asegura el respeto a la privacidad, el derecho al olvido y la autodeterminación informativa del ciudadano.

**Independent Test**: Puede probarse creando una cuenta, registrando reportes con fotografías adjuntas y ejecutando la solicitud de eliminación de cuenta, comprobando que la credencial se elimine, el alias cambie a un identificador anónimo, las imágenes se borren y los reportes históricos desvinculen al usuario.

**Acceptance Scenarios**:

1. **Given** un usuario registrado con reportes y fotografías históricas publicadas, **When** solicita la supresión de su cuenta a través de su perfil, **Then** sus filas en la tabla histórica de reportes desvinculan su identificador de usuario (`reportante_id = null`), las fotografías se borran físicamente del almacenamiento, su alias se reemplaza por un seudónimo anónimo irreversible, la autorización se marca como revocada y las credenciales de acceso se eliminan del sistema de autenticación.
2. **Given** un usuario registrado que desea actualizar su alias visible, **When** modifica su alias por uno disponible que cumple las reglas de formato, **Then** el alias se actualiza de inmediato para futuras consultas y los reportes anteriores exhiben el nuevo alias.

---

### User Story 5 - Gestionar catálogo y sugerencias de productos (Priority: P2)

Como consumidor o comerciante, quiero consultar un catálogo normalizado de productos y presentaciones de la canasta familiar y tener la posibilidad de sugerir presentaciones faltantes o reportar inconsistencias en los datos de un establecimiento, para que el equipo de moderación verifique e incorpore información confiable.

**Why this priority**: Mantiene la calidad del catálogo cerrado, evita la proliferación caótica de productos duplicados con nombres informales y permite expandir la cobertura de presentaciones locales.

**Independent Test**: Puede probarse enviando una sugerencia de presentación con multiplicador y unidad (ej. "Arroz 1/2 kg"), verificando que el moderador la apruebe y el sistema precalcule de forma exacta su equivalencia en la unidad base del producto.

**Acceptance Scenarios**:

1. **Given** que un usuario envía una sugerencia para crear la presentación "Arroz Roa 1/2 kg" asociada al producto genérico "Arroz blanco" (unidad base: gramo), **When** el moderador revisa y aprueba la sugerencia, **Then** el sistema calcula y almacena la cantidad base exacta de 500 gramos, activa la nueva presentación en el catálogo oficial y genera un registro de auditoría.
2. **Given** un ciudadano que detecta que los datos de dirección o denominación de una tienda de barrio están errados, **When** envía una solicitud de corrección desde la ficha del establecimiento, **Then** el sistema genera un caso en la bandeja de moderación con los datos aportados para su validación manual.

---

### Edge Cases

- **Precios fuera de límites económicos razonables**: Si un usuario intenta reportar un precio inferior a $50 COP o superior a $2.000.000 COP, el sistema rechaza la solicitud de inmediato sin almacenarla, informando que el valor se encuentra fuera del rango permitido.
- **Fechas futuras o excesivamente antiguas**: Si un reporte incluye una marca temporal en el futuro (con tolerancia superior a 60 segundos por desalineación de reloj) o una antigüedad mayor a 24 horas hacia atrás, la petición es rechazada por fecha inválida.
- **Pérdida absoluta de conectividad**: Si el dispositivo móvil carece de red al momento de pulsar «Guardar precio», el formulario no bloquea al usuario; la transacción se resguarda en almacenamiento local persistente (`IndexedDB`) y se despacha de forma desatendida cuando el navegador detecte el evento de conexión en línea.
- **Unidades de medida incompatibles**: Si se intenta asociar una presentación en unidades de volumen (ej. mililitros) a un producto cuya unidad base es de masa (ej. gramos), el sistema bloquea la operación indicando incompatibilidad dimensional.
- **Búsquedas imprecisas o con errores tipográficos**: Cuando un consumidor busca términos con tildes omitidas, mayúsculas arbitrarias, errores de ortografía leves o expresiones fraccionarias comunes ("arroz 1/2 kilo"), el motor de búsqueda identifica y entrega la familia de productos correcta en menos de 300 milisegundos.
- **Ataque en ráfaga con cuentas múltiples**: Si un atacante utiliza varias cuentas creadas recientemente para enviar reportes coordinados hacia una misma tienda desde la misma huella de red en una ventana de 30 minutos, el sistema detecta el patrón, neutraliza el impacto marcándolos en revisión e impide la alteración del precio vigente.
- **Escasez de datos de referencia (respaldo `sin_referencia`)**: Cuando una presentación o producto nuevo carece del mínimo de reportes aceptados en los últimos 14 días en los niveles de tienda, municipio o producto unitario, el sistema adopta el estado de contingencia `sin_referencia`, evitando falsos positivos por falta de muestra estadística.
- **Duplicidad por reintento de red**: Si por inestabilidad de red el cliente reenvía la misma petición de reporte varias veces con la misma clave de idempotencia, el sistema procesa únicamente la primera transacción y devuelve confirmación exitosa sin crear filas redundantes.
- **Consultas con geolocalización**: Cuando el consumidor envía coordenadas de latitud y longitud para ordenar por cercanía, el sistema utiliza las coordenadas estrictamente en memoria volátil para el cálculo de distancia y filtra los resultados según el radio solicitado, garantizando que las coordenadas jamás se persistan en base de datos ni queden en registros de auditoría o trazas de ejecución.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema **MUST** almacenar cada producto con una única unidad de medida base (`g`, `ml` o `unidad`) y cada presentación con su `cantidad_base` precalculada, exacta e inmutable.
- **FR-002**: El sistema **MUST** normalizar y convertir las unidades de entrada admitidas (`g`, `kg`, `lb` colombiana = 500 g, `ml`, `l`, `unidad`, `docena`) utilizando aritmética decimal exacta y rechazar unidades incompatibles con la dimensión del producto.
- **FR-003**: El sistema **MUST** permitir la búsqueda y exploración de productos y presentaciones ignorando mayúsculas, diacríticos y tildes, tolerando errores tipográficos y reconociendo expresiones fraccionarias habituales.
- **FR-004**: El sistema **MUST** exigir la aceptación previa, expresa e informada de la política de tratamiento de datos personales antes de registrar el perfil de un usuario o permitir la creación de reportes de precios.
- **FR-005**: El sistema **MUST** determinar los privilegios y roles de usuario consultando exclusivamente el perfil verificado en la base de datos y jamás a partir de metadatos manipulables del cliente.
- **FR-006**: El sistema **MUST** proveer a todo titular de datos la funcionalidad para consultar sus datos personales registrados, actualizar su alias público y solicitar la supresión de su cuenta.
- **FR-007**: Al tramitar la eliminación de una cuenta, el sistema **MUST** desvincular de forma definitiva al usuario de sus reportes históricos, borrar las fotografías de prueba alojadas, reemplazar el alias por un identificador anónimo irreversible, registrar la revocación de la autorización y eliminar la credencial de autenticación.
- **FR-008**: El sistema **MUST** exigir una clave de idempotencia única en cada registro de reporte y devolver la respuesta original sin duplicar información cuando la misma clave sea enviada nuevamente por el mismo usuario.
- **FR-009**: El sistema **MUST** validar que todo precio reportado sea un número entero estricto dentro del rango económico admisible configurado en los parámetros de la plataforma.
- **FR-010**: El sistema **MUST** verificar que la fecha y hora de observación del precio no corresponda a un tiempo futuro ni supere el límite máximo de antigüedad permitido respecto a la hora de recepción.
- **FR-011**: El sistema **MUST** suprimir la totalidad de metadatos EXIF (especialmente coordenadas de geolocalización satelital) de cualquier fotografía de prueba antes de su almacenamiento definitivo.
- **FR-012**: El sistema **MUST** asegurar a nivel de persistencia que las tablas de evidencia histórica sean de sólo inserción (*append-only*), bloqueando modificaciones o eliminaciones de los reportes originales.
- **FR-013**: El sistema **MUST** evaluar la consistencia de cada reporte seleccionando jerárquicamente su conjunto de referencia en tres niveles (misma tienda, mismo municipio o mismo producto por unidad base) y recurrir al estado de contingencia `sin_referencia` si ningún nivel reúne la muestra mínima requerida en la ventana temporal activa.
- **FR-014**: El sistema **MUST** evaluar anomalías estadísticas de precios aplicando la metodología de *z-score* modificado cuando la muestra cuente con 5 o más observaciones y dispersión no nula, o mediante desviación porcentual frente a la mediana cuando la muestra sea de 3 a 4 observaciones o carezca de dispersión absoluta.
- **FR-015**: El sistema **MUST** calcular la huella de red del cliente utilizando un algoritmo criptográfico HMAC con clave secreta rotativa diaria y purgar de manera definitiva dicho identificador tras 30 días de antigüedad.
- **FR-016**: Al detectarse una concentración inusual de reportes (ráfaga) provenientes de una misma huella de red hacia un mismo establecimiento en una ventana de 30 minutos, el sistema **MUST** reclasificar a estado `dudoso` los reportes de dicha ventana, recalcular el precio vigente y priorizar el caso para moderación.
- **FR-017**: El sistema **MUST** resguardar la confidencialidad de los criterios de detección, mostrando al reportante estados neutrales como "recibido" o "en revisión" sin revelar señales internas de riesgo o sospecha de fraude.
- **FR-018**: El sistema **MUST** recalcular de manera transaccional e inmediata la fila de precio vigente ante cualquier nuevo reporte aceptado o resolución de moderación, e invalidar la caché de comparación en menos de 60 segundos.
- **FR-019**: El sistema **MUST** presentar los resultados de comparación estructurados en dos bloques claramente diferenciados: un primer bloque con precios vigentes y sellos confiables, y un segundo bloque final con datos dudosos o desactualizados, ordenando cada bloque por precio por unidad de medida base por defecto.
- **FR-020**: El sistema **MUST** procesar las coordenadas geográficas enviadas por consumidores en búsquedas públicas estrictamente en memoria volátil para calcular proximidad espacial, garantizando que jamás se guarden en base de datos ni queden en registros de auditoría.
- **FR-021**: El sistema **MUST** registrar una entrada inmutable de auditoría por cada decisión de moderación humana, aplicación de sanciones disciplinarias o ajuste de parámetros operativos de la plataforma.

---

### Key Entities *(include if feature involves data)*

- **Producto**: Familia genérica de un bien de consumo de la canasta familiar (ej. "Arroz blanco", "Leche entera", "Aceite vegetal"). Posee una única `unidad_base` normalizada (`g`, `ml` o `unidad`) y categoría asignada.
- **Presentación**: Variante comercial específica de un producto, caracterizada por su marca comercial, contenido neto, multiplicador de empaque y una `cantidad_base` precalculada expresada en la unidad base de su producto padre.
- **Establecimiento**: Punto físico de venta (tienda de barrio, minimercado o supermercado) geolocalizado con coordenadas geográficas fijas y dirección dentro del municipio.
- **ReportePrecio**: Evidencia inmutable de un precio observado por un consumidor en un establecimiento para una presentación concreta en una fecha determinada. Incluye precio en pesos COP, estado de validación (`aceptado`, `dudoso`, `descartado`), fotografía opcional sin EXIF, clave de idempotencia y huella de red procesada con HMAC.
- **PrecioVigente**: Modelo de lectura optimizado y precalculado que almacena el valor de referencia actual de un producto o presentación en un establecimiento, su sello de confiabilidad (`confiable`, `pocos_datos`, `desactualizado`, `dudoso`), fecha de actualización y cálculo de precio por unidad de medida base.
- **Perfil**: Cuenta de usuario registrada con seudónimo o alias visible, fecha de vinculación, rol asignado (`consumidor`, `reportante`, `moderador`), reputación calculada mediante modelo bayesiano y estado de cuenta (`activa`, `suspendida`, `eliminada`).
- **AutorizacionDatos**: Registro legal de consentimiento previo, expreso e informado bajo la Ley 1581 de 2012, con versión de la política aceptada, fecha de otorgamiento y campo de fecha de revocación.
- **CasoModeracion**: Expediente generado de forma automática o por sugerencia de usuarios para revisión humana de reportes dudosos, ráfagas coordinadas, creación de presentaciones o correcciones a establecimientos.
- **Auditoria**: Bitácora inmutable de eventos sensibles que documenta autor, acción, entidad afectada, estado previo y posterior, y fecha exacta del suceso.
- **ConfigParametro**: Tabla centralizada de parámetros y umbrales operativos del negocio, leída dinámicamente sin valores cableados en el código.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (Operabilidad y Rapidez de Registro — EC-01)**: Al menos el 80 % de los intentos de registro de precios (8 de cada 10) realizados por usuarios reales en pasillo con conectividad móvil limitada se completan satisfactoriamente en 15 segundos o menos.
- **SC-002 (Actualidad del Dato — EC-02)**: Cuando el precio de un producto cambia o es invalidado, la comparación pública deja de mostrar el valor anterior y exhibe el nuevo precio vigente en un tiempo igual o inferior a 60 segundos en el 100 % de las ejecuciones evaluadas.
- **SC-003 (Credibilidad e Integridad — EC-03)**: El motor determinista de evaluación detecta y contiene al menos el 90 % (9 de cada 10) de los reportes anómalos individuales y al menos el 70 % (7 de cada 10) de los ataques coordinados grupales, manteniendo una tasa de falsos positivos inferior al 10 % sobre reportes honestos. Ningún dato anómalo se presenta como vigente sin advertencia.
- **SC-004 (Eficiencia de Desempeño — EC-04)**: Durante picos de alta demanda con 500 usuarios concurrentes consultando comparaciones, el percentil 95 (p95) del tiempo de respuesta se mantiene en 2 segundos o menos, con una tasa global de error inferior al 1 %.
- **SC-005 (Mantenibilidad y Preparación para el Cambio — EC-05)**: La incorporación posterior del módulo comercial sobre el núcleo construido no requerirá ningún rediseño estructural en las tablas ni en el dominio del núcleo, preservando limpios los tres puntos de extensión arquitectónica definidos.
- **SC-006 (Neutralidad Comercial Absoluta — EC-06)**: El orden de clasificación de los resultados de comparación es 100 % idéntico con y sin publicaciones comerciales activas, y la totalidad de la información comercial viaja en una colección separada y claramente etiquetada.

---

## Assumptions

- **Población y Cobertura Geográfica**: El despliegue inicial concentra su cobertura de datos en el municipio de Armenia y municipios aledaños del departamento del Quindío.
- **Conectividad Intermitente**: Se asume que los establecimientos comerciales cerrados presentan zonas con cobertura celular débil o nula, por lo que la cola de almacenamiento local en el dispositivo es indispensable.
- **Naturaleza de los Precios**: Todos los precios corresponden al mercado minorista de bienes de consumo masivo de la canasta familiar expresados en pesos colombianos e incluyen los impuestos aplicables.
- **Acceso Público a la Consulta**: Cualquier persona puede consultar y comparar precios sin necesidad de registrarse ni autenticarse; únicamente se exige autenticación y autorización de datos para registrar reportes o emitir sugerencias.
- **Datos Iniciales**: Antes de contar con una masa crítica de usuarios reportantes, el sistema se abastece de una carga semilla inicial de productos y establecimientos reales bajo licencia abierta y datos de prueba claramente rotulados con advertencia visual visible.
- **Infraestructura de Costo Cero**: Se asume que el sistema opera bajo los límites de capas gratuitas de servicios en la nube (Supabase, Upstash y Vercel), optimizando el volumen de almacenamiento y comandos de red mediante caché de dos niveles.
