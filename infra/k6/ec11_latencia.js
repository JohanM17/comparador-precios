// Escenario de latencia para el simulacro EC-11 (Tarea T-123).
//
// Terminal 1: backend con latencia inyectada y OTLP configurado, solo en pruebas:
//   ENTORNO=pruebas SIMULAR_LATENCIA_MS=3000 \
//     OTEL_EXPORTER_OTLP_ENDPOINT="<endpoint-otlp>" \
//     OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <credencial>" \
//     uv --directory backend run uvicorn app.main:app --port 8000
//
// Terminal 2: carga de 200 VUs durante 3 minutos:
//   k6 run infra/k6/ec11_latencia.js
//
// En setup() se resuelve un producto real del seed:
//   GET /v1/productos?q=arroz&limite=1  ->  datos[0].id
// Se usa `arroz` porque el seed incluye "Arroz blanco tradicional" y otras
// variedades. Si la busqueda no devuelve productos, el escenario falla con un
// error explicito en lugar de generar carga contra un UUID inexistente.
//
// PRODUCTO_ID es un override opcional. El UUID de ejemplo de los contratos es
// 3b241101-e2bb-4255-8caf-4136c566a962, pero NO es un ID fijo del seed:
// scripts/semilla.py inserta los productos sin id y PostgreSQL genera UUIDs
// aleatorios. Si se usa el override, confirma el ID real con:
//   SELECT id, nombre FROM producto WHERE nombre = 'Arroz blanco tradicional';
//   BASE_URL=http://127.0.0.1:8000 PRODUCTO_ID=<uuid-real> \
//     k6 run infra/k6/ec11_latencia.js
//
// El threshold solo controla errores HTTP, no latencia: durante el simulacro se
// espera que la latencia supere el SLO de 2 s y que la alerta
// ComparadorSLOComparacionIncumplido se dispare en <= 5 minutos. Un threshold
// de latencia haria fallar k6 justo por el comportamiento buscado. La validacion
// real de la alerta es T-126.

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const PRODUCTO_ID_OVERRIDE = (__ENV.PRODUCTO_ID || "").trim();

export const options = {
  scenarios: {
    comparacion_ec11: {
      executor: "constant-vus",
      vus: 200,
      duration: "3m",
      gracefulStop: "10s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
  },
};

export function setup() {
  if (PRODUCTO_ID_OVERRIDE) {
    return { productoId: PRODUCTO_ID_OVERRIDE };
  }

  const busqueda = http.get(`${BASE_URL}/v1/productos?q=arroz&limite=1`);
  if (busqueda.status !== 200) {
    throw new Error(
      `No se pudo resolver un producto para EC-11: ` +
        `GET /v1/productos respondio ${busqueda.status}. ` +
        `Verifica el backend y BASE_URL=${BASE_URL}.`,
    );
  }

  let cuerpo;
  try {
    cuerpo = busqueda.json();
  } catch (error) {
    throw new Error("La busqueda de productos no devolvio JSON valido.");
  }

  const productos = cuerpo && Array.isArray(cuerpo.datos) ? cuerpo.datos : [];
  if (productos.length === 0 || !productos[0].id) {
    throw new Error(
      "La busqueda de productos no devolvio resultados. " +
        "Ejecuta el seed o define PRODUCTO_ID con un UUID real.",
    );
  }

  return { productoId: productos[0].id };
}

export default function simularLatenciaEc11(datos) {
  const respuesta = http.get(
    `${BASE_URL}/v1/productos/${datos.productoId}/comparacion?orden=precio_unitario`,
    { tags: { endpoint: "comparacion" } },
  );
  check(respuesta, {
    "comparacion responde 200": (r) => r.status === 200,
  });
  sleep(1);
}
