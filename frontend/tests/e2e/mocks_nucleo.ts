import type { Page, Route } from "@playwright/test";

export const PROD_ID = "3b241101-e2bb-4255-8caf-4136c566a962";
export const PRES_500 = "7c9e6679-7425-40de-944b-e07fc1f90ae7";
export const PRES_1000 = "8d0f7780-8536-51ef-a55c-f18fd2fa1bf8";
export const TIENDA_A = "11111111-2222-3333-4444-555555555555";
export const TIENDA_B = "22222222-3333-4444-5555-666666666666";
export const CASO_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

export type OrigenHistorialMock = "usuario" | "comercio" | "semilla";
export type EstadoHistorialMock = "aceptado" | "dudoso";

export interface PuntoHistorialMock {
  readonly id: string;
  readonly observado_en: string;
  readonly precio_cop: number;
  readonly precio_por_unidad: {
    readonly valor_cop: number;
    readonly por: "kg" | "l" | "unidad";
  };
  readonly origen: OrigenHistorialMock;
  readonly estado: EstadoHistorialMock;
  readonly es_demo: boolean;
  readonly presentacion_id: string | null;
  readonly cantidad_base: number;
}

export interface RespuestaHistorialMock {
  readonly datos: {
    readonly producto: {
      readonly id: string;
      readonly nombre: string;
      readonly unidad_base: "g";
      readonly unidad_visualizacion: "kg";
    };
    readonly establecimiento: {
      readonly id: string;
      readonly nombre: string;
      readonly municipio: string;
    };
    readonly presentacion: null;
    readonly desde: string;
    readonly hasta: string;
    readonly puntos: readonly PuntoHistorialMock[];
    readonly total: number;
    readonly truncado: boolean;
    readonly datos_de_demostracion: boolean;
  };
}

export interface OpcionesHistorialMock {
  readonly puntos?: readonly PuntoHistorialMock[];
  readonly truncado?: boolean;
  readonly datos_de_demostracion?: boolean;
  readonly desde?: string;
  readonly hasta?: string;
}

export interface OpcionesMock {
  rol?: "reportante" | "moderador" | "comercio";
  /** Presentaciones que el modo rapido muestra para la tienda del comercio. */
  presentacionesComercio?: number;
  alPublicarPrecios?: (cuerpo: unknown) => void;
  autorizadoInicial?: boolean;
  alCrearReporte?: (headers: Record<string, string>, cuerpo: unknown) => void;
  alResolverCaso?: (cuerpo: unknown) => void;
}

interface EstadoMock {
  autorizado: boolean;
  casoResuelto: boolean;
  readonly rol: "reportante" | "moderador" | "comercio";
  readonly opts: OpcionesMock;
}

function construirComparacion(): unknown {
  const ahora = new Date().toISOString();
  return {
    datos: {
      producto: {
        id: PROD_ID, nombre: "Arroz blanco", categoria_id: 1, unidad_base: "g", unidad_visualizacion: "kg",
        presentaciones: [
          { id: PRES_1000, etiqueta: "Arroz Diana 1 kg", marca: "Diana", cantidad_base: 1000 },
          { id: PRES_500, etiqueta: "Arroz Diana 500 g", marca: "Diana", cantidad_base: 500 },
        ],
      },
      resultados: [
        {
          establecimiento: { id: TIENDA_A, nombre: "Tienda La Esquina", tipo: "tienda_barrio", barrio: "Centro", direccion: "Cra 14 # 18-22", distancia_m: 420 },
          presentacion: { id: PRES_1000, etiqueta: "Arroz Diana 1 kg", marca: "Diana", cantidad_base: 1000 },
          precio_cop: 5000, precio_oficial_cop: null, precio_por_unidad: { valor_cop: 5000, por: "kg" },
          sello: "confiable", motivo_sello: null, n_reportes_validos: 4, n_fuentes: 3, ultimo_reporte_en: ahora, con_foto_prueba: true, es_bloque_secundario: false,
        },
        {
          establecimiento: { id: TIENDA_B, nombre: "Supermercado Central", tipo: "supermercado", barrio: "Norte", direccion: "Av Bolivar 10-20", distancia_m: 980 },
          presentacion: { id: PRES_500, etiqueta: "Arroz Diana 500 g", marca: "Diana", cantidad_base: 500 },
          precio_cop: 2800, precio_oficial_cop: null, precio_por_unidad: { valor_cop: 5600, por: "kg" },
          sello: "desactualizado", motivo_sello: "Sin reportes recientes", n_reportes_validos: 1, n_fuentes: 1, ultimo_reporte_en: ahora, con_foto_prueba: false, es_bloque_secundario: true,
        },
      ],
      promociones: [{
        id: "promo-1", titulo: "Pague 2 lleve 3 en Supermercado Central", condiciones: "Valido viernes",
        porcentaje_descuento: 15, establecimiento_nombre: "Supermercado Central", presentacion_etiqueta: "Arroz Diana 500 g", hasta_revocar: true,
      }],
      meta: {
        criterio_orden: "precio_unitario",
        texto_neutralidad: "Ordenado por precio por kg. Las promociones no cambian el orden.",
        bloques: ["vigentes", "dudosos_y_desactualizados"], generado_en: ahora, datos_de_demostracion: false,
      },
    },
  };
}

