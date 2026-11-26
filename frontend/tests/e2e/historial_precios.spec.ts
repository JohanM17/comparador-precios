import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import {
  PROD_ID,
  TIENDA_A,
  TIENDA_B,
  configurarMocksNucleo,
  construirRespuestaHistorial,
} from "./mocks_nucleo";

const RUTA_HISTORIAL = /\/v1\/productos\/[^/]+\/historial-precios(?:\?.*)?$/;

function seccionHistorial(page: Page) {
  return page.getByRole("region", { name: "Historial de precios", exact: true });
}

function seccionGrafica(page: Page) {
  return page.getByRole("region", { name: "Historial de precios: Arroz blanco", exact: true });
}

async function irAFicha(page: Page): Promise<void> {
  await page.goto(`/producto/${PROD_ID}`, { waitUntil: "networkidle" });
  await expect(seccionHistorial(page)).toBeVisible();
  await expect(page.locator("#selector-establecimiento-historial")).toHaveValue(TIENDA_A);
}

async function interceptarHistorial(
  page: Page,
  responder: (establecimientoId: string) => unknown
): Promise<void> {
  await page.route(RUTA_HISTORIAL, async (route) => {
    const establecimientoId =
      new URL(route.request().url()).searchParams.get("establecimiento_id") ?? "";
    await route.fulfill({ json: responder(establecimientoId) });
  });
}

test.describe("Historial de precios (A2, EC-08)", () => {
  test("muestra la serie con origen, estado, demo y aviso de demostración", async ({ page }) => {
    const peticiones: string[] = [];
    page.on("request", (request) => {
      if (RUTA_HISTORIAL.test(request.url())) {
        peticiones.push(request.url());
      }
    });

    await configurarMocksNucleo(page);
    await irAFicha(page);

    const grafica = seccionGrafica(page);
    await expect(grafica).toBeVisible();
    await expect(
      grafica.getByRole("img", { name: /Historial de precios de Arroz blanco/ })
    ).toBeVisible();

    const tabla = grafica.getByRole("table");
    await expect(tabla).toBeVisible();
    await expect(tabla).toContainText("Reportado");
    await expect(tabla).toContainText("Oficial");
    await expect(tabla).toContainText("Semilla/demostración");
    await expect(tabla).toContainText("Aceptado");
    await expect(tabla).toContainText("En revisión");
    await expect(tabla).toContainText("$5.000");

    const filaSemilla = tabla.getByRole("row", { name: /Semilla\/demostración/ });
    await expect(filaSemilla).toContainText("En revisión");
    await expect(filaSemilla).toContainText("Sí");

    const filaOficial = tabla.getByRole("row", { name: /Oficial/ });
    await expect(filaOficial).toContainText("Aceptado");
    await expect(filaOficial).toContainText("No");

    await expect(
      page.getByRole("region", { name: "Aviso de datos de demostración" })
    ).toBeVisible();
    expect(
      peticiones.some((url) => url.includes(`establecimiento_id=${TIENDA_A}`)),
      "La ficha debe consultar el historial de la primera tienda"
    ).toBe(true);
  });

  test("cambia la serie y consulta la tienda elegida", async ({ page }) => {
    await configurarMocksNucleo(page);
    await irAFicha(page);

    const grafica = seccionGrafica(page);
    await expect(grafica.getByRole("table")).toContainText("$5.000");

    const peticionTiendaB = page.waitForRequest((request) => {
      if (!RUTA_HISTORIAL.test(request.url())) {
        return false;
      }
      return new URL(request.url()).searchParams.get("establecimiento_id") === TIENDA_B;
    });

    await page.selectOption("#selector-establecimiento-historial", TIENDA_B);
    await peticionTiendaB;

    const tabla = grafica.getByRole("table");
    await expect(tabla).toContainText("$6.300");
    await expect(tabla).not.toContainText("$5.000");
    await expect(
      grafica.getByRole("img", {
        name: /Historial de precios de Arroz blanco en Supermercado Central/,
      })
    ).toBeVisible();
    await expect(grafica.getByText("Supermercado Central · Armenia")).toBeVisible();
  });

  test("muestra el estado vacío cuando la serie no tiene puntos", async ({ page }) => {
    await configurarMocksNucleo(page);
    await interceptarHistorial(page, (establecimientoId) =>
      construirRespuestaHistorial(establecimientoId, { puntos: [] })
    );
    await irAFicha(page);

    await expect(
      page.getByRole("heading", { name: "Sin historial de precios", exact: true })
    ).toBeVisible();
    await expect(page.getByRole("img", { name: /Historial de precios de/ })).toHaveCount(0);
    await expect(page.getByRole("table")).toHaveCount(0);
  });

  test("muestra el error y recupera la serie al reintentar", async ({ page }) => {
    await configurarMocksNucleo(page);
    let intentos = 0;
    await page.route(RUTA_HISTORIAL, async (route) => {
      intentos += 1;
      if (intentos === 1) {
        await route.fulfill({
          status: 500,
          json: {
            type: "https://comparador.armenia.gov.co/errores/error-interno",
            title: "Error interno",
            status: 500,
            detail: "Historial no disponible temporalmente.",
            codigo: "ERROR_INTERNO",
          },
        });
        return;
      }
      await route.fallback();
    });

    await irAFicha(page);

    const alerta = seccionHistorial(page).getByRole("alert");
    await expect(alerta).toContainText("Historial no disponible temporalmente.");
    const botonReintentar = alerta.getByRole("button", { name: "Reintentar" });
    await expect(botonReintentar).toBeVisible();

    await botonReintentar.click();

    const grafica = seccionGrafica(page);
    await expect(grafica.getByRole("table")).toBeVisible();
    await expect(
      grafica.getByRole("img", { name: /Historial de precios de Arroz blanco/ })
    ).toBeVisible();
    expect(intentos).toBe(2);
  });

  test("avisa cuando la serie está truncada", async ({ page }) => {
    await configurarMocksNucleo(page);
    await interceptarHistorial(page, (establecimientoId) =>
      construirRespuestaHistorial(establecimientoId, { truncado: true })
    );
    await irAFicha(page);

    const grafica = seccionGrafica(page);
    await expect(grafica.getByRole("note")).toContainText(
      "Se muestran los puntos más recientes"
    );
    await expect(grafica.getByRole("table")).toBeVisible();
  });

  test("la ficha con historial no tiene violaciones axe críticas o serias", async ({ page }) => {
    await configurarMocksNucleo(page);
    await irAFicha(page);
    await expect(seccionGrafica(page).getByRole("table")).toBeVisible();

    const resultados = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();

    const graves = resultados.violations.filter(
      (violacion) => violacion.impact === "critical" || violacion.impact === "serious"
    );

    expect(
      graves,
      `Violaciones graves en la ficha con historial: ${JSON.stringify(graves, null, 2)}`
    ).toEqual([]);
  });
});
