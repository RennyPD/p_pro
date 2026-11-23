import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "../../store/auth";
import { platformApi, usePlatformSession } from "../../lib/platformApi";
import { PlatformPage } from "./PlatformPage";

const institution = {
  institution_id: 2,
  name: "Liceo Horizonte",
  code: "liceo-horizonte",
  status: "active",
  contact_email: "direccion@horizonte.edu.do",
  created_at: "2026-11-24T10:00:00",
  usage: { students: 120, users: 9, last_activity: null },
};

function renderPage() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <PlatformPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PlatformPage", () => {
  beforeEach(() => usePlatformSession.getState().signOut());
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("signs in with the verification code and keeps its own session", async () => {
    const post = vi
      .spyOn(platformApi, "post")
      .mockResolvedValue({ data: { access_token: "plataforma", email: "a@b.do", name: "Equipo" } });
    vi.spyOn(platformApi, "get").mockImplementation(async url =>
      url === "/platform/me"
        ? ({ data: { platform_admin_id: 1, email: "a@b.do", name: "Equipo" } } as never)
        : ({ data: [], headers: { "x-total-count": "0" } } as never),
    );
    renderPage();
    await userEvent.type(screen.getByLabelText("Correo"), "soporte@nexo.com.do");
    await userEvent.type(screen.getByLabelText("Contraseña"), "PlataformaNexo2026!");
    await userEvent.type(screen.getByLabelText("Código de verificación"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/platform/auth/login", {
        email: "soporte@nexo.com.do",
        password: "PlataformaNexo2026!",
        otp: "123456",
      }),
    );
    expect(await screen.findByRole("heading", { name: "Instituciones" })).toBeInTheDocument();
    expect(usePlatformSession.getState().token).toBe("plataforma");
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("lists institutions with their usage and suspends with a reason", async () => {
    usePlatformSession.getState().signIn("plataforma");
    vi.spyOn(platformApi, "get").mockImplementation(async url =>
      url === "/platform/institutions"
        ? ({ data: [institution], headers: { "x-total-count": "1" } } as never)
        : ({ data: url === "/platform/me" ? { name: "Equipo" } : [] } as never),
    );
    const post = vi.spyOn(platformApi, "post").mockResolvedValue({ data: {} });
    renderPage();
    const row = (await screen.findByText("Liceo Horizonte")).closest("tr") as HTMLElement;
    expect(within(row).getByText("120")).toBeInTheDocument();
    expect(within(row).getByText("Activa")).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: "Suspender" }));
    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "Suspender" });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Motivo"), "Pago pendiente");
    await userEvent.click(confirm);
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/platform/institutions/2/suspend", {
        reason: "Pago pendiente",
      }),
    );
  });
});