function haceDias(dias: number): string {
  return new Date(Date.now() - dias * 86_400_000).toISOString();
}

function crearPuntoHistorial(
  id: string,
  diasAtras: number,
  precioCop: number,
  origen: OrigenHistorialMock,
  estado: EstadoHistorialMock,
  esDemo: boolean
): PuntoHistorialMock {
  return {
    id,
    observado_en: haceDias(diasAtras),
    precio_cop: precioCop,
    precio_por_unidad: { valor_cop: precioCop, por: "kg" },
    origen,
    estado,
    es_demo: esDemo,
    presentacion_id: null,
    cantidad_base: 1000,
  };
}

const HISTORIAL_POR_ESTABLECIMIENTO: Readonly<
  Record<string, { readonly nombre: string; readonly puntos: readonly PuntoHistorialMock[] }>
> = {
  [TIENDA_A]: {
    nombre: "Tienda La Esquina",
    puntos: [
      crearPuntoHistorial(
        "a1111111-1111-4111-8111-111111111111",
        80,
        5000,
        "usuario",
        "aceptado",
        false
      ),
      crearPuntoHistorial(
        "a2222222-2222-4222-8222-222222222222",
        45,
        5250,
        "comercio",
        "aceptado",
        false
      ),
      crearPuntoHistorial(
        "a3333333-3333-4333-8333-333333333333",
        20,
        4800,
        "semilla",
        "dudoso",
        true
      ),
      crearPuntoHistorial(
        "a4444444-4444-4444-8444-444444444444",
        3,
        5100,
        "usuario",
        "aceptado",
        false
      ),
    ],
  },
  [TIENDA_B]: {
    nombre: "Supermercado Central",
    puntos: [
      crearPuntoHistorial(
        "b1111111-1111-4111-8111-111111111111",
        70,
        6300,
        "usuario",
        "aceptado",
        false
      ),
      crearPuntoHistorial(
        "b2222222-2222-4222-8222-222222222222",
        30,
        6400,
        "comercio",
        "aceptado",
        false
      ),
      crearPuntoHistorial(
        "b3333333-3333-4333-8333-333333333333",
        7,
        6000,
        "usuario",
        "dudoso",
        false
      ),
      crearPuntoHistorial(
        "b4444444-4444-4444-8444-444444444444",
        40,
        6200,
        "semilla",
        "aceptado",
        true
      ),
    ],
  },
};

/**
 * Construye una respuesta valida del historial para las tiendas del mock.
 * Devuelve `null` cuando el establecimiento no existe, para responder 422.
 */
