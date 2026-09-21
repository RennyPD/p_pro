import { expect, test } from "@playwright/test";

const profiles = [
  { role: "admin", username: "admin.horizonte", student_id: null, teacher_id: null, expected: "Control institucional", permissions: ["academic.manage", "grades.manage", "finance.manage", "reports.view", "communications.manage"] },
  { role: "teacher", username: "profesor.01", student_id: null, teacher_id: 1, expected: "Mis secciones", permissions: ["academic.manage", "grades.manage", "communications.manage"] },
  { role: "student", username: "estudiante.001", student_id: 1, teacher_id: null, expected: "Elegir asignaturas", permissions: ["records.own"] },
  { role: "guardian", username: "tutor.01", student_id: null, teacher_id: null, guardian_id: 1, expected: "Seguimiento familiar", permissions: ["records.own"] },
];

for (const [index, profile] of profiles.entries()) {
  test(`${profile.role} receives the correct workspace`, async ({ page }) => {
    const user = { user_id: index + 1, email: `${profile.username}@example.com`, role_id: index + 1, role_name: profile.role, guardian_id: null, ...profile };
    await page.route("http://127.0.0.1:8000/**", async route => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/auth/login" || path === "/auth/me") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(path === "/auth/login" ? { access_token: "test-token", token_type: "bearer", user } : user) });
      if (path === "/access/me") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ permissions: profile.permissions }) });
      if (path === "/dashboard/summary") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ active_period: "2026-3", alerts: [], metrics: [] }) });
      return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });
    await page.goto("/login");
    await page.getByLabel("Usuario o correo").fill(profile.username);
    await page.locator('input[name="password"]').fill("NexoPrueba2026!");
    await page.getByRole("button", { name: "Entrar a Nexo" }).click();
    await expect(page.getByRole("link", { name: profile.expected })).toBeVisible();
  });
}
