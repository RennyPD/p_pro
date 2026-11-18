import { expect, test } from "@playwright/test";

for (const viewport of [
  { width: 1366, height: 900 },
  { width: 390, height: 844 },
]) {
  for (const count of [17, 125]) {
    test(`catalog selector with ${count} options is complete and readable at ${viewport.width}px`, async ({
      page,
    }, testInfo) => {
      await page.setViewportSize(viewport);
      const subjects = Array.from({ length: count }, (_, index) => ({
        subject_id: index + 1,
        code: `MAT-${index + 1}`,
        description:
          index === count - 1
            ? "Álgebra avanzada y métodos cuantitativos para la gestión institucional"
            : `Asignatura de prueba ${index + 1}`,
      }));
      const user = {
        user_id: 1,
        username: "admin.test",
        email: "admin@example.test",
        role_id: 1,
        role_name: "admin",
        student_id: null,
        teacher_id: null,
      };
      await page.route("http://127.0.0.1:48017/**", async route => {
        const url = new URL(route.request().url());
        let data: unknown = [];
        if (url.pathname === "/auth/login") data = { access_token: "test-only", user };
        if (url.pathname === "/auth/me") data = user;
        if (url.pathname === "/access/me") data = { permissions: ["academic.manage", "reports.view"] };
        if (url.pathname === "/dashboard/summary") data = { alerts: [], metrics: [] };
        if (url.pathname === "/subjects/") {
          const skip = Number(url.searchParams.get("skip") || 0);
          data = subjects.slice(skip, skip + Number(url.searchParams.get("limit") || 50));
        }
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
      });
      await page.goto("/login");
      await page.getByLabel("Usuario o correo").fill("admin.test");
      await page.locator('input[name="password"]').fill("TestOnly2026!");
      await page.getByRole("button", { name: "Entrar a Nexo" }).click();
      await expect(page.getByRole("link", { name: "Control institucional" })).toBeAttached();
      if (viewport.width < 768) await page.getByRole("button", { name: "Abrir menú" }).click();
      await page.getByRole("link", { name: "Secciones", exact: true }).click();
      await page.getByRole("button", { name: "Nueva sección" }).click();
      await page.getByRole("button", { name: /Asignatura.*Buscar asignatura/ }).click();
      await expect(page.getByText(`Mostrando 1–8 de ${count} opciones`)).toBeVisible();
      if (count === 17) {
        await page.getByRole("button", { name: "MAT-1 · Asignatura de prueba 1", exact: true }).click();
        await page.getByRole("button", { name: "Asignatura * MAT-1 · Asignatura de prueba 1", exact: true }).click();
      }
      await page.getByRole("button", { name: "Opciones siguientes" }).click();
      await expect(page.getByText(`Mostrando 9–16 de ${count} opciones`)).toBeVisible();
      if (count === 17) {
        await page.getByRole("button", { name: "Opciones siguientes" }).click();
        await expect(page.getByText("Mostrando 17–17 de 17 opciones")).toBeVisible();
        await expect(page.getByRole("button", { name: /MAT-17.*Álgebra/ })).toBeVisible();
        await expect(
          page.getByRole("button", { name: "Asignatura * MAT-1 · Asignatura de prueba 1", exact: true }),
        ).toBeVisible();
        await expect(page.getByRole("button", { name: "Opciones siguientes" })).toBeDisabled();
        await page.getByRole("button", { name: "Opciones anteriores" }).click();
        await page.getByRole("button", { name: "Opciones anteriores" }).click();
        await expect(page.getByText("Mostrando 1–8 de 17 opciones")).toBeVisible();
        await page.getByRole("button", { name: "Opciones siguientes" }).focus();
        await page.keyboard.press("Enter");
        await page.getByRole("button", { name: "Opciones siguientes" }).focus();
        await page.keyboard.press("Enter");
        await expect(page.getByText("Mostrando 17–17 de 17 opciones")).toBeVisible();
        await page.getByRole("button", { name: /MAT-17.*Álgebra/ }).click();
        await page.getByRole("button", { name: /Asignatura.*MAT-17/ }).click();
        await expect(page.getByText("Mostrando 17–17 de 17 opciones")).toBeVisible();
      }
      const search = page.getByRole("searchbox", { name: "Buscar opciones" });
      await search.fill("algebra");
      await expect(page.getByText(`Mostrando 1–1 de 1 opciones · ${count} en total`)).toBeVisible();
      await search.scrollIntoViewIfNeeded();
      const bounds = await page.locator(".lookup-search").evaluate(element => {
        const icon = element.querySelector("svg")!.getBoundingClientRect();
        const input = element.querySelector("input")!.getBoundingClientRect();
        const panel = element.closest(".lookup-popover")!.getBoundingClientRect();
        return {
          iconRight: icon.right,
          inputLeft: input.left,
          panelLeft: panel.left,
          panelRight: panel.right,
          screen: window.innerWidth,
        };
      });
      expect(bounds.inputLeft - bounds.iconRight).toBeGreaterThanOrEqual(6);
      expect(bounds.panelLeft).toBeGreaterThanOrEqual(0);
      expect(bounds.panelRight).toBeLessThanOrEqual(bounds.screen);
      await page.screenshot({ path: testInfo.outputPath(`selector-${viewport.width}.png`) });
      await page.getByRole("button", { name: new RegExp(`^MAT-${count}.*Álgebra`) }).click();
      await expect(page.getByRole("button", { name: new RegExp(`Asignatura.*MAT-${count}`) })).toBeVisible();
      await expect(page.locator(".lookup-popover")).toHaveCount(0);
      if (count === 17 && viewport.width === 1366) {
        const confirmation = page.waitForEvent("dialog");
        await page.evaluate(() => history.back());
        const change = await confirmation;
        expect(change.message()).toContain("Hay cambios sin guardar");
        await change.dismiss();
        await expect(page).toHaveURL(/\/sections$/);
        await expect(page.getByRole("button", { name: /Asignatura.*MAT-17/ })).toBeVisible();
      }
    });
  }
}
