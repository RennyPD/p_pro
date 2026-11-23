import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { FinancePolicyPage } from "./FinancePolicyPage";
import { FinanceReportsPage } from "./FinanceReportsPage";
import { RecordMovementPanel } from "./RecordMovementPanel";

vi.mock("../../lib/permissions", () => ({
  useAccess: () => ({ can: () => true }),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function wrap(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const policy = {
  late_fee_enabled: false,
  grace_days: 5,
  late_fee_kind: "percent",
  late_fee_value: 5,
  hold_enabled: false,
  hold_after_days: 30,
  hold_min_amount: 0,
  sibling_discount_enabled: false,
  sibling_second_percent: 10,
  sibling_third_percent: 15,
  auto_billing_enabled: false,
  billing_lead_days: 10,
};

describe("school finance", () => {
  it("saves the policy with a reason and simulates the daily job", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: policy });
    const put = vi.spyOn(api, "put").mockResolvedValue({ data: policy });
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        today: "2026-11-23",
        simulated: true,
        billing_runs: [],
        sibling_discounts: 0,
        late_fees: [{ student: "Ana", charge: "Mensualidad", amount: "250.00" }],
        holds_set: ["Ana Díaz"],
        holds_lifted: [],
      },
    });
    wrap(<FinancePolicyPage />);
    await userEvent.click(await screen.findByLabelText("Aplicar recargo a cuotas vencidas"));
    const save = screen.getByRole("button", { name: /Guardar política/ });
    expect(save).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Motivo del cambio"), "Reglamento 2026");
    await userEvent.click(save);
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith(
        "/finance/policy",
        expect.objectContaining({ late_fee_enabled: true, reason: "Reglamento 2026" }),
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: /Simular hoy/ }));
    expect(post).toHaveBeenCalledWith("/finance/automation/simulate");
    const result = await screen.findByRole("status");
    expect(within(result).getByText("1 recargos por mora")).toBeInTheDocument();
    expect(within(result).getByText(/1 bloqueos: Ana Díaz/)).toBeInTheDocument();
  });

  it("shows aging buckets, the overdue accounts and the cashier's day", async () => {
    vi.spyOn(api, "get").mockImplementation(url => {
      const data: Record<string, unknown> = {
        "/finance/cashier/today": {
          day: "2026-11-23",
          payments: 2,
          total: 3000,
          by_method: { Efectivo: 3000 },
        },
        "/finance/reports/aging": {
          as_of: "2026-11-23",
          totals: { current: 0, d1_30: 5000, d31_60: 0, d61_90: 0, d90_plus: 15000, total: 20000 },
          students_overdue: 3,
          groups: [
            {
              label: "1.º A · Secundaria",
              students: 3,
              current: 0,
              d1_30: 5000,
              d31_60: 0,
              d61_90: 0,
              d90_plus: 15000,
              total: 20000,
            },
          ],
        },
      };
      if (url === "/finance/reports/aging/accounts")
        return Promise.resolve({
          data: [
            {
              student_id: 9,
              student_name: "Ana Díaz",
              enrollment_number: "ESC-009",
              group: "1.º A · Secundaria",
              family: "Familia Rosa Peña",
              financial_hold: true,
              oldest_due: "2026-08-05",
              current: 0,
              d1_30: 0,
              d31_60: 0,
              d61_90: 0,
              d90_plus: 5000,
              total: 5000,
            },
          ],
          headers: { "x-total-count": "1" },
        });
      return Promise.resolve({ data: data[url as string] ?? [] });
    });
    wrap(<FinanceReportsPage />);
    expect(await screen.findByText("Mi caja de hoy")).toBeInTheDocument();
    expect(await screen.findByText("3 estudiantes con atraso")).toBeInTheDocument();
    expect(screen.getAllByText("1.º A · Secundaria").length).toBeGreaterThan(0);
    expect(await screen.findByRole("link", { name: "Ana Díaz" })).toHaveAttribute(
      "href",
      "/finance/9",
    );
    expect(screen.getByText("Bloqueado")).toBeInTheDocument();
  });

  it("lets a cashier record payments but not charges or adjustments", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [] });
    wrap(
      <RecordMovementPanel
        studentId={1}
        dueDay={5}
        balance={500}
        canCollect
        canSupervise={false}
      />,
    );
    expect(screen.getByRole("heading", { name: "Efectivo recibido" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Nuevo cargo" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Becas y ajustes" })).toBeNull();
  });
});
