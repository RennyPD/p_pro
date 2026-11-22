import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { ChoosePasswordPage, ForgotPasswordPage } from "./PasswordPages";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function at(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/recuperar" element={<ForgotPasswordPage />} />
        <Route path="/restablecer" element={<ChoosePasswordPage mode="reset" />} />
        <Route path="/activar" element={<ChoosePasswordPage mode="activate" />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("password pages", () => {
  it("requests a reset link and shows the same answer for any account", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: { message: "Si la cuenta existe y tiene correo, enviamos un enlace" },
    } as never);
    at("/recuperar");
    fireEvent.change(screen.getByLabelText("Usuario o correo"), { target: { value: " ana " } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar enlace" }));
    expect(await screen.findByRole("heading", { name: "Revisa tu correo" })).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/auth/password-reset/request", { identifier: "ana" });
  });

  it("checks both passwords before saving and sends the token from the link", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: null } as never);
    at("/activar?token=abc123abc123abc123abc123");
    expect(screen.getByRole("heading", { name: "Activa tu cuenta" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Contraseña nueva"), {
      target: { value: "Clave-segura-2026" },
    });
    fireEvent.change(screen.getByLabelText("Repite la contraseña"), {
      target: { value: "Otra-clave-2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar contraseña" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Las contraseñas no coinciden");
    expect(post).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Repite la contraseña"), {
      target: { value: "Clave-segura-2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar contraseña" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/auth/password-reset/confirm", {
        token: "abc123abc123abc123abc123",
        new_password: "Clave-segura-2026",
      }),
    );
    expect(await screen.findByRole("heading", { name: "Cuenta activada" })).toBeInTheDocument();
  });

  it("explains an incomplete link", () => {
    at("/restablecer");
    expect(screen.getByRole("heading", { name: "Enlace incompleto" })).toBeInTheDocument();
  });
});
