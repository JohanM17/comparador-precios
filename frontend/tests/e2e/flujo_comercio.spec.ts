import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { TIENDA_A, configurarMocksNucleo } from "./mocks_nucleo";

/** Criterio de T-67: veinte precios en modo rápido en menos de un minuto. */
const PRECIOS_A_CORREGIR = 20;
const LIMITE_SEGUNDOS = 60;

async function ingresar(page: Page, correo: string): Promise<void> {
  await page.goto("/ingresar", { waitUntil: "networkidle" });
  await page.fill("#auth-correo", correo);
  await page.fill("#auth-clave", "ClaveComercio123");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByText(/Sesión activa como/i)).toBeVisible();
}

test.describe("Panel de comercio en S6 (T-67)", () => {
  test("un comercio corrige 20 precios en modo rápido en menos de un minuto", async ({ page }) => {
    let publicado: { precios?: { presentacion_id: string; precio_cop: number }[] } | undefined;
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 24,
      alPublicarPrecios: (cuerpo) => {
        publicado = cuerpo as typeof publicado;
      },
    });

    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    // Un comercio aterriza directo en su tarea, no en una pantalla intermedia.
    await expect(page.getByRole("tab", { name: "Precios" })).toHaveAttribute(
      "aria-selected",
      "true"
    );

    const campos = page.locator('[data-prueba="lista-precios-rapido"] input');
    await expect(campos).toHaveCount(24);

    /*
     * El cronómetro arranca con la lista ya en pantalla: lo que se mide es el
     * trabajo del comercio, no la latencia de la red simulada.
     */
    const inicio = Date.now();

    await campos.nth(0).focus();
    for (let i = 0; i < PRECIOS_A_CORREGIR; i += 1) {
      await page.keyboard.press("Control+a");
      await page.keyboard.type(String(4100 + i * 25));
      // Enter baja al siguiente campo: es lo que evita volver al ratón.
      await page.keyboard.press("Enter");
    }

    const boton = page.locator('[data-prueba="publicar-precios"]');
    await expect(boton).toContainText(`Publicar ${PRECIOS_A_CORREGIR} precios`);
    await boton.click();
    await expect(page.getByText(`${PRECIOS_A_CORREGIR} precios publicados`)).toBeVisible();

    const segundos = (Date.now() - inicio) / 1000;
    expect(
      segundos,
      `Corregir y publicar ${PRECIOS_A_CORREGIR} precios tomó ${segundos.toFixed(1)} s`
    ).toBeLessThan(LIMITE_SEGUNDOS);

    // Solo viaja lo que cambió, no la lista entera.
    expect(publicado?.precios).toHaveLength(PRECIOS_A_CORREGIR);
    expect(publicado?.precios?.[0]?.precio_cop).toBe(4100);
  });

  test("«Todo sigue igual» confirma sin escribir un solo precio", async ({ page }) => {
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 12,
    });

    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    await expect(page.locator('[data-prueba="publicar-precios"]')).toContainText(
      "Sin cambios por publicar"
    );
    await page.getByRole("button", { name: "Todo sigue igual" }).click();
    await expect(page.getByText("12 precios confirmados sin cambios")).toBeVisible();
  });

  test("la pestaña de precios advierte que el valor precargado es de la comunidad", async ({
    page,
  }) => {
    await configurarMocksNucleo(page, { rol: "comercio", autorizadoInicial: true });
    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    const aviso = page.getByText(/Cada campo trae el último precio que reportó la comunidad/);
    await expect(aviso).toBeVisible();
    await expect(aviso).toContainText("no el tuyo");
  });

  test("un reportante ve el reclamo pero no las pestañas de comercio", async ({ page }) => {
    await configurarMocksNucleo(page, { rol: "reportante", autorizadoInicial: true });
    await ingresar(page, "vecino@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    await expect(page.getByRole("tab", { name: "Mi comercio" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Precios" })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Promociones" })).toHaveCount(0);

    await page.getByRole("tab", { name: "Mi comercio" }).click();
    await expect(
      page.getByRole("heading", { name: "Reclamar un establecimiento" })
    ).toBeVisible();
    await expect(page.getByText(/Un moderador lo verifica a mano/)).toBeVisible();
  });

  test("un moderador ve la cola de reclamos con el dato para verificar", async ({ page }) => {
    await configurarMocksNucleo(page, { rol: "moderador", autorizadoInicial: true });
    await ingresar(page, "moderador@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    await page.getByRole("tab", { name: "Reclamos de comercio" }).click();
    await expect(page.getByText("Tienda La Esquina")).toBeVisible();
    await expect(page.getByText("don_jose · 3001234567")).toBeVisible();
    await expect(page.getByRole("button", { name: "Aprobar" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Rechazar" })).toBeVisible();
  });

  test("el panel de comercio no tiene violaciones axe críticas o serias", async ({ page }) => {
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 8,
    });
    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    for (const pestana of ["Precios", "Promociones", "Mi comercio"]) {
      await page.getByRole("tab", { name: pestana, exact: true }).click();
      await expect(page.getByRole("tab", { name: pestana, exact: true })).toHaveAttribute(
        "aria-selected",
        "true"
      );
      const resultados = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      const graves = resultados.violations.filter(
        (v) => v.impact === "critical" || v.impact === "serious"
      );
      expect(graves, `Violaciones en la pestaña ${pestana}: ${JSON.stringify(graves, null, 2)}`).toEqual(
        []
      );
    }
  });
});

test("el identificador de la tienda de prueba no cambió", () => {
  expect(TIENDA_A).toBe("11111111-2222-3333-4444-555555555555");
});
