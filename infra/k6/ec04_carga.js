import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const TOKEN_REPORTANTE = __ENV.TOKEN_REPORTANTE || "";
const PRESENTACION_ID =
  __ENV.PRESENTACION_ID || "11111111-1111-1111-1111-111111111111";
const ESTABLECIMIENTO_ID =
  __ENV.ESTABLECIMIENTO_ID || "22222222-2222-2222-2222-222222222222";
const PRODUCTO_ID =
  __ENV.PRODUCTO_ID || "3b241101-e2bb-4255-8caf-4136c566a962";

export const options = {
  stages: [
    { duration: "2m", target: 500 },
    { duration: "5m", target: 500 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<2000"],
  },
};

function generarUuidV4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function consultarCatalogo() {
  const res = http.get(`${BASE_URL}/v1/productos?limite=20`, {
    tags: { endpoint: "catalogo" },
  });
  check(res, { "catalogo status 200": (r) => r.status === 200 });
}

function consultarComparacion() {
  const res = http.get(
    `${BASE_URL}/v1/productos/${PRODUCTO_ID}/comparacion?orden=precio_unitario`,
    { tags: { endpoint: "comparacion" } },
  );
  check(res, { "comparacion status 200": (r) => r.status === 200 });
}

function consultarTiendas() {
  const res = http.get(`${BASE_URL}/v1/establecimientos?limite=20`, {
    tags: { endpoint: "establecimientos" },
  });
  check(res, { "tiendas status 200": (r) => r.status === 200 });
}

function registrarReporte() {
  if (!TOKEN_REPORTANTE) {
    consultarComparacion();
    return;
  }
  const carga = JSON.stringify({
    presentacion_id: PRESENTACION_ID,
    establecimiento_id: ESTABLECIMIENTO_ID,
    precio_cop: 4800 + ((__VU + __ITER) % 25) * 50,
    observado_en: new Date().toISOString(),
    foto_ruta: null,
  });
  const res = http.post(`${BASE_URL}/v1/reportes`, carga, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${TOKEN_REPORTANTE}`,
      "Idempotency-Key": generarUuidV4(),
    },
    tags: { endpoint: "reportes" },
  });
  check(res, { "reporte 201 o 429 controlado": (r) => r.status === 201 || r.status === 429 });
}

export default function ejecutarCargaEc04() {
  const sorteo = Math.random();
  if (sorteo < 0.60) {
    consultarCatalogo();
  } else if (sorteo < 0.90) {
    consultarComparacion();
  } else if (sorteo < 0.95) {
    consultarTiendas();
  } else {
    registrarReporte();
  }
  sleep(1 + Math.random() * 2);
}

