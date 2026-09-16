import { expect, test } from "@playwright/test";
test("shows the academic sign-in experience",async({page})=>{await page.goto("/login");await expect(page.getByRole("heading",{name:"Qué bueno verte"})).toBeVisible();await expect(page.getByText("Todo el pulso de tu comunidad educativa.")).toBeVisible();await expect(page.getByRole("button",{name:"Entrar a Nexo"})).toBeVisible();});
