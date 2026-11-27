# Evidencia EC-11 — Simulacro de latencia y alerta SLO

Esta carpeta contiene la evidencia reproducible del escenario `EC-11`.

## Archivos

| Archivo | Contenido |
|---|---|
| `k6_ec11_summary.json` | Resumen exportado por k6 del simulacro de 200 VUs durante 3 minutos. |
| `slo-comparador-staging.yml` | Copia de las reglas de SLO/alerta usadas en staging (sin secretos). |
| `alerta_firing.png` | Captura de `ComparadorSLOComparacionIncumplidoStaging` en estado `Firing`. |
| `traza_lenta.png` | Captura de una traza de 4.8 s en el servicio `comparador-precios-backend-staging`. |
| `trazas_linea_base.png` | Captura de trazas rápidas (2–3 ms) para contraste. |
| `sli_staging.png` | Opcional/pendiente: captura de `comparador:sli_comparacion_7d_staging = 0`. |
| `presupuesto_staging.png` | Opcional/pendiente: captura del presupuesto al 100 %. |
| `tablero_produccion.png` | Opcional/pendiente: captura del tablero de producción sano. |

## Datos del simulacro

- Fecha: 2026-11-26/27.
- Servicio staging: `https://comparador-precios-vfsz.onrender.com`.
- `ENTORNO=pruebas`, `SIMULAR_LATENCIA_MS=3000`.
- Servicio OTel: `comparador-precios-backend-staging`.
- k6: 200 VUs, 3 minutos, 5.934 iteraciones, 0 % errores HTTP.
- Latencia k6: p95 = 6.79 s, máximo = 25.5 s.
- SLI staging: 0. Presupuesto consumido: 100 %.
- Traza ejemplo: `9511fb3ec363418b15cb551dc4f3deb1`, span `GET /v1/productos/{id}/comparacion`, 4.80 s.

## Producción

- Servicio: `https://comparador-precios-api-f0hh.onrender.com`.
- SLI de producción al momento del simulacro: 0.9981.
- p95 de historial con 100 puntos: 272.40 ms.
- El simulacro se ejecutó contra staging para no contaminar el SLO de producción.
