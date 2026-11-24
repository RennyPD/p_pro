import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { BillingPage } from "./BillingPage";
import { SandboxCheckoutPage } from "./SandboxCheckoutPage";

const plan = (code: string, name: string, students: number | null) => ({
  code,
  name,
  description: "Descripción",
  currency: "USD",
  monthly_price: "99.00",
  yearly_price: "990.00",
  max_students: students,
  max_staff: 30,
  storage_gb: 10,
});
const overview = (extra = {}) => ({
  plan: plan("basico", "Básico", 300),
  status: "trialing",
  interval: "monthly",
  trial_ends_at: "2026-12-25T00:00:00",
  current_period_end: null,
  provider: "sandbox",
  online_checkout: true,
  has_payment_method: false,
  students: { used: 270, limit: 300, ceiling: 330 },
  staff: { used: 5, limit: 30, ceiling: 33 },
  storage_gb: { used: 1.5, limit: 10, ceiling: 11 },
  plans: [plan("basico", "Básico", 300), plan("profesional", "Profesional", 1500)],
  ...extra,
});

function renderAt(path: string) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/billing" element={<BillingPage />} />
          <Route path="/billing/sandbox" element={<SandboxCheckoutPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Plan y facturación", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows the plan, its usage and starts a checkout", async () => {
    vi.spyOn(api, "get").mockImplementation(async url =>
      url === "/billing/subscription" ? ({ data: overview() } as never) : ({ data: [] } as never),
    );
    const post = vi
      .spyOn(api, "post")
      .mockResolvedValue({ data: { url: "/billing/sandbox?token=abc" } });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    renderAt("/billing");
    expect(await screen.findByRole("heading", { name: "Plan Básico" })).toBeInTheDocument();
    expect(screen.getByText("En prueba")).toBeInTheDocument();
    expect(screen.getByText("270 de 300")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Estudiantes activos" })).toHaveAttribute(
      "aria-valuenow",
      "90",
    );
    await userEvent.click(screen.getByRole("button", { name: "Anual" }));
    const card = screen.getByRole("article", { name: "Plan Profesional" });
    await userEvent.click(within(card).getByRole("button", { name: "Elegir Profesional" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/billing/checkout", {
        plan_code: "profesional",
        interval: "yearly",
      }),
    );
    expect(assign).toHaveBeenCalledWith("/billing/sandbox?token=abc");
    vi.unstubAllGlobals();
  });

  it("explains when online payment is not available yet", async () => {
    vi.spyOn(api, "get").mockImplementation(async url =>
      url === "/billing/subscription"
        ? ({ data: overview({ online_checkout: false, status: "active" }) } as never)
        : ({ data: [] } as never),
    );
    renderAt("/billing");
    expect(await screen.findByText(/El pago en línea aún no está disponible/)).toBeInTheDocument();
    const card = screen.getByRole("article", { name: "Plan Profesional" });
    expect(within(card).getByRole("button", { name: "Elegir Profesional" })).toBeDisabled();
  });

  it("simulates an approved payment and returns to the plan", async () => {
    vi.spyOn(api, "get").mockImplementation(async url =>
      url === "/billing/sandbox/session"
        ? ({
            data: { plan: plan("profesional", "Profesional", 1500), interval: "monthly" },
          } as never)
        : url === "/billing/subscription"
          ? ({ data: overview({ status: "active" }) } as never)
          : ({ data: [] } as never),
    );
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    renderAt("/billing/sandbox?token=abc");
    await userEvent.click(await screen.findByRole("button", { name: "Simular pago aprobado" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/billing/sandbox/complete", {
        token: "abc",
        outcome: "paid",
      }),
    );
    expect(await screen.findByText("Pago recibido. Tu plan ya está activo.")).toBeInTheDocument();
  });
});
