import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  beforeEach(() => useAuthStore.getState().clearSession());
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });
  it("presents a clear institutional sign-in form", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("heading", { name: "Qué bueno verte" })).toBeInTheDocument();
    expect(screen.getByLabelText("Usuario o correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entrar a Nexo" })).toBeInTheDocument();
  });

  it("asks for the institution code when the username exists in several", async () => {
    const post = vi
      .spyOn(api, "post")
      .mockRejectedValueOnce({
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            detail: "Esa cuenta existe en varias instituciones. Indica el código de tu institución",
          },
        },
      })
      .mockResolvedValueOnce({ data: { access_token: "t", user: { user_id: 2 } } });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.queryByLabelText("Código de tu institución")).toBeNull();
    await userEvent.type(screen.getByLabelText("Usuario o correo"), "demo.admin");
    await userEvent.type(screen.getByLabelText("Contraseña"), "SegundaAdmin2026!");
    await userEvent.click(screen.getByRole("button", { name: "Entrar a Nexo" }));
    const code = await screen.findByLabelText("Código de tu institución");
    await userEvent.type(code, "segundo");
    await userEvent.click(screen.getByRole("button", { name: "Entrar a Nexo" }));
    await waitFor(() =>
      expect(post).toHaveBeenLastCalledWith(
        "/auth/login",
        expect.objectContaining({ username: "demo.admin", institution: "segundo" }),
      ),
    );
  });
});