export function construirRespuestaHistorial(
  establecimientoId: string,
  opciones: OpcionesHistorialMock = {}
): RespuestaHistorialMock | null {
  const establecimiento = HISTORIAL_POR_ESTABLECIMIENTO[establecimientoId];
  if (!establecimiento) {
    return null;
  }

  const puntos = opciones.puntos ?? establecimiento.puntos;
  return {
    datos: {
      producto: {
        id: PROD_ID,
        nombre: "Arroz blanco",
        unidad_base: "g",
        unidad_visualizacion: "kg",
      },
      establecimiento: {
        id: establecimientoId,
        nombre: establecimiento.nombre,
        municipio: "Armenia",
      },
      presentacion: null,
      desde: opciones.desde ?? haceDias(89),
      hasta: opciones.hasta ?? new Date().toISOString(),
      puntos,
      total: puntos.length,
      truncado: opciones.truncado ?? false,
      datos_de_demostracion:
        opciones.datos_de_demostracion ?? puntos.some((punto) => punto.es_demo),
    },
  };
}

function esRutaHistorial(ruta: string): boolean {
  const partes = ruta.split("/");
  return (
    partes.length === 5 &&
    partes[1] === "v1" &&
    partes[2] === "productos" &&
    partes[4] === "historial-precios"
  );
}

async function responderHistorial(route: Route, ruta: string): Promise<boolean> {
  if (!esRutaHistorial(ruta) || route.request().method() !== "GET") {
    return false;
  }

  const productoId = ruta.split("/")[3];
  if (productoId !== PROD_ID) {
    await route.fulfill({
      status: 404,
      json: {
        type: "https://comparador.armenia.gov.co/errores/no-encontrado",
        title: "No encontrado",
        status: 404,
        detail: "Producto no encontrado o inactivo.",
        codigo: "NO_ENCONTRADO",
      },
    });
    return true;
  }

  const establecimientoId =
    new URL(route.request().url()).searchParams.get("establecimiento_id") ?? "";
  const respuesta = construirRespuestaHistorial(establecimientoId);
  if (!respuesta) {
    await route.fulfill({
      status: 422,
      json: {
        type: "https://comparador.armenia.gov.co/errores/validacion",
        title: "Solicitud invalida",
        status: 422,
        detail: "El establecimiento_id es obligatorio y debe existir.",
        codigo: "VALIDACION",
      },
    });
    return true;
  }

  await route.fulfill({ json: respuesta });
  return true;
}

async function responderPublicos(route: Route, ruta: string): Promise<boolean> {
  const mapaPublicos: Record<string, unknown> = {
    "/v1/categorias": [{ id: 1, nombre: "Granos, arroz y pastas", padre_id: null, orden: 1 }],
    "/v1/productos": {
      datos: [{
        id: PROD_ID, nombre: "Arroz blanco", categoria_id: 1, unidad_base: "g",
        unidad_visualizacion: "kg", precio_desde_por_unidad_cop: 5000, n_tiendas_con_precio: 2, imagen_url: null,
      }],
      siguiente_cursor: null, total_estimado: 1,
    },
    [`/v1/productos/${PROD_ID}`]: {
      id: PROD_ID, nombre: "Arroz blanco", categoria_id: 1, unidad_base: "g", unidad_visualizacion: "kg", activo: true,
      presentaciones: [{
        id: PRES_500, producto_id: PROD_ID, marca: "Diana", valor_cantidad: "500",
        unidad: "g", multiplicador: 1, cantidad_base: "500.000", etiqueta: "Arroz Diana 500 g", activa: true,
      }],
    },
    [`/v1/productos/${PROD_ID}/comparacion`]: construirComparacion(),
    "/v1/establecimientos": {
      datos: [{
        id: TIENDA_A, nombre: "Tienda La Esquina", tipo: "tienda_barrio", cadena: null,
        direccion: "Cra 14 # 18-22", barrio: "Centro", municipio: "Armenia", departamento: "Quindío",
        lat: 4.535, lng: -75.675, distancia_m: 420, estado_verificacion: "sin_dueno", activo: true,
      }],
      total: 1,
    },
    "/v1/legal/politica-tratamiento": {
      version: "1.0", contacto_legal_email: "contacto@cue.edu.co",
      finalidades: ["Comparación colaborativa de precios"], derechos_arco: ["Conocer, actualizar y suprimir datos"],
      texto_completo: "Política de tratamiento de datos personales Ley 1581 de 2012.",
    },
  };
  if (ruta in mapaPublicos) {
    await route.fulfill({ json: mapaPublicos[ruta] });
    return true;
  }
  return false;
}

