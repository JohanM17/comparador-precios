import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

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

const PANTALLAS: readonly { readonly nombre: string; readonly ruta: string }[] = [
  { nombre: "S1 Inicio", ruta: "/" },
  { nombre: "S2 Comparador", ruta: `/producto/${PROD_ID}` },
  { nombre: "S3 Tienda", ruta: `/tienda/${TIENDA_ID}` },
  { nombre: "S4 Reportar", ruta: "/reportar?medicion=1" },
  { nombre: "S5 Ingresar", ruta: "/ingresar" },
  { nombre: "S6 Gestion", ruta: "/gestion" },
  { nombre: "S7 Legal", ruta: "/legal" },
  { nombre: "Offline", ruta: "/offline" },
];

test.describe("PWA y Accesibilidad WCAG 2.2 AA", () => {
  test("El manifiesto PWA existe y cumple configuracion standalone", async ({ request }) => {
    const resp = await request.get("/manifest.webmanifest");
    expect(resp.status()).toBe(200);
    const json = (await resp.json()) as Record<string, unknown>;
    expect(json.display).toBe("standalone");
    expect(json.start_url).toBe("/");
    expect(Array.isArray(json.icons)).toBe(true);
  });

  for (const pantalla of PANTALLAS) {
    test(`${pantalla.nombre} (${pantalla.ruta}) tiene 0 violaciones criticas o serias WCAG 2.2 AA`, async ({
      page,
    }) => {
      await mockApiBasica(page);
      await page.goto(pantalla.ruta, { waitUntil: "networkidle" });
      await page.waitForSelector("main h1", { timeout: 10_000 });

      const resultados = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();

      const graves = resultados.violations.filter(
        (v) => v.impact === "critical" || v.impact === "serious"
      );

      expect(
        graves,
        `Violaciones graves en ${pantalla.ruta}: ${JSON.stringify(graves, null, 2)}`
      ).toEqual([]);
    });
  }

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

