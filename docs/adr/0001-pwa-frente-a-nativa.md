# ADR-001: PWA Responsive Mobile-First frente a App Móvil Nativa

## Estado
Aceptado

## Contexto
El comparador de precios está dirigido a consumidores y familias de Armenia (Quindío) que necesitan consultar y registrar precios frente a la góndola en supermercados y tiendas de barrio. Desarrollar apps nativas independientes (iOS/Swift y Android/Kotlin) o híbridas con tiendas de aplicaciones (Play Store / App Store) incrementa la fricción de adopción (descarga de 50+ MB, registro de cuentas de desarrollador, comisiones y tiempos de aprobación de revisiones de tiendas).

## Alternativas consideradas
1. **App Nativa (Android/Kotlin + iOS/Swift):** Mejor acceso a hardware pero costo de desarrollo y mantenimiento doble para un equipo de 4 personas.
2. **Framework Híbrido (React Native / Flutter):** Base de código única pero requiere empaquetado, distribución en tiendas y almacenamiento significativo en teléfonos de gama de entrada.
3. **PWA Responsive Mobile-First (Next.js + Web App Manifest):** Acceso web instantáneo con URL, instalable con un toque, consumo de almacenamiento < 5 MB y soporte de capacidades offline vía `Service Worker` e `IndexedDB`.

## Decisión
Adoptar una **PWA (Progressive Web App) Responsive Mobile-First** construida con Next.js (App Router), Tailwind CSS y `manifest.webmanifest`. Se diseñan todas las pantallas priorizando dispositivos móviles (pantallas táctiles con objetivos de clic $\ge 44 \times 44$ px según WCAG 2.2 AA) con adaptación fluida a pantallas de escritorio.

## Consecuencias
### Positivas
- Acceso inmediato sin descarga obligatoria desde tiendas de aplicaciones.
- Capacidad de instalación en pantalla de inicio en Android e iOS.
- Soporte para captura offline de precios mediante `IndexedDB` (`EC-01`).
- Ciclo de despliegue continuo instantáneo en web sin esperas de aprobación.

### Negativas
- Restricciones menores de APIs de fondo en iOS Safari (requiere sincronización en primer plano al recuperar red).