async function responderCuentaYReportes(route: Route, ruta: string, metodo: string, estado: EstadoMock): Promise<boolean> {
  if (ruta === "/v1/mi-cuenta" && metodo === "GET") {
    if (!estado.autorizado) {
      await route.fulfill({ status: 403, json: { codigo: "AUTORIZACION_REQUERIDA", detail: "Requiere Ley 1581", status: 403 } });
      return true;
    }
    await route.fulfill({
      json: {
        usuario_id: "user-e2e-1", alias: "vecino_armenia", email: `${estado.rol}@armenia.co`, rol: estado.rol, estado: "activa",
        reputacion: 0.75, reportes_corroborados: 3, reportes_malos_confirmados: 0,
        autorizacion_vigente: { version_politica: "1.0", aceptada_en: new Date().toISOString() }, creado_en: new Date().toISOString(),
      },
    });
    return true;
  }
  if (ruta === "/v1/mi-cuenta/autorizacion" && metodo === "POST") {
    estado.autorizado = true;
    await route.fulfill({ status: 201, json: { usuario_id: "user-e2e-1", alias: "vecino_armenia", version_politica: "1.0", aceptada_en: new Date().toISOString(), mensaje: "OK" } });
    return true;
  }
  if (ruta === "/v1/reportes" && metodo === "POST") {
    const req = route.request();
    estado.opts.alCrearReporte?.(req.headers(), req.postDataJSON());
    await route.fulfill({ status: 201, json: { datos: { id: "rep-e2e-1", estado_visible: "recibido", mensaje: "Gracias, tu precio quedó registrado." } } });
    return true;
  }
  return false;
}

/** Presentaciones sinteticas para medir el modo rapido con un lote realista. */
export function presentacionesComercioMock(cantidad: number): unknown[] {
  return Array.from({ length: cantidad }, (_, i) => ({
    producto_id: `prod-${i}`,
    producto_nombre: `Producto ${i + 1}`,
    presentacion_id: `pres-${i}`,
    presentacion_etiqueta: `Marca ${i + 1} 500 g`,
    precio_cop: 3000 + i * 50,
    precio_por_base: { valor_cop: 6000 + i * 100, por: "kg" },
    sello: "confiable",
    motivo_sello: "3 reportes de 3 fuentes",
    ultimo_reporte_en: new Date().toISOString(),
  }));
}

async function responderComercio(
  route: Route,
  ruta: string,
  metodo: string,
  estado: EstadoMock
): Promise<boolean> {
  const cantidad = estado.opts.presentacionesComercio ?? 20;

  if (ruta === "/v1/comercio/establecimientos" && metodo === "GET") {
    await route.fulfill({
      json: [{
        id: TIENDA_A, nombre: "Tienda La Esquina", tipo: "tienda_barrio", barrio: "Centro",
        direccion: "Cra 14 # 18-22", estado_verificacion: "verificado",
        n_precios_oficiales: 0, n_por_revalidar: 0,
      }],
    });
    return true;
  }

  if (ruta === `/v1/establecimientos/${TIENDA_A}` && metodo === "GET") {
    await route.fulfill({
      json: {
        id: TIENDA_A, nombre: "Tienda La Esquina", tipo: "tienda_barrio", cadena: null,
        direccion: "Cra 14 # 18-22", barrio: "Centro", municipio: "Armenia", departamento: "Quindío",
        lat: 4.535, lng: -75.675, distancia_m: null, estado_verificacion: "verificado", activo: true,
        precios_vigentes: presentacionesComercioMock(cantidad),
      },
    });
    return true;
  }

  if (ruta === `/v1/comercio/establecimientos/${TIENDA_A}/precios` && metodo === "PUT") {
    const cuerpo = route.request().postDataJSON() as { precios?: unknown[] };
    estado.opts.alPublicarPrecios?.(cuerpo);
    await route.fulfill({
      json: { actualizados: cuerpo.precios?.length ?? 0, rechazados: [] },
    });
    return true;
  }

  if (ruta === `/v1/comercio/establecimientos/${TIENDA_A}/revalidar` && metodo === "POST") {
    await route.fulfill({ json: { revalidados: cantidad, revalidado_en: new Date().toISOString() } });
    return true;
  }

  if (ruta === `/v1/comercio/establecimientos/${TIENDA_A}/promociones` && metodo === "GET") {
    await route.fulfill({ json: [] });
    return true;
  }

  if (ruta === "/v1/moderacion/comercios" && metodo === "GET") {
    await route.fulfill({
      json: {
        datos: [{
          id: "sol-e2e-1", establecimiento_id: TIENDA_A,
          establecimiento_nombre: "Tienda La Esquina", establecimiento_barrio: "Centro",
          establecimiento_direccion: "Cra 14 # 18-22", solicitante_alias: "don_jose",
          telefono_contacto: "3001234567", mensaje: "Soy el dueño, atiendo de 7 a 8.",
          estado: "pendiente", creado_en: new Date().toISOString(),
        }],
        total: 1,
      },
    });
    return true;
  }

  return false;
}

