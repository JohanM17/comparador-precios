import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { PROD_ID, TIENDA_A, configurarMocksNucleo } from "./mocks_nucleo";

/** Criterio de T-67: veinte precios en modo rápido en menos de un minuto. */
const PRECIOS_A_CORREGIR = 20;
const LIMITE_SEGUNDOS = 60;
const TEMAS = ["claro", "oscuro"] as const;

async function ingresar(page: Page, correo: string): Promise<void> {
  await page.goto("/ingresar", { waitUntil: "networkidle" });
  await page.fill("#auth-correo", correo);
  await page.fill("#auth-clave", "ClaveComercio123");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByText(/Sesión activa como/i)).toBeVisible();
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

test.describe("Panel de comercio en S6 (T-67)", () => {
  test("un comercio corrige 20 precios en modo rápido en menos de un minuto", async ({ page }) => {
    let publicado: { precios?: { presentacion_id: string; precio_cop: number }[] } | undefined;
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 24,
      preciosOficialesComercio: 24,
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
      await page.keyboard.type(String(4000 + i * 100));
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
    expect(publicado?.precios?.[0]?.precio_cop).toBe(4000);
  });

  test("«Todo sigue igual» confirma sin escribir un solo precio", async ({ page }) => {
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 12,
      preciosOficialesComercio: 12,
    });

    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    await expect(page.locator('[data-prueba="publicar-precios"]')).toContainText(
      "Sin cambios por publicar"
    );
    await page.getByRole("button", { name: "Todo sigue igual" }).click();
    await expect(page.getByText("12 precios confirmados sin cambios")).toBeVisible();
  });

  test("el modo rápido precarga el precio oficial y avisa cuando solo hay comunidad", async ({
    page,
  }) => {
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 2,
      preciosOficialesComercio: 1,
      selloPreciosOficiales: "en_disputa",
    });
    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    const campos = page.locator('[data-prueba="lista-precios-rapido"] input');
    await expect(campos).toHaveCount(2);

    // En disputa el precio vigente es la comunidad (3000), pero el campo debe
    // precargar el oficial (3700) y rotular la discrepancia.
    await expect(campos.nth(0)).toHaveValue("3700");
    await expect(
      page.locator('[data-prueba="lista-precios-rapido"]').getByText(/oficial en disputa/)
    ).toBeVisible();
    await expect(
      page.locator('[data-prueba="lista-precios-rapido"]').getByText(/comunidad \$3\.000/)
    ).toBeVisible();

    // La fila sin precio oficial muestra el comunitario y lo advierte.
    await expect(campos.nth(1)).toHaveValue("3050");
    await expect(
      page.locator('[data-prueba="lista-precios-rapido"]').getByText(/precio de la comunidad, no el tuyo/)
    ).toBeVisible();

    const aviso = page.getByText(/Cada campo trae tu precio oficial cuando ya lo publicaste/);
    await expect(aviso).toBeVisible();
  });

  test("una tienda sin precios oficiales publica todas las filas y no llama a revalidar", async ({
    page,
  }) => {
    let publicado: { precios?: { presentacion_id: string; precio_cop: number }[] } | undefined;
    let revalidaciones = 0;
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 5,
      preciosOficialesComercio: 0,
      alPublicarPrecios: (cuerpo) => {
        publicado = cuerpo as typeof publicado;
      },
      alRevalidarPrecios: () => {
        revalidaciones += 1;
      },
    });
    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    const boton = page.locator('[data-prueba="publicar-precios"]');
    await expect(boton).toContainText("Publicar precios comunitarios");
    await expect(page.getByRole("button", { name: "Todo sigue igual" })).toHaveCount(0);
    await expect(page.getByText(/Esta tienda aún no tiene precios oficiales/)).toBeVisible();

    // Antes de publicar, «Mi comercio» tambien refleja cero oficiales.
    await page.getByRole("tab", { name: "Mi comercio" }).click();
    await expect(page.getByText(/0 precios oficiales/)).toBeVisible();
    await expect(page.getByText(/Publícalos en la pestaña «Precios»/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Todo sigue igual" })).toHaveCount(0);

    await page.getByRole("tab", { name: "Precios", exact: true }).click();
    await expect(page.locator('[data-prueba="lista-precios-rapido"] input')).toHaveCount(5);
    await boton.click();
    await expect(page.getByText("5 precios publicados. Ninguno quedó fuera.")).toBeVisible();

    expect(publicado?.precios).toHaveLength(5);
    expect(publicado?.precios?.[0]?.precio_cop).toBe(3000);
    expect(revalidaciones).toBe(0);

    // El mock ahora es stateful: el aviso inicial desaparece y ya hay oficiales
    // que se pueden revalidar sin recibir un 409.
    await expect(page.getByText(/Esta tienda aún no tiene precios oficiales/)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Todo sigue igual" })).toBeVisible();
    await expect(boton).toContainText("Sin cambios por publicar");

    await page.getByRole("tab", { name: "Mi comercio" }).click();
    await expect(page.getByText(/5 precios oficiales/)).toBeVisible();
    await expect(page.getByText(/Publícalos en la pestaña «Precios»/)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Todo sigue igual" })).toBeVisible();
  });

  test("si la primera publicación se rechaza entera, no aparece «Todo sigue igual»", async ({
    page,
  }) => {
    let publicaciones = 0;
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 3,
      preciosOficialesComercio: 0,
      rechazarPrecios: {
        "pres-0": "La presentacion no existe o esta inactiva.",
        "pres-1": "La presentacion no existe o esta inactiva.",
        "pres-2": "La presentacion no existe o esta inactiva.",
      },
      alPublicarPrecios: () => {
        publicaciones += 1;
      },
    });
    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    const boton = page.locator('[data-prueba="publicar-precios"]');
    await expect(boton).toContainText("Publicar precios comunitarios");
    await expect(page.getByRole("button", { name: "Todo sigue igual" })).toHaveCount(0);

    await boton.click();
    await expect(page.getByText("0 publicados, 3 no entraron.")).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: "3 no entraron" })).toBeVisible();

    // Sin oficiales reales no se ofrece revalidar, y el boton sigue disponible
    // para reintentar la publicacion completa.
    await expect(page.getByRole("button", { name: "Todo sigue igual" })).toHaveCount(0);
    await expect(boton).toBeEnabled();
    await expect(boton).toContainText("Publicar precios comunitarios");
    expect(publicaciones).toBe(1);

    await boton.click();
    expect(publicaciones).toBe(2);
  });

  test("una fila sin precio se informa y no se publica como si todo hubiera entrado", async ({
    page,
  }) => {
    let publicado: { precios?: { presentacion_id: string }[] } | undefined;
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 2,
      preciosOficialesComercio: 2,
      alPublicarPrecios: (cuerpo) => {
        publicado = cuerpo as typeof publicado;
      },
    });
    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    const campos = page.locator('[data-prueba="lista-precios-rapido"] input');
    await campos.nth(1).fill("");
    await campos.nth(0).focus();
    await page.keyboard.press("Control+a");
    await page.keyboard.type("4100");

    await expect(page.locator('[data-prueba="filas-sin-precio"]')).toContainText(
      "1 fila quedó sin precio"
    );
    const boton = page.locator('[data-prueba="publicar-precios"]');
    await expect(boton).toContainText("Publicar 1 precio");
    await boton.click();

    await expect(
      page.getByText("1 precio publicado. 1 fila quedó sin precio y no se envió.")
    ).toBeVisible();
    await expect(page.getByText(/Ninguno quedó fuera/)).toHaveCount(0);
    expect(publicado?.precios).toHaveLength(1);
    expect(publicado?.precios?.[0]?.presentacion_id).toBe("pres-0");
  });

  test("un rechazo conserva el valor tecleado y el motivo visible", async ({ page }) => {
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      presentacionesComercio: 2,
      preciosOficialesComercio: 2,
      rechazarPrecios: {
        "pres-1": "La presentacion no existe o esta inactiva.",
      },
    });
    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    const campos = page.locator('[data-prueba="lista-precios-rapido"] input');
    await campos.nth(0).focus();
    await page.keyboard.press("Control+a");
    await page.keyboard.type("4100");
    await campos.nth(1).focus();
    await page.keyboard.press("Control+a");
    await page.keyboard.type("4200");

    const boton = page.locator('[data-prueba="publicar-precios"]');
    await expect(boton).toContainText("Publicar 2 precios");
    await boton.click();

    await expect(page.getByText("1 publicados, 1 no entraron.")).toBeVisible();
    const alerta = page.getByRole("alert").filter({ hasText: "1 no entró" });
    await expect(alerta).toBeVisible();
    await expect(alerta).toContainText("1 no entró");
    await expect(alerta).toContainText("La presentacion no existe o esta inactiva.");

    // La recarga posterior a publicar no borra lo que el comercio ya habia escrito.
    await expect(campos.nth(1)).toHaveValue("4200");
    await expect(alerta).toBeVisible();
  });

  test("revocar una promoción acepta la respuesta 204 sin cuerpo", async ({ page }) => {
    let revocaciones = 0;
    await configurarMocksNucleo(page, {
      rol: "comercio",
      autorizadoInicial: true,
      promocionesComercio: true,
      alRevocarPromocion: () => {
        revocaciones += 1;
      },
    });
    await ingresar(page, "comercio@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    await page.getByRole("tab", { name: "Promociones", exact: true }).click();
    await expect(page.getByText("Pague 2 lleve 3 en arroz")).toBeVisible();
    await page.getByRole("button", { name: "Revocar" }).click();

    await expect(page.getByText(/Promoción revocada/)).toBeVisible();
    await expect(page.getByText("Pague 2 lleve 3 en arroz")).toHaveCount(0);
    expect(revocaciones).toBe(1);
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

  for (const tema of TEMAS) {
    test(`el panel de comercio en modo ${tema} no tiene violaciones axe críticas o serias`, async ({
      page,
    }) => {
      await page.addInitScript((valor) => {
        try {
          window.localStorage.setItem("tema", valor);
        } catch {
          // Sin almacenamiento disponible la pagina cae al tema del sistema.
        }
      }, tema);
      await configurarMocksNucleo(page, {
        rol: "comercio",
        autorizadoInicial: true,
        presentacionesComercio: 8,
        preciosOficialesComercio: 8,
      });
      await ingresar(page, "comercio@armenia.co");
      await page.goto("/gestion", { waitUntil: "networkidle" });

      const esOscuro = await page.evaluate(() =>
        document.documentElement.classList.contains("dark")
      );
      expect(esOscuro, `El tema ${tema} no quedo aplicado`).toBe(tema === "oscuro");

      const contenido: readonly { readonly pestana: string; readonly espera: RegExp }[] = [
        { pestana: "Precios", espera: /Modo rápido/ },
        { pestana: "Promociones", espera: /Publicar una promoción/ },
        { pestana: "Mi comercio", espera: /Mis establecimientos/ },
      ];
      for (const { pestana, espera } of contenido) {
        await page.getByRole("tab", { name: pestana, exact: true }).click();
        await expect(page.getByRole("tab", { name: pestana, exact: true })).toHaveAttribute(
          "aria-selected",
          "true"
        );
        // Se espera el contenido propio de la pestaña antes de analizar: axe no
        // debe escanear el panel vacio del cambio de pestaña.
        await expect(page.getByText(espera).first()).toBeVisible();
        await analizarAxe(page, `pestaña ${pestana} (modo ${tema})`);
      }
    });
  }

  test("la pestaña de reclamos de comercio no tiene violaciones axe como moderador", async ({
    page,
  }) => {
    await configurarMocksNucleo(page, { rol: "moderador", autorizadoInicial: true });
    await ingresar(page, "moderador@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    await page.getByRole("tab", { name: "Reclamos de comercio" }).click();
    await expect(
      page.getByRole("heading", { name: "Reclamos de titularidad" })
    ).toBeVisible();
    await expect(page.getByText("don_jose · 3001234567")).toBeVisible();
    await analizarAxe(page, "pestaña Reclamos de comercio");
  });
});

test.describe("Disputa de precio en la cola de moderación (D-01)", () => {
  test("muestra ambos precios y solo las decisiones que el backend acepta", async ({ page }) => {
    let decisionEnviada: unknown;
    await configurarMocksNucleo(page, {
      rol: "moderador",
      autorizadoInicial: true,
      casoModeracion: "disputa_precio",
      alResolverCaso: (cuerpo) => {
        decisionEnviada = cuerpo;
      },
    });
    await ingresar(page, "moderador@armenia.co");
    await page.goto("/gestion", { waitUntil: "networkidle" });

    const filtro = page.locator("#filtro-tipo-caso");
    await expect(filtro.locator('option[value="disputa_precio"]')).toHaveText(
      "Disputa de precio"
    );
    await expect(filtro.locator('option[value="verificacion_comercio"]')).toHaveText(
      "Verificación de comercio"
    );
    await filtro.selectOption("disputa_precio");

    await page.getByRole("button", { name: "Revisar" }).click();
    await expect(page.locator('[data-prueba="detalle-disputa"]')).toBeVisible();
    await expect(page.locator('[data-prueba="precio-oficial-disputa"]')).toContainText("$3.700");
    await expect(page.locator('[data-prueba="precio-comunidad-disputa"]')).toContainText(
      "$3.000"
    );
    await expect(page.getByText(/Diferencia: 18,9 %/)).toBeVisible();
    await expect(page.getByText(/4 reportes · 3 fuentes/)).toBeVisible();

    const opciones = page.locator("#decision-caso option");
    await expect(opciones).toHaveText([
      "Dar la razón al comercio (confirmar)",
      "Dar la razón a la comunidad (descartar)",
    ]);
    await expect(page.getByText(/sancionar/i)).toHaveCount(0);

    await page.selectOption("#decision-caso", "confirmar");
    await page.fill("#nota-caso", "Contraste verificado en góndola");
    await page.getByRole("button", { name: "Guardar resolución" }).click();

    await expect(page.getByText(/resuelto: gana el comercio/)).toBeVisible();
    expect(decisionEnviada).toEqual({
      decision: "confirmar",
      nota: "Contraste verificado en góndola",
      sancion: null,
    });
  });

  for (const tema of TEMAS) {
    test(`el panel de disputa en modo ${tema} no tiene violaciones axe críticas o serias`, async ({
      page,
    }) => {
      await page.addInitScript((valor) => {
        try {
          window.localStorage.setItem("tema", valor);
        } catch {
          // Sin almacenamiento disponible la pagina cae al tema del sistema.
        }
      }, tema);
      await configurarMocksNucleo(page, {
        rol: "moderador",
        autorizadoInicial: true,
        casoModeracion: "disputa_precio",
      });
      await ingresar(page, "moderador@armenia.co");
      await page.goto("/gestion", { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Revisar" }).click();
      await expect(page.locator('[data-prueba="detalle-disputa"]')).toBeVisible();

      const esOscuro = await page.evaluate(() =>
        document.documentElement.classList.contains("dark")
      );
      expect(esOscuro, `El tema ${tema} no quedo aplicado`).toBe(tema === "oscuro");
      await analizarAxe(page, `panel de disputa (modo ${tema})`);
    });
  }
});

test.describe("Aviso D-02 de revalidación del precio oficial", () => {
  test("la ficha de tienda muestra el motivo sin romper el sello oficial", async ({ page }) => {
    await configurarMocksNucleo(page, {
      presentacionesComercio: 2,
      preciosOficialesComercio: 2,
      revalidacionComercio: true,
    });
    await page.goto(`/tienda/${TIENDA_A}`, { waitUntil: "networkidle" });

    await expect(
      page.getByRole("heading", { name: /Precios vigentes en este establecimiento/ })
    ).toBeVisible();
    const avisos = page.locator('[data-prueba="aviso-revalidacion"]');
    await expect(avisos).toHaveCount(2);
    await expect(avisos.first()).toContainText(
      "Precio oficial por revalidar: 45 días sin cambios"
    );
    await expect(page.getByText("Precio oficial", { exact: true }).first()).toBeVisible();
    await analizarAxe(page, "ficha de tienda con aviso D-02");
  });

  test("el comparador muestra el motivo del precio oficial por revalidar", async ({ page }) => {
    await configurarMocksNucleo(page, { revalidacionComparacion: true });
    await page.goto(`/producto/${PROD_ID}`, { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: "Arroz blanco", exact: true })).toBeVisible();
    const aviso = page.locator('[data-prueba="aviso-revalidacion"]');
    await expect(aviso).toBeVisible();
    await expect(aviso).toContainText("Precio oficial por revalidar: 45 días sin cambios");
    await expect(page.getByText("Precio oficial", { exact: true })).toBeVisible();
    await analizarAxe(page, "comparador con aviso D-02");
  });
});

test("el identificador de la tienda de prueba no cambió", () => {
  expect(TIENDA_A).toBe("11111111-2222-3333-4444-555555555555");
});
