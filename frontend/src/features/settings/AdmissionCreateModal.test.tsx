import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { AdmissionCreateModal } from "./AdmissionCreateModal";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it("registers a new admission and preserves input on server failure", async () => {
  vi.spyOn(api, "get").mockResolvedValue({ data: [{ career_id: 8, name: "Ingeniería", status: "active" }] });
  const post = vi.spyOn(api, "post").mockRejectedValueOnce(new Error("Servicio no disponible")).mockResolvedValueOnce({ data: {} });
  const onCreated = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AdmissionCreateModal onClose={() => {}} onCreated={onCreated} /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Nombres"), { target: { value: " Ana " } });
  fireEvent.change(screen.getByLabelText("Apellidos"), { target: { value: "Prueba" } });
  fireEvent.change(screen.getByLabelText("Correo del aspirante"), { target: { value: "ana@example.com" } });
  fireEvent.change(screen.getByLabelText("Teléfono del aspirante"), { target: { value: "8095550100" } });
  await screen.findByRole("option", { name: "Ingeniería" });
  fireEvent.change(screen.getByLabelText("Programa solicitado"), { target: { value: "8" } });
  fireEvent.click(screen.getByRole("button", { name: "Registrar solicitud" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Nombres")).toHaveValue(" Ana ");
  expect(onCreated).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Registrar solicitud" }));
  await waitFor(() => expect(onCreated).toHaveBeenCalledOnce());
  expect(post).toHaveBeenLastCalledWith("/operations/admissions", expect.objectContaining({ first_name: "Ana", career_id: 8 }));
});