async function responderModeracion(route: Route, ruta: string, metodo: string, estado: EstadoMock): Promise<boolean> {
  if (ruta === "/v1/moderacion/casos" && metodo === "GET") {
    const lista = estado.casoResuelto ? [] : [{
      id: CASO_ID, tipo: "reporte_dudoso", referencia_tabla: "reporte_precio", referencia_id: "rep-99",
      detalle: { senales: ["z_score_alto"] }, prioridad: 2, estado: "abierto", creado_en: new Date().toISOString(),
    }];
    await route.fulfill({ json: { datos: lista, total: lista.length } });
    return true;
  }
  if (ruta === `/v1/moderacion/casos/${CASO_ID}` && metodo === "GET") {
    await route.fulfill({
      json: {
        id: CASO_ID, tipo: "reporte_dudoso", referencia_tabla: "reporte_precio", referencia_id: "rep-99",
        detalle: { senales: ["z_score_alto"] }, prioridad: 2, estado: "abierto", creado_en: new Date().toISOString(),
        referencia_datos: { precio_cop: 15000, producto: "Arroz blanco" },
      },
    });
    return true;
  }
  if (ruta === `/v1/moderacion/casos/${CASO_ID}/resolver` && metodo === "POST") {
    estado.casoResuelto = true;
    estado.opts.alResolverCaso?.(route.request().postDataJSON());
    await route.fulfill({ json: { id: CASO_ID, tipo: "reporte_dudoso", estado: "resuelto", decision: "confirmar", prioridad: 2, creado_en: new Date().toISOString() } });
    return true;
  }
  return false;
}

export async function configurarMocksNucleo(page: Page, opts: OpcionesMock = {}): Promise<void> {
  const estado: EstadoMock = {
    autorizado: opts.autorizadoInicial ?? true,
    casoResuelto: false,
    rol: opts.rol ?? "reportante",
    opts,
  };

  await page.route("**/v1/**", async (route) => {
    const req = route.request();
    const ruta = new URL(req.url()).pathname;
    if (ruta.startsWith("/auth/")) {
      await route.fallback();
      return;
    }
    const metodo = req.method();
    if (await responderHistorial(route, ruta)) return;
    if (await responderComercio(route, ruta, metodo, estado)) return;
    if (await responderPublicos(route, ruta)) return;
    if (await responderCuentaYReportes(route, ruta, metodo, estado)) return;
    if (await responderModeracion(route, ruta, metodo, estado)) return;
    await route.fulfill({ status: 404, json: { detail: `Ruta no mockeada: ${ruta}` } });
  });

  await page.route("**/auth/v1/**", async (route) => {
    if (route.request().url().includes("/token")) {
      await route.fulfill({
        json: {
          access_token: "jwt-e2e-valido", token_type: "bearer", expires_in: 3600,
          expires_at: Math.floor(Date.now() / 1000) + 3600, refresh_token: "ref-e2e",
          user: { id: "user-e2e-1", email: `${estado.rol}@armenia.co`, aud: "authenticated", role: "authenticated" },
        },
      });
      return;
    }
    await route.fulfill({ json: { id: "user-e2e-1", email: `${estado.rol}@armenia.co` } });
  });
}
