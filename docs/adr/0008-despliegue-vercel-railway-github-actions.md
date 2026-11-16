# ADR-008: Despliegue en Vercel, Contenedor Docker en Railway y Jobs en GitHub Actions

## Estado
Aceptado

## Contexto
El proyecto opera bajo la restricción estricta de **presupuesto $0 USD** para infraestructura de desarrollo y demostración académica. Se requiere alojar el frontend de Next.js con soporte Edge/SSR, ejecutar el backend FastAPI en un entorno contenedorizado estable y ejecutar tareas de mantenimiento periódicas (ping a la base de datos para prevenir hibernación, cálculo de reputación y purga de huellas).

## Alternativas consideradas
1. **Servidor VPS dedicado único (ej. DigitalOcean, AWS EC2):** Costo mensual recurrente desde el día uno ($6-$12 USD/mes) sin financiamiento disponible.
2. **Plataformas PaaS integradas con Docker (Heroku legado):** Planes gratuitos eliminados.
3. **Arquitectura distribuida en capas gratuitas (Vercel + Railway + GitHub Actions):**
   - Frontend en **Vercel Hobby** (CDN global, SSL automático, optimización de imágenes y despliegue continuo desde rama Git).
   - Backend en **Railway** mediante contenedor Docker multi-etapa utilizando los $5 USD iniciales de prueba gratuita.
   - Automatización de tareas periódicas mediante cron jobs en **GitHub Actions** (`jobs.yml`).

## Decisión
Desplegar el frontend en **Vercel** conectado al repositorio de GitHub, empaquetar el backend de FastAPI en un **contenedor Docker multi-etapa** estandarizado desplegado en Railway (con fallback documentado a Render o Fly.io en ADR-017), y programar los jobs de fondo (`ping_bd`, `recalcular_reputacion`, `limpiar_huellas`) a través de workflows programados en **GitHub Actions**.

## Consecuencias
### Positivas
- Infraestructura 100 % operativa a costo cero para el equipo.
- Separación de responsabilidades: caídas del backend no afectan la entrega del frontend y viceversa.
- Ejecución desatendida y confiable de tareas de mantenimiento sin mantener procesos daemon costosos en memoria.

### Negativas
- Posible latencia de arranque en frío (*cold start*) si la plataforma duerme el contenedor por inactividad.
