import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import {
  PRES_500,
  TIENDA_A,
  configurarMocksNucleo,
  construirRespuestaHistorial,
} from "./mocks_nucleo";

const PROD_ID = "3b241101-e2bb-4255-8caf-4136c566a962";
const PRES_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7";
const TIENDA_ID = "11111111-2222-3333-4444-555555555555";

async function mockApiBasica(page: Page): Promise<void> {
  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const ruta = url.pathname;

    if (ruta === "/v1/categorias") {
      await route.fulfill({
        json: [{ id: 1, nombre: "Granos, arroz y pastas", padre_id: null, orden: 1 }],
      });
      return;
    }

    if (ruta === "/v1/productos") {
      await route.fulfill({
        json: {
          datos: [
            {
              id: PROD_ID,
              nombre: "Arroz blanco",
              categoria_id: 1,
              unidad_base: "g",
              unidad_visualizacion: "kg",
              precio_desde_por_unidad_cop: 5200,
              n_tiendas_con_precio: 2,
              imagen_url: null,
            },
          ],
          siguiente_cursor: null,
          total_estimado: 1,
        },
      });
      return;
    }

    if (ruta === `/v1/productos/${PROD_ID}`) {
      await route.fulfill({
        json: {
          id: PROD_ID,
          nombre: "Arroz blanco",
          categoria_id: 1,
          unidad_base: "g",
          unidad_visualizacion: "kg",
          activo: true,
          presentaciones: [
            {
              id: PRES_ID,
              producto_id: PROD_ID,
              marca: "Diana",
              valor_cantidad: "500",
              unidad: "g",
              multiplicador: 1,
              cantidad_base: "500.000",
              etiqueta: "Arroz Diana 500 g",
              activa: true,
            },
          ],
        },
      });
      return;
    }

    if (ruta === `/v1/productos/${PROD_ID}/comparacion`) {
      await route.fulfill({
        json: {
          datos: {
            producto: {
              id: PROD_ID,
              nombre: "Arroz blanco",
              categoria_id: 1,
              unidad_base: "g",
              unidad_visualizacion: "kg",
              presentaciones: [
                { id: PRES_ID, etiqueta: "Arroz Diana 500 g", marca: "Diana", cantidad_base: 500 },
              ],
            },
            resultados: [
              {
                establecimiento: {
                  id: TIENDA_ID,
                  nombre: "Tienda La Esquina",
                  tipo: "tienda_barrio",
                  barrio: "Centro",
                  direccion: "Cra 14 # 18-22",
                  distancia_m: 420,
                },
                presentacion: {
                  id: PRES_ID,
                  etiqueta: "Arroz Diana 500 g",
                  marca: "Diana",
                  cantidad_base: 500,
                },
                precio_cop: 2600,
                precio_oficial_cop: null,
                precio_por_unidad: { valor_cop: 5200, por: "kg" },
                sello: "confiable",
                motivo_sello: null,
                n_reportes_validos: 4,
                n_fuentes: 3,
                ultimo_reporte_en: new Date().toISOString(),
                con_foto_prueba: true,
                es_bloque_secundario: false,
              },
            ],
            promociones: [],
            meta: {
              criterio_orden: "precio_unitario",
              texto_neutralidad: "Ordenado por precio por kg. Las promociones no cambian el orden.",
              bloques: ["vigentes", "dudosos_y_desactualizados"],
              generado_en: new Date().toISOString(),
              datos_de_demostracion: false,
            },
          },
        },
      });
      return;
    }

    if (ruta === `/v1/productos/${PROD_ID}/historial-precios`) {
      const establecimientoId = url.searchParams.get("establecimiento_id") ?? TIENDA_ID;
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
        return;
      }
      await route.fulfill({ json: respuesta });
      return;
    }

    if (ruta === "/v1/establecimientos") {
      await route.fulfill({
        json: {
          datos: [
            {
              id: TIENDA_ID,
              nombre: "Tienda La Esquina",
              tipo: "tienda_barrio",
              cadena: null,
              direccion: "Cra 14 # 18-22",
              barrio: "Centro",
              municipio: "Armenia",
              departamento: "Quindío",
              lat: 4.535,
              lng: -75.675,
              distancia_m: 420,
              estado_verificacion: "sin_dueno",
              activo: true,
            },
          ],
          total: 1,
        },
      });
      return;
    }

    if (ruta === `/v1/establecimientos/${TIENDA_ID}`) {
      await route.fulfill({
        json: {
          id: TIENDA_ID,
          nombre: "Tienda La Esquina",
          tipo: "tienda_barrio",
          cadena: null,
          direccion: "Cra 14 # 18-22",
          barrio: "Centro",
          municipio: "Armenia",
          departamento: "Quindío",
          lat: 4.535,
          lng: -75.675,
          distancia_m: 420,
          estado_verificacion: "sin_dueno",
          activo: true,
          precios_vigentes: [],
        },
      });
      return;
    }

    if (ruta === "/v1/legal/politica-tratamiento") {
      await route.fulfill({
        json: {
          version: "1.0",
          contacto_legal_email: "por-confirmar-equipo@cue.edu.co",
          finalidades: ["Comparación colaborativa de precios"],
          derechos_arco: ["Conocer, actualizar y suprimir datos personales"],
          texto_completo: "Política de tratamiento de datos conforme a la Ley 1581 de 2012.",
        },
      });
      return;
    }

    await route.fulfill({ status: 404, json: { detail: "No encontrado en mock" } });
  });
}

