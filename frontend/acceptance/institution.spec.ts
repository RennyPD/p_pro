import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Usuario o correo").fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Entrar a Nexo" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

for (const profile of [
  { name: "admin", username: "admin.horizonte", password: "NexoAdmin2026!", menu: "Control institucional" },
  { name: "teacher", username: "profesor.01", password: "NexoDocente2026!", menu: "Mis secciones" },
  { name: "student", username: "estudiante.001", password: "NexoEstudiante2026!", menu: "Elegir asignaturas" },
  { name: "guardian", username: "tutor.01", password: "NexoTutor2026!", menu: "Seguimiento familiar" },
]) {
  test(`real migrated backend: ${profile.name} workspace and isolation`, async ({ page, request }) => {
    await login(page, profile.username, profile.password);
    await expect(page.getByRole("link", { name: profile.menu, exact: true })).toBeVisible();
    if (profile.name !== "admin") await expect(page.getByRole("link", { name: "Control institucional", exact: true })).toHaveCount(0);
    const auth = await request.post("http://127.0.0.3:8012/auth/login", { data: { username: profile.username, password: profile.password } });
    expect(auth.ok()).toBeTruthy();
    const { access_token } = await auth.json();
    const headers = { Authorization: `Bearer ${access_token}` };
    if (profile.name === "teacher") {
      const denied = await request.patch("http://127.0.0.3:8012/sections/2", { headers, data: { description: "Forbidden" } });
      expect(denied.status()).toBe(403);
      await page.getByRole("link", { name: "Mis secciones", exact: true }).click();
      await page.getByRole("button", { name: /Ver asistencia de la sección/ }).first().click();
      await expect(page.getByRole("heading", { name: "Pase de lista" }).first()).toBeVisible();
    }
    if (profile.name === "guardian") {
      await expect(page.getByText("ITH-2026-00001", { exact: true })).toBeVisible();
      const denied = await request.get("http://127.0.0.3:8012/academic/students/120/grades", { headers });
      expect(denied.status()).toBe(403);
    }
  });
}

test("admissions can be created from the real interface", async ({ page }) => {
  await login(page, "admin.horizonte", "NexoAdmin2026!");
  await page.goto("/institutional-control");
  await page.getByRole("button", { name: "Admisiones", exact: true }).click();
  await page.getByRole("button", { name: "Nueva solicitud" }).click();
  const dialog = page.getByRole("dialog", { name: "Nueva solicitud de admisión" });
  await dialog.getByLabel("Nombres", { exact: true }).fill("Aceptación");
  await dialog.getByLabel("Apellidos").fill("Interfaz");
  await dialog.getByLabel("Correo del aspirante").fill(`aceptacion-${Date.now()}@example.com`);
  await dialog.getByLabel("Teléfono del aspirante").fill("8095550101");
  await dialog.getByLabel("Programa solicitado").selectOption({ index: 1 });
  await dialog.getByRole("button", { name: "Registrar solicitud" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Aceptación Interfaz" })).toBeVisible();
});

test("student confirms a real cart without native dialogs and keeps their seat", async ({ page, request }) => {
  const base = "http://127.0.0.3:8012";
  const auth = await request.post(`${base}/auth/login`, { data: { username: "admin.horizonte", password: "NexoAdmin2026!" } });
  const headers = { Authorization: `Bearer ${(await auth.json()).access_token}` };
  const profile = await (await request.get(`${base}/academic/students/1/profile`, { headers })).json();
  const periods = await (await request.get(`${base}/periods/`, { headers })).json();
  const period = periods.find((p: { active: boolean }) => p.active);
  const suffix = Date.now();
  const subjectResponse = await request.post(`${base}/subjects/`, { headers, data: { code: `E2E-${suffix}`, description: "Asignatura de aceptación real" } });
  expect(subjectResponse.ok()).toBeTruthy();
  const subject = await subjectResponse.json();
  const course = await request.post(`${base}/curriculum/courses`, { headers, data: { career_id: profile.career_id, subject_id: subject.subject_id, term_number: 1, credits: 1, curriculum_version: "2026" } });
  expect(course.ok()).toBeTruthy();
  const sectionResponse = await request.post(`${base}/sections/`, { headers, data: { code: `E2E-A-${suffix}`, description: "Aceptación", teacher_id: 1, subject_id: subject.subject_id, days_of_week: ["Domingo"], start_time: "20:00", end_time: "21:00", capacity: 1, period_name: period.name } });
  expect(sectionResponse.ok()).toBeTruthy();
  const section = await sectionResponse.json();
  await login(page, "estudiante.001", "NexoEstudiante2026!");
  await page.goto("/my-catalog");
  const card = page.locator("article").filter({ has: page.getByRole("heading", { name: "Asignatura de aceptación real" }) });
  await card.getByRole("button", { name: /Agregar/ }).click();
  await page.getByRole("button", { name: "Confirmar selección", exact: true }).click();
  await page.getByRole("dialog", { name: "Confirmar selección académica" }).getByRole("button", { name: "Confirmar", exact: true }).click();
  await expect(card.getByText("Tu plaza está reservada")).toBeVisible();
  await expect(card.getByText("Confirmada", { exact: true })).toBeVisible();
  await expect(card.getByText("Sin cupos para nuevas selecciones")).toHaveCount(0);
  const selections = await (await request.get(`${base}/enrollments/`, { headers })).json();
  expect(selections.filter((e: { section_id: number; state: string }) => e.section_id === section.section_id && e.state === "enrolled")).toHaveLength(1);
});
