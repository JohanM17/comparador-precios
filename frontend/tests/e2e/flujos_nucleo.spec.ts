import { expect, test } from "@playwright/test";
import { PRES_ISABEL, PROD_ATUN, PROD_ID, configurarMocksNucleo } from "./mocks_nucleo";

test.describe("Flujos E2E del Nucleo (T-51)", () => {
  test("Flujo 1: Consumidor busca producto y compara por unidad base en dos bloques con neutralidad", async ({ page }) => {
    await configurarMocksNucleo(page);
    await page.goto("/", { waitUntil: "networkidle" });
    await page.fill("#buscador-vitrina", "arroz");
    await page.getByRole("button", { name: "Buscar" }).click();

    await expect(page.getByRole("link", { name: /Arroz blanco/i })).toBeVisible();
    await page.getByRole("link", { name: /Arroz blanco/i }).click();

    await page.waitForURL(`**/producto/${PROD_ID}`);
    await expect(page.getByRole("heading", { name: "Arroz blanco" })).toBeVisible();
    await expect(page.getByText(/Ordenado por precio por kg\. Las promociones no cambian el orden\./i)).toBeVisible();
    await expect(page.getByRole("region", { name: "Precios vigentes confiables" })).toContainText("Tienda La Esquina");
    await expect(page.getByRole("heading", { name: /Precios desactualizados o en revisión/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Promoción — Contenido comercial que no altera el ranking/i })).toBeVisible();
  });

  test("Flujo catálogo: la búsqueda por marca muestra la presentación coincidente", async ({ page }) => {
    await configurarMocksNucleo(page);
    await page.goto("/", { waitUntil: "networkidle" });
    await page.fill("#buscador-vitrina", "atun isabel");
    await page.getByRole("button", { name: "Buscar" }).click();

    const tarjetaAtun = page
      .getByRole("region", { name: "Catálogo de productos" })
      .getByRole("link", { name: /Atún en lomitos en aceite/i });
    await expect(tarjetaAtun).toBeVisible();
    await expect(tarjetaAtun).toContainText("Lata 160 g Atún Isabel Aceite");

    const coincidencias = page.getByRole("region", { name: "Presentaciones que coinciden" });
    const enlaceIsabel = coincidencias.getByRole("link", {
      name: /Lata 160 g Atún Isabel Aceite/i,
    });
    await expect(enlaceIsabel).toBeVisible();
    await expect(enlaceIsabel).toHaveAttribute(
      "href",
      `/producto/${PROD_ATUN}?presentacion=${PRES_ISABEL}`,
    );
  });

  test("Flujo sugerencia: el modal envía sin recargar y muestra confirmación", async ({ page }) => {
    let cuerpoSugerencia: Record<string, unknown> | undefined;
    await configurarMocksNucleo(page, {
      rol: "reportante",
      autorizadoInicial: true,
      alSugerirPresentacion: (cuerpo) => {
        cuerpoSugerencia = cuerpo as Record<string, unknown>;
      },
    });

    await page.goto("/ingresar", { waitUntil: "networkidle" });
    await page.fill("#auth-correo", "vecino@armenia.co");
    await page.fill("#auth-clave", "ClaveSegura123");
    await page.getByRole("button", { name: "Ingresar" }).click();

    await page.goto("/reportar?medicion=1", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: /Sugerir presentación faltante/i }).click();
    await page.fill("#sug-texto", "Atún Isabel en aceite");
    await page.getByRole("button", { name: "Enviar sugerencia" }).click();

    await expect(
      page.getByText("Sugerencia de presentacion recibida y caso abierto para moderacion.")
    ).toBeVisible();
    await expect(
      page.getByText("Completa tienda, presentación y un precio válido en COP.")
    ).toHaveCount(0);
    expect(page.url()).toContain("/reportar");
    expect(cuerpoSugerencia).toMatchObject({ texto_libre: "Atún Isabel en aceite" });
  });

  test("Flujo 2: Reportante autoriza Ley 1581, encola reporte offline en IndexedDB y sincroniza", async ({ page, context }) => {
    let claveIdempotenciaRecibida: string | undefined;
    await configurarMocksNucleo(page, {
      rol: "reportante",
      autorizadoInicial: false,
      alCrearReporte: (headers) => {
        claveIdempotenciaRecibida = headers["idempotency-key"];
      },
    });

    await page.goto("/ingresar", { waitUntil: "networkidle" });
    await page.fill("#auth-correo", "vecino@armenia.co");
    await page.fill("#auth-clave", "ClaveSegura123");
    await page.getByRole("button", { name: "Ingresar" }).click();

    const checkbox = page.getByRole("checkbox");
    await expect(checkbox).not.toBeChecked();
    await page.fill("#autorizacion-alias", "vecino_armenia");
    await checkbox.check();
    await page.getByRole("button", { name: /Aceptar y activar mi cuenta/i }).click();
    await expect(page.getByText(/Sesión activa como vecino_armenia/i)).toBeVisible();

    await page.goto("/reportar?medicion=1", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: /Tienda La Esquina/i }).click();
    await page.getByRole("button", { name: /Arroz Diana 500 g/i }).click();
    await page.fill("#campo-precio-cop", "2600");

    await context.setOffline(true);
    await page.evaluate(() => window.dispatchEvent(new Event("offline")));
    await page.getByRole("button", { name: "Guardar precio" }).click();
    await expect(page.getByText(/Sin señal: reporte guardado en tu dispositivo/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /1 en cola/i })).toBeVisible();

    const enIndexedDb = await page.evaluate(async () => {
      const req = indexedDB.open("comparador_precios_offline", 1);
      return await new Promise<number>((resolve, reject) => {
        req.onsuccess = () => {
          const tx = req.result.transaction("cola_reportes", "readonly");
          const c = tx.objectStore("cola_reportes").count();
          c.onsuccess = () => resolve(c.result);
        };
        req.onerror = () => reject(req.error);
      });
    });
    expect(enIndexedDb).toBe(1);

    await context.setOffline(false);
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
    await expect(page.getByRole("button", { name: /1 en cola/i })).toHaveCount(0, { timeout: 10_000 });
    expect(claveIdempotenciaRecibida).toMatch(/^[0-9a-f-]{36}$/i);
  });

  test("Flujo 3: Moderador consulta cola y resuelve un caso en /gestion", async ({ page }) => {
    let decisionEnviada: unknown;
    await configurarMocksNucleo(page, {
      rol: "moderador",
      autorizadoInicial: true,
      alResolverCaso: (cuerpo) => {
        decisionEnviada = cuerpo;
      },
    });

    await page.goto("/ingresar", { waitUntil: "networkidle" });
    await page.fill("#auth-correo", "moderador@armenia.co");
    await page.fill("#auth-clave", "ClaveMod123");
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page.getByText(/Sesión activa como/i)).toBeVisible();

    await page.goto("/gestion", { waitUntil: "networkidle" });
    await expect(page.getByRole("tab", { name: "Cola de casos" })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("button", { name: "Revisar" }).click();
    await page.selectOption("#decision-caso", "confirmar");
    await page.fill("#nota-caso", "Precio atipico verificado en tablero");
    await page.getByRole("button", { name: "Guardar resolución" }).click();

    await expect(page.getByText(/Caso .* resuelto \(confirmar\)/i)).toBeVisible();
    expect(decisionEnviada).toEqual({
      decision: "confirmar",
      nota: "Precio atipico verificado en tablero",
      sancion: null,
    });
  });

  test("El botón flotante de captura aparece en la vitrina y se oculta en /gestion", async ({
    page,
  }) => {
    await configurarMocksNucleo(page);

    await page.goto("/", { waitUntil: "networkidle" });
    const boton = page.getByRole("link", { name: "Reportar precio de producto" });
    await expect(boton).toBeVisible();

    await page.goto("/gestion", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("link", { name: "Reportar precio de producto" })
    ).toHaveCount(0);
  });
});
