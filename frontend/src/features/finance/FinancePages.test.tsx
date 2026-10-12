import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { FinancePage } from "./FinancePages";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const summary = { student_id: 7, enrollment_number: "EST-2026-0001", student_name: "Daniel Santos", cutoff_day: 15, due_day: 30, total_charges: 15000, total_payments: 5000, total_adjustments: -200, balance: 9800, overdue_balance: 9800, transactions: [
  { transaction_id: 1, type: "charge", description: "Matrícula", amount: 15000, date: "2026-09-01T08:00:00", due_date: "2026-09-15", direction: "debit", status: "posted" },
  { transaction_id: 1, type: "adjustment", description: "Beca académica", amount: 200, date: "2026-09-01T08:00:00", direction: "credit", kind: "scholarship", status: "posted" },
] };
function setup(admin = false, accounts = false) {
  useAuthStore.setState({ user: { user_id: admin ? 1 : 3, username: "demo", email: "demo@example.com", role_id: admin ? 1 : 3, role_name: admin ? "admin" : "student", student_id: admin ? null : 7, teacher_id: null } });
  vi.spyOn(api, "get").mockImplementation(async path => ({ data: path === "/finance/accounts" ? [summary, { student_id: 8, student_name: "Eva Demo", enrollment_number: "EST-8", balance: 0, overdue_balance: 0 }] : String(path).endsWith("/options") ? { transfer_instructions: "", simulator_enabled: admin } : String(path).endsWith("/transfers") ? [{ transfer_request_id: 1, amount: 500, reference: "BANCO-1", bank: "Banco ficticio", status: "pending", submitted_at: "2026-10-12T12:00:00" }] : String(path).endsWith("/payment-plans") || String(path).endsWith("/history") || String(path).endsWith("/cash-closings") || String(path).endsWith("/billing-concepts") ? [] : summary } as never));
  const post = vi.spyOn(api, "post").mockImplementation(async path => ({ data: String(path).endsWith("/simulate") ? { outcome: "approved", balance_changed: false } : summary } as never));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[accounts ? "/finance" : admin ? "/finance/7" : "/my-finance"]}><Routes><Route path="/finance" element={<FinancePage />} /><Route path="/finance/:studentId" element={<FinancePage />} /><Route path="/my-finance" element={<FinancePage />} /></Routes></MemoryRouter></QueryClientProvider>);
  return post;
}
it("shows adjustments and hides administrative posting and simulation from students", async () => {
  setup();
  expect(await screen.findByRole("heading", { name: "Daniel Santos" })).toBeInTheDocument();
  expect(screen.getByText("Balance pendiente")).toBeInTheDocument();
  expect(screen.getByText("Matrícula")).toBeInTheDocument();
  expect(screen.getByText("Beca académica")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Registrar efectivo" })).not.toBeInTheDocument();
  expect(screen.queryByText("Simulador de pagos · sin dinero real")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Transferencias" }));
  expect(await screen.findByText("BANCO-1 · RD$500.00")).toBeInTheDocument();
  expect(screen.getByText(/No realices transferencias hasta recibirlas/)).toBeInTheDocument();
  expect(screen.getByText("Pendiente")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Revisar ingreso" })).not.toBeInTheDocument();
});
it("filters student accounts and leaves actions directly visible", async () => {
  setup(true, true);
  await screen.findByText("Daniel Santos");
  fireEvent.change(screen.getByLabelText("Buscar estudiante"), { target: { value: "Eva" } });
  expect(screen.getByText("Eva Demo")).toBeInTheDocument();
  expect(screen.queryByText("Daniel Santos")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Abrir" })).toHaveAttribute("href", "/finance/8");
});
it("requires reason and explicit verification before approving a transfer", async () => {
  const post = setup(true);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  await screen.findByRole("heading", { name: "Daniel Santos" });
  fireEvent.click(screen.getByRole("button", { name: "Transferencias" }));
  fireEvent.click(await screen.findByRole("button", { name: "Revisar ingreso" }));
  expect(screen.getByText(/Confirma el ingreso en el banco/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Motivo de la operación"), { target: { value: "Ingreso confirmado" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar dinero recibido" }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/finance/transfers/1/review", { reason: "Ingreso confirmado", approve: true }));
});
it("simulates a result without posting to the real payment endpoint", async () => {
  const post = setup(true);
  await screen.findByRole("heading", { name: "Daniel Santos" });
  fireEvent.click(await screen.findByText("Simulador de pagos · sin dinero real"));
  fireEvent.click(screen.getByRole("button", { name: "Ejecutar simulación" }));
  expect(await screen.findByText("SIMULACIÓN: aprobada. Balance sin cambios.")).toBeInTheDocument();
  expect(post).toHaveBeenCalledWith("/finance/students/7/simulate", { amount: "100", outcome: "approved" });
  expect(post.mock.calls.some(([path]) => String(path).endsWith("/payments"))).toBe(false);
});
