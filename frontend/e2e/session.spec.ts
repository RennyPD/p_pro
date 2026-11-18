import { expect, test, type Page } from "@playwright/test";

const user = { user_id: 1, username: "admin.session", email: "session@example.com", role_id: 1, role_name: "admin", student_id: null, teacher_id: null };
const jwt = (expires: number) => `header.${Buffer.from(JSON.stringify({ sub: "1", exp: expires })).toString("base64url")}.test-signature`;

async function setup(page: Page, mode: "concurrent" | "proactive" | "revoked") {
  const now = Date.now();
  if (mode === "proactive") await page.clock.install({ time: now });
  const oldToken = jwt(Math.floor(now / 1000) + (mode === "proactive" ? 120 : 3600));
  const newToken = jwt(Math.floor(now / 1000) + 7200);
  let refreshes = 0;
  let oldFailures = 0;
  await page.route("http://127.0.0.1:48017/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const fulfill = (data: unknown, status = 200, headers = {}) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data), headers });
    if (path === "/auth/login") return fulfill({ access_token: oldToken, token_type: "bearer", user }, 200, { "Set-Cookie": "refresh_token=test-cookie; HttpOnly; SameSite=Lax; Path=/auth" });
    if (path === "/auth/refresh") {
      refreshes++;
      expect(request.headers().cookie).toContain("refresh_token=test-cookie");
      if (mode === "revoked") return fulfill({ detail: "Refresh session expired" }, 401);
      return fulfill({ access_token: newToken, token_type: "bearer", user });
    }
    if (mode !== "proactive" && request.headers().authorization === `Bearer ${oldToken}`) {
      oldFailures++;
      return fulfill({ detail: "Tu sesión expiró. Inicia sesión de nuevo" }, 401);
    }
    if (path === "/auth/me") return fulfill(user);
    if (path === "/access/me") return fulfill({ permissions: ["academic.manage", "reports.view"] });
    if (path === "/dashboard/summary") return fulfill({ metrics: [], alerts: [] });
    return fulfill([]);
  });
  await page.goto("/login");
  await page.getByLabel("Usuario o correo").fill(user.username);
  await page.locator('input[name="password"]').fill("TestOnly2026!");
  await page.getByRole("button", { name: "Entrar a Nexo" }).click();
  return { refreshes: () => refreshes, oldFailures: () => oldFailures, newToken };
}

test("simultaneous expired-token responses renew once and retain the logged-in profile", async ({ page }) => {
  const state = await setup(page, "concurrent");
  await expect(page.getByRole("heading", { name: "Hola, admin.session" })).toBeVisible();
  await expect.poll(state.oldFailures).toBeGreaterThan(1);
  await expect.poll(state.refreshes).toBe(1);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Hola, admin.session" })).toBeVisible();
  expect(state.refreshes()).toBe(1);
});

test("renews before expiry while retaining an open teacher form and its draft", async ({ page }) => {
  const state = await setup(page, "proactive");
  await expect(page.getByRole("heading", { name: "Hola, admin.session" })).toBeVisible();
  await page.getByRole("link", { name: "Docentes", exact: true }).click();
  await page.getByRole("button", { name: "Nuevo docente" }).click();
  await page.getByLabel("Nombres").fill("Borrador conservado");
  await page.clock.fastForward(65_000);
  await expect.poll(state.refreshes).toBe(1);
  await expect(page.getByLabel("Nombres")).toHaveValue("Borrador conservado");
  await expect(page.getByRole("heading", { name: "Nuevo docente" })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem("nexo_access_token"))).toBe(state.newToken);
});

test("a revoked refresh session still requires a new login", async ({ page }) => {
  const state = await setup(page, "revoked");
  await expect(page.getByRole("button", { name: "Entrar a Nexo" })).toBeVisible();
  await expect.poll(state.refreshes).toBe(1);
  await expect(page).toHaveURL(/\/login$/);
});
