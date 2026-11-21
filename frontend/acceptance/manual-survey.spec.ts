import { expect, test, type Page } from "@playwright/test";

// Read-only visual survey against the disposable migrated acceptance server.
const profiles = [
  ["admin", "admin.horizonte", "NexoAdmin2026!"],
  ["teacher", "profesor.01", "NexoDocente2026!"],
  ["student", "estudiante.001", "NexoEstudiante2026!"],
  ["guardian", "tutor.01", "NexoTutor2026!"],
] as const;

async function enter(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Usuario o correo").fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Entrar a Nexo" }).click();
  await expect(page.getByRole("navigation", { name: "Navegación principal" })).toBeAttached();
  await page.waitForLoadState("networkidle");
}

for (const [role, username, password] of profiles) {
  test(`manual survey: ${role} navigation on desktop and mobile`, async ({ page }, testInfo) => {
    test.setTimeout(180_000);
    await enter(page, username, password);
    const nav = page.getByRole("navigation", { name: "Navegación principal", includeHidden: true });
    const routes = await nav
      .getByRole("link", { includeHidden: true })
      .evaluateAll(links => links.map(link => link.getAttribute("href")!).filter(Boolean));
    const evidence: object[] = [];
    for (const width of [1366, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of [...new Set([...routes, "/account"])]) {
        const failures: string[] = [];
        const onError = (error: Error) => failures.push(error.message);
        const onResponse = (response: import("@playwright/test").Response) => {
          if (response.url().startsWith("http://127.0.0.3:8012") && response.status() >= 400)
            failures.push(`${response.status()} ${new URL(response.url()).pathname}`);
        };
        page.on("pageerror", onError);
        page.on("response", onResponse);
        await page.goto(route);
        await page.waitForLoadState("networkidle");
        await expect(page).toHaveURL(url => url.pathname === route);
        await expect(page.locator("main h1").first()).toBeVisible();
        const layout = await page.locator("main").evaluate(main => {
          const viewport = document.documentElement.clientWidth;
          return {
            overflow: Math.max(0, document.documentElement.scrollWidth - viewport),
            selects: main.querySelectorAll("select").length,
            searches: main.querySelectorAll(
              'input[type=search], input[placeholder*="Buscar"], .search-box input',
            ).length,
          };
        });
        evidence.push({
          route,
          width,
          renderedRoute: new URL(page.url()).pathname,
          heading: await page.locator("main h1").allTextContents(),
          ...layout,
          failures,
        });
        page.off("pageerror", onError);
        page.off("response", onResponse);
      }
    }
    await testInfo.attach("survey.json", {
      body: JSON.stringify(evidence, null, 2),
      contentType: "application/json",
    });
    expect(evidence.length).toBeGreaterThan(2);
    expect(evidence.filter(item => (item as { width: number }).width === 390)).toHaveLength(
      new Set([...routes, "/account"]).size,
    );
  });
}

test("manual survey: admin directory searches and section selector", async ({ page }, testInfo) => {
  await enter(page, profiles[0][1], profiles[0][2]);
  const evidence: object[] = [];
  for (const [route, valid] of [
    ["/students", "ITH-2026-00001"],
    ["/teachers", "Ana"],
    ["/subjects", "Programación"],
    ["/careers", "Software"],
    ["/sections", "DS-101-A"],
    ["/periods", "2026-2027"],
  ]) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    const search = page.locator(".resource-toolbar .search-box input").first();
    if (!(await search.count())) {
      evidence.push({ route, control: "directory search", status: "not found" });
      continue;
    }
    for (const [variant, term] of [
      ["match", valid],
      ["no match", "qa-no-existe-987654"],
    ]) {
      const loaded = page
        .waitForResponse(
          response =>
            response.url().startsWith("http://127.0.0.3:8012/") &&
            new URL(response.url()).searchParams.get("q") === term,
        )
        .catch(() => null);
      await search.fill(term);
      const response = await loaded;
      const data: unknown = response?.ok() ? await response.json() : null;
      evidence.push({
        route,
        variant,
        status: response?.status(),
        matches: Array.isArray(data) ? data.length : null,
      });
    }
  }
  await page.goto("/sections");
  await page.getByRole("button", { name: "Nueva sección" }).click();
  const trigger = page.getByRole("button", { name: /Asignatura.*Buscar asignatura/ });
  await trigger.click();
  const filter = page.getByRole("searchbox", { name: "Buscar opciones" });
  await filter.fill("qa-no-existe-987654");
  await expect(page.getByText(/Sin coincidencias/)).toBeVisible();
  await filter.fill("");
  await expect(page.getByText(/Mostrando.*opciones/)).toBeVisible();
  await filter.press("Escape");
  await expect(trigger).toBeFocused();
  await expect(page.getByRole("heading", { name: "Nueva sección" })).toBeVisible();
  await testInfo.attach("searches.json", {
    body: JSON.stringify(evidence, null, 2),
    contentType: "application/json",
  });
});
