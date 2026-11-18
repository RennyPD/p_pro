import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Usuario o correo").fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Entrar a Nexo" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test("configura módulos por cuenta y aplica la revocación al abrir el enlace", async ({ page, request, browser }) => {
  const base = "http://127.0.0.3:8012";
  const admin = { username: "admin.horizonte", password: "NexoAdmin2026!" };
  const auth = await request.post(`${base}/auth/login`, { data: admin });
  expect(auth.status()).toBe(200);
  const headers = { Authorization: `Bearer ${(await auth.json()).access_token}` };
  const role = await request.post(`${base}/roles/`, { headers, data: { name: "consulta_qa", description: "Consulta QA" } });
  expect(role.status()).toBe(200);
  const username = "consulta.qa";
  const password = "NexoConsulta2026!";
  const account = await request.post(`${base}/users/`, { headers, data: {
    username, password, email: "consulta.qa@example.com", role_id: (await role.json()).role_id,
  } });
  expect(account.status()).toBe(200);

  await login(page, admin.username, admin.password);
  await page.goto("/users");
  await page.getByPlaceholder(/Buscar/).fill(username);
  const row = page.getByRole("row").filter({ hasText: username });
  await row.getByRole("button", { name: "Módulos" }).click();
  const editor = page.getByRole("dialog", { name: `Módulos de ${username}` });
  await editor.getByRole("checkbox", { name: "Estudiantes", exact: true }).check();
  await editor.getByRole("button", { name: "Guardar módulos" }).click();
  await expect(editor).toHaveCount(0);

  const observerContext = await browser.newContext({ baseURL: "http://127.0.0.3:5176" });
  try {
    const observer = await observerContext.newPage();
    await login(observer, username, password);
    const nav = observer.getByRole("navigation", { name: "Navegación principal" });
    await nav.getByRole("link", { name: "Estudiantes", exact: true }).click();
    await expect(observer.getByRole("heading", { name: "Estudiantes", exact: true })).toBeVisible();
    await expect(observer.getByRole("columnheader", { name: "Matrícula" })).toBeVisible();
    await observer.goto("/modules/teachers");
    await expect(observer.getByRole("heading", { name: "Módulo no disponible" })).toBeVisible();
    await row.getByRole("button", { name: "Módulos" }).click();
    await editor.getByRole("checkbox", { name: "Estudiantes", exact: true }).uncheck();
    await editor.getByRole("button", { name: "Guardar módulos" }).click();
    await expect(editor).toHaveCount(0);
    await observer.goto("/modules/students");
    await expect(observer.getByRole("heading", { name: "Módulo no disponible" })).toBeVisible();
  } finally {
    await observerContext.close();
  }
});