async function iniciarSesion(page: Page, correo: string): Promise<void> {
  await page.goto("/ingresar", { waitUntil: "networkidle" });
  await page.fill("#auth-correo", correo);
  await page.fill("#auth-clave", "ClaveAccesibilidad123");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByText(/Sesión activa como/i)).toBeVisible();
}

/** Deja un reporte pendiente en la misma base IndexedDB que usa la cola offline. */
async function sembrarColaOffline(page: Page): Promise<void> {
  await page.evaluate(
    async ({ presentacionId, tiendaId }) => {
      const solicitud = indexedDB.open("comparador_precios_offline", 1);
      const db = await new Promise<IDBDatabase>((resolver, rechazar) => {
        solicitud.onupgradeneeded = () => {
          const base = solicitud.result;
          if (!base.objectStoreNames.contains("cola_reportes")) {
            base.createObjectStore("cola_reportes", { keyPath: "idempotency_key" });
          }
        };
        solicitud.onsuccess = () => resolver(solicitud.result);
        solicitud.onerror = () => rechazar(solicitud.error);
      });
      await new Promise<void>((resolver, rechazar) => {
        const tx = db.transaction("cola_reportes", "readwrite");
        tx.objectStore("cola_reportes").put({
          idempotency_key: "cola-accesibilidad-1",
          presentacion_id: presentacionId,
          presentacion_etiqueta: "Arroz Diana 500 g",
          establecimiento_id: tiendaId,
          establecimiento_nombre: "Tienda La Esquina",
          precio_cop: 2600,
          observado_en: new Date().toISOString(),
          foto_blob: null,
          foto_ruta_remota: null,
          intentos: 0,
          ultimo_error: null,
          proximo_intento_en: null,
          creado_localmente_en: new Date().toISOString(),
        });
        tx.oncomplete = () => resolver();
        tx.onerror = () => rechazar(tx.error);
        tx.onabort = () => rechazar(tx.error);
      });
      db.close();
    },
    { presentacionId: PRES_500, tiendaId: TIENDA_A }
  );
}

async function analizarAxe(page: Page, contexto: string): Promise<void> {
  const resultados = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const graves = resultados.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious"
  );
  expect(
    graves,
    `Violaciones graves en ${contexto}: ${JSON.stringify(graves, null, 2)}`
  ).toEqual([]);
}

