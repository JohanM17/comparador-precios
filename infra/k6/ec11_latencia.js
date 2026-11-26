// Escenario de latencia para el simulacro EC-11 (Tarea T-123).
//
// Terminal 1: backend con latencia inyectada y OTLP configurado, solo en pruebas:
//   ENTORNO=pruebas SIMULAR_LATENCIA_MS=3000 \
//     uv --directory backend run uvicorn app.main:app --port 8000
//
// Terminal 2: carga de 200 VUs durante 3 minutos:
//   k6 run infra/k6/ec11_latencia.js
//   BASE_URL=http://127.0.0.1:8000 PRODUCTO_ID=<uuid> k6 run infra/k6/ec11_latencia.js
//
// UUID de ejemplo de los contratos y del seed (arroz blanco tradicional):
//   3b241101-e2bb-4255-8caf-4136c566a962
// El seed genera los IDs al ejecutarse; confirma el tuyo con:
//   SELECT id, nombre FROM producto WHERE nombre = 'Arroz blanco tradicional';
//
// Sin thresholds a proposito: durante el simulacro se espera que la latencia
// supere el SLO de 2 s y que la alerta ComparadorSLOComparacionIncumplido se
// dispare en <= 5 minutos. La validacion real de la alerta es T-126; un
// threshold aqui haria fallar k6 justo por el comportamiento esperado.

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const PRODUCTO_ID =
  __ENV.PRODUCTO_ID || "3b241101-e2bb-4255-8caf-4136c566a962";

export const options = {
  scenarios: {
    comparacion_ec11: {
      executor: "constant-vus",
      vus: 200,
      duration: "3m",
      gracefulStop: "10s",
    },
  },
};

export default function simularLatenciaEc11() {
  const respuesta = http.get(
    `${BASE_URL}/v1/productos/${PRODUCTO_ID}/comparacion?orden=precio_unitario`,
    { tags: { endpoint: "comparacion" } },
  );
  check(respuesta, {
    "comparacion responde 200": (r) => r.status === 200,
  });
  sleep(1);
}