test("asigna el pensum individual desde el historial del expediente", async ({ page, request }) => {
  const student = await request.post("http://127.0.0.3:8012/auth/login", {
    data: { username: "estudiante.001", password: "NexoEstudiante2026!" },
  });
  expect(student.status()).toBe(200);
  const { user } = await student.json();
  await login(page, "admin.horizonte", "NexoAdmin2026!");
  await page.goto(`/students/${user.student_id}`);
  await page.getByRole("button", { name: "Trayectoria académica", exact: true }).click();
  const version = page.getByRole("combobox", { name: "Versión del pensum", exact: true });
  const option = await version.locator("option").nth(1).evaluate((item: HTMLOptionElement) => item.value);
  await version.selectOption(option);
  await page.getByLabel("Motivo de la asignación").fill("Resolución ficticia de prueba");
  await page.getByRole("button", { name: "Asignar versión" }).click();
  await expect(page.getByText(`Versión asignada · ${option}`)).toBeVisible();
  const course = page.getByRole("listitem").filter({ hasText: "Fundamentos de Programación" });
  await course.getByRole("button", { name: "Verificar créditos" }).click();
  await page.getByRole("textbox", { name: "Versión original" }).fill(option);
  await page.getByRole("spinbutton", { name: "Créditos originales" }).fill("4");
  await page.getByRole("textbox", { name: "Referencia del respaldo institucional" }).fill("Registro ficticio QA");
  await page.getByRole("button", { name: "Guardar verificación" }).click();
  await expect(course).toHaveCount(0);
});

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
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "Abrir menú" }).click();
    await page.getByRole("link", { name: "Mi seguridad", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Mi seguridad" })).toBeVisible();
    await expect(page.getByText("Estado: desactivada")).toBeVisible();
    await expect(page.getByText(/Iniciada el/).first()).toBeVisible();
    if (profile.name === "teacher") {
      await page.getByRole("button", { name: "Configurar autenticador" }).click();
      await expect(page.getByLabel("Código del nuevo autenticador")).toBeVisible();
      await page.getByRole("button", { name: "Cancelar", exact: true }).click();
      await expect(page.getByRole("button", { name: "Configurar autenticador" })).toBeVisible();
      await page.getByRole("button", { name: "Cerrar todas las sesiones" }).click();
      await expect(page).toHaveURL(/\/login$/);
      expect((await request.get("http://127.0.0.3:8012/auth/me", { headers })).status()).toBe(401);
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

test("admin publishes a draft and can filter the resulting audit event", async ({ page, request }) => {
  const base = "http://127.0.0.3:8012";
  const auth = await request.post(`${base}/auth/login`, { data: { username: "admin.horizonte", password: "NexoAdmin2026!" } });
  expect(auth.status()).toBe(200);
  const headers = { Authorization: `Bearer ${(await auth.json()).access_token}` };
  const periods = await request.get(`${base}/periods/?active=true&limit=1`, { headers });
  const [period] = await periods.json();
  const existing = await request.get(`${base}/sections/?limit=1`, { headers });
  const [source] = await existing.json();
  const code = `PUBLICAR-QA-${Date.now()}`;
  const draft = await request.post(`${base}/sections/`, {
    headers,
    data: {
      code, description: "Prueba de publicación", subject_id: source.subject_id,
      teacher_id: source.teacher_id, period_name: period.name, status: "draft",
      capacity: 20, minimum_capacity: 2, days_of_week: ["Domingo"],
      start_time: "23:15", end_time: "23:45",
    },
  });
  expect(draft.status()).toBe(200);
  await login(page, "admin.horizonte", "NexoAdmin2026!");
  await page.getByRole("link", { name: "Secciones", exact: true }).click();
  await page.getByPlaceholder("Buscar código o asignatura").fill(code);
  await page.getByRole("button", { name: `Publicar ${code}`, exact: true }).click();
  await expect(page.getByRole("dialog", { name: `Publicar ${code}` })).toBeVisible();
  await page.getByRole("button", { name: "Confirmar publicación" }).click();
  await expect(page.getByRole("cell", { name: "Publicada", exact: true })).toBeVisible();
  await page.goto("/settings/audit");
  await page.getByLabel("Acción", { exact: true }).selectOption("section.published");
  await page.getByRole("button", { name: "Filtrar" }).click();
  await expect(page.getByRole("cell", { name: "Sección publicada", exact: true }).first()).toBeVisible();
});

test("admin edits an account without reentering its password", async ({ page, request }) => {
  const base = "http://127.0.0.3:8012";
  const auth = await request.post(`${base}/auth/login`, { data: { username: "admin.horizonte", password: "NexoAdmin2026!" } });
  expect(auth.status()).toBe(200);
  const { access_token, user } = await auth.json();
  const suffix = Date.now();
  const username = `cuenta-qa-${suffix}`;
  const headers = { Authorization: `Bearer ${access_token}` };
  const account = await request.post(`${base}/users/`, {
    headers, data: { username, email: `cuenta-${suffix}@example.com`, password: "NexoFicticio2026!", role_id: user.role_id },
  });
  expect(account.status()).toBe(200);
  await login(page, "admin.horizonte", "NexoAdmin2026!");
  await page.goto("/users");
  await page.getByPlaceholder("Buscar usuario o correo").fill(username);
  const row = page.getByRole("row").filter({ hasText: username });
  await row.getByRole("button", { name: /Editar usuario/ }).click();
  const dialog = page.getByRole("dialog", { name: "Editar usuario" });
  await expect(dialog.locator('input[type="password"]')).toHaveCount(0);
  await dialog.getByLabel("Correo", { exact: true }).fill(`editada-${suffix}@example.com`);
  await dialog.getByRole("button", { name: "Guardar cuenta" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(row.getByText(`editada-${suffix}@example.com`, { exact: true })).toBeVisible();
});

test("the student can read a filed document and request approval without changing the record", async ({ page, request }) => {
  const base = "http://127.0.0.3:8012";
  const studentLogin = await request.post(`${base}/auth/login`, { data: { username: "estudiante.001", password: "NexoEstudiante2026!" } });
  expect(studentLogin.status()).toBe(200);
  const { user } = await studentLogin.json();
  const suffix = Date.now();
  const filename = `archivo-ficticio-${suffix}.png`;
  const reason = `Revisión QA de expediente ${suffix}`;
  await login(page, "admin.horizonte", "NexoAdmin2026!");
  await page.goto(`/students/${user.student_id}`);
  await page.getByRole("button", { name: "Documentos", exact: true }).click();
  await page.getByRole("button", { name: "Agregar documento" }).click();
  const upload = page.getByRole("dialog", { name: "Agregar documento al expediente" });
  await upload.getByLabel("Tipo de documento").fill("Archivo ficticio");
  await upload.locator('input[type="file"]').setInputFiles({
    name: filename, mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jX1sAAAAASUVORK5CYII=", "base64"),
  });
  await upload.getByRole("button", { name: "Guardar documento" }).click();
  await expect(upload).toHaveCount(0);
  await expect(page.getByRole("button", { name: `Descargar ${filename}` })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar sesión", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page, "estudiante.001", "NexoEstudiante2026!");
  await page.getByRole("link", { name: "Mi expediente", exact: true }).click();
  const file = page.getByRole("button", { name: `Descargar ${filename}` });
  await expect(file).toBeVisible();
  const [download] = await Promise.all([page.waitForEvent("download"), file.click()]);
  expect(download.suggestedFilename()).toBe(filename);
  await page.getByRole("button", { name: "Solicitar revisión", exact: true }).click();
  await page.getByLabel("Motivo de la solicitud").fill(reason);
  await page.getByRole("button", { name: "Enviar solicitud" }).click();
  await expect(page.getByRole("dialog", { name: "Solicitar revisión" })).toHaveCount(0);
  await page.getByRole("link", { name: "Mis solicitudes", exact: true }).click();
  await expect(page.getByText(reason, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar sesión", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page, "admin.horizonte", "NexoAdmin2026!");
  await page.getByRole("link", { name: "Mis solicitudes", exact: true }).click();
  await page.getByRole("button", { name: "Bandeja institucional" }).click();
  await page.locator("article").filter({ hasText: reason }).getByRole("button", { name: "Revisar solicitud" }).click();
  await page.getByLabel("Motivo de la decisión").fill("Revisión de aceptación QA");
  await page.getByRole("button", { name: "Registrar decisión" }).click();
  await expect(page.locator("article").filter({ hasText: reason }).getByText("Aprobada", { exact: true })).toBeVisible();
  await page.goto(`/students/${user.student_id}`);
  await page.getByRole("button", { name: "Documentos", exact: true }).click();
  await expect(page.getByRole("button", { name: `Descargar ${filename}` })).toHaveCount(1);
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