const PANTALLAS: readonly { readonly nombre: string; readonly ruta: string }[] = [
  { nombre: "S1 Inicio", ruta: "/" },
  { nombre: "S2 Comparador", ruta: `/producto/${PROD_ID}` },
  { nombre: "S3 Tienda", ruta: `/tienda/${TIENDA_ID}` },
  { nombre: "S4 Reportar", ruta: "/reportar?medicion=1" },
  { nombre: "S5 Ingresar", ruta: "/ingresar" },
  { nombre: "S7 Legal", ruta: "/legal" },
  { nombre: "Offline", ruta: "/offline" },
];

test.describe("PWA y Accesibilidad WCAG 2.2 AA", () => {
  /*
   * Las pantallas con varias corridas de axe (S6) rozan el limite por defecto
   * de 30 s cuando el runner esta cargado. 90 s mantiene 4 workers y evita
   * timeouts intermitentes en CI.
   */
  test.describe.configure({ timeout: 90_000 });

  test("El manifiesto PWA existe y cumple configuracion standalone", async ({ request }) => {
    const resp = await request.get("/manifest.webmanifest");
    expect(resp.status()).toBe(200);
    const json = (await resp.json()) as Record<string, unknown>;
    expect(json.display).toBe("standalone");
    expect(json.start_url).toBe("/");
    expect(Array.isArray(json.icons)).toBe(true);
  });

  /*
   * La aplicacion ofrece modo claro y oscuro, asi que el contraste se verifica en
   * los dos. El tema se fija en localStorage antes de cargar la pagina: el script
   * del <head> lo lee y aplica la clase `dark` antes del primer pintado.
   */
  const TEMAS = ["claro", "oscuro"] as const;

  for (const tema of TEMAS) {
    for (const pantalla of PANTALLAS) {
      test(`${pantalla.nombre} (${pantalla.ruta}) en modo ${tema} tiene 0 violaciones criticas o serias WCAG 2.2 AA`, async ({
        page,
      }) => {
        await page.addInitScript((valor) => {
          try {
            window.localStorage.setItem("tema", valor);
          } catch {
            // Sin almacenamiento disponible la pagina cae al tema del sistema.
          }
        }, tema);
        await mockApiBasica(page);
        await page.goto(pantalla.ruta, { waitUntil: "networkidle" });
        await page.waitForSelector("main h1", { timeout: 10_000 });

        const esOscuro = await page.evaluate(() =>
          document.documentElement.classList.contains("dark")
        );
        expect(esOscuro, `El tema ${tema} no quedo aplicado en ${pantalla.ruta}`).toBe(
          tema === "oscuro"
        );

        const resultados = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
          .analyze();

        const graves = resultados.violations.filter(
          (v) => v.impact === "critical" || v.impact === "serious"
        );

        expect(
          graves,
          `Violaciones graves en ${pantalla.ruta} (modo ${tema}): ${JSON.stringify(graves, null, 2)}`
        ).toEqual([]);
      });
    }
  }

  /*
   * /gestion solo muestra las pestanas reales con una sesion valida. El moderador
   * tiene acceso a la cola de casos, a sus reportes y a los reclamos de comercio;
   * la cola offline pendiente se siembra en IndexedDB antes de entrar al panel.
   */
  for (const tema of TEMAS) {
    test(`S6 Gestion con sesion y cola offline en modo ${tema} tiene 0 violaciones criticas o serias`, async ({
      page,
    }) => {
      await page.addInitScript((valor) => {
        try {
          window.localStorage.setItem("tema", valor);
        } catch {
          // Sin almacenamiento disponible la pagina cae al tema del sistema.
        }
      }, tema);
      await configurarMocksNucleo(page, { rol: "moderador", autorizadoInicial: true });
      await iniciarSesion(page, "moderador@armenia.co");
      await sembrarColaOffline(page);

      await page.goto("/gestion", { waitUntil: "networkidle" });
      await expect(page.getByRole("tab", { name: "Cola de casos" })).toHaveAttribute(
        "aria-selected",
        "true"
      );
      await expect(page.getByRole("button", { name: "Revisar" })).toBeVisible();
      await analizarAxe(page, `/gestion · Cola de casos (modo ${tema})`);

      await page.getByRole("tab", { name: "Mis reportes" }).click();
      const colaPendiente = page.getByRole("region", {
        name: "Reportes pendientes en cola offline",
      });
      await expect(colaPendiente).toBeVisible();
      await expect(colaPendiente).toContainText("Sincronizar ahora");
      await expect(page.getByRole("table")).toContainText("Arroz blanco");
      await analizarAxe(page, `/gestion · Mis reportes con cola offline (modo ${tema})`);

      await page.getByRole("tab", { name: "Reclamos de comercio" }).click();
      await expect(
        page.getByRole("heading", { name: "Reclamos de titularidad" })
      ).toBeVisible();
      await expect(page.getByText("don_jose")).toBeVisible();
      await analizarAxe(page, `/gestion · Reclamos de comercio (modo ${tema})`);
    });
  }

  test("ToggleTema expone aria-pressed y etiqueta dinamica en ambos sentidos", async ({
    page,
  }) => {
    await mockApiBasica(page);
    await page.goto("/", { waitUntil: "networkidle" });

    const aOscuro = page.getByRole("button", { name: "Cambiar a modo oscuro" });
    await expect(aOscuro).toHaveAttribute("aria-pressed", "false");
    await aOscuro.click();

    const aClaro = page.getByRole("button", { name: "Cambiar a modo claro" });
    await expect(aClaro).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("html")).toHaveClass(/dark/);

    await aClaro.click();
    await expect(page.getByRole("button", { name: "Cambiar a modo oscuro" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });

  test("Los selects nativos mantienen contraste en tema oscuro", async ({ page }) => {
    await configurarMocksNucleo(page);
    await page.goto(`/producto/${PROD_ID}`, { waitUntil: "networkidle" });
    await page.waitForSelector("#filtro-presentacion");
    await page.getByRole("button", { name: "Cambiar a modo oscuro" }).click();
    await expect(page.locator("html")).toHaveClass(/dark/);

    const colores = await page
      .locator("#filtro-presentacion option")
      .first()
      .evaluate((option) => {
        const estilo = getComputedStyle(option);
        return { color: estilo.color, backgroundColor: estilo.backgroundColor };
      });

    const aRgb = (valor: string): [number, number, number] => {
      const partes = (valor.match(/\d+/g) ?? ["0", "0", "0"]).map(Number);
      return [partes[0] ?? 0, partes[1] ?? 0, partes[2] ?? 0];
    };
    const luminancia = ([r, g, b]: [number, number, number]): number => {
      const canal = (v: number): number => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
    };
    const l1 = luminancia(aRgb(colores.color));
    const l2 = luminancia(aRgb(colores.backgroundColor));
    const contraste = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    expect(contraste).toBeGreaterThanOrEqual(4.5);
  });

  test("Navegacion por teclado en S4 (/reportar) alcanza controles y cronometro EC-01", async ({
    page,
  }) => {
    await mockApiBasica(page);
    await page.goto("/reportar?medicion=1", { waitUntil: "networkidle" });
    await expect(page.getByTestId("cronometro-ec01")).toBeVisible();

    await page.keyboard.press("Tab");
    const elementoActivo = await page.evaluate(() => document.activeElement?.tagName ?? "");
    expect(["A", "INPUT", "BUTTON", "SELECT"]).toContain(elementoActivo);

    const campoPrecio = page.locator("#campo-precio-cop");
    await campoPrecio.focus();
    await campoPrecio.fill("2600");
    await expect(campoPrecio).toHaveValue("2.600");
  });
});

