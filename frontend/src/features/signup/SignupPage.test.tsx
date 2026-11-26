import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { SignupPage } from "./SignupPage";

const config = (enabled = true) => ({
  enabled,
  trial_days: 30,
  plans: [
    {
      code: "basico",
      name: "Básico",
      description: "",
      currency: "USD",
      monthly_price: "99.00",
      max_students: 300,
    },
    {
      code: "profesional",
      name: "Profesional",
      description: "",
      currency: "USD",
      monthly_price: "249.00",
      max_students: 1500,
    },
  ],
});

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SignupPage", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("creates the institution and asks to check the email", async () => {
    vi.spyOn(api, "get").mockImplementation(async url =>
      url === "/public/signup"
        ? ({ data: config() } as never)
        : ({ data: { available: false, reason: "Ese código ya está en uso" } } as never),
    );
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { message: "Te enviamos un correo para activar la cuenta." } });
    renderPage();
    expect(await screen.findByText("Prueba gratuita de 30 días")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Nombre de la institución"), "Colegio Nuevo");
    const code = screen.getByLabelText(/Código/);
    await userEvent.type(code, "principal");
    await userEvent.tab();
    expect(await screen.findByText("Ese código ya está en uso")).toBeInTheDocument();
    await userEvent.clear(code);
    await userEvent.type(code, "colegio-nuevo");
    await userEvent.type(screen.getByLabelText("Correo del administrador"), "dir@colegio.edu.do");
    await userEvent.click(screen.getByLabelText(/Básico/));
    await userEvent.click(screen.getByRole("button", { name: "Crear la cuenta" }));
    expect(await screen.findByText(/Acepta los términos/)).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Crear la cuenta" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/public/signup",
        expect.objectContaining({
          name: "Colegio Nuevo",
          code: "colegio-nuevo",
          admin_email: "dir@colegio.edu.do",
          plan_code: "basico",
          website: "",
          accept_terms: true,
        }),
      ),
    );
    expect(await screen.findByRole("heading", { name: "Revisa tu correo" })).toBeInTheDocument();
  });

  it("explains when sign-up is closed", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: config(false) });
    renderPage();
    expect(
      await screen.findByRole("heading", { name: "Registro no disponible" }),
    ).toBeInTheDocument();
  });
});
