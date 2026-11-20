import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { BillingPlansPage } from "./BillingPlansPage";
import { cycleLabel } from "./billingCycles";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const plan = {
  billing_plan_id: 3,
  name: "Mensualidad 2026-2027",
  charge_description: "Mensualidad",
  billing_concept_id: null,
  amount: "8500.00",
  frequency: "monthly",
  start_month: "2026-08",
  end_month: "2026-10",
  due_day: 5,
  period_id: null,
  active: true,
  targets: { career_ids: [1], student_ids: [], excluded_student_ids: [] },
  cycles: ["2026-08", "2026-09", "2026-10"],
  generated_cycles: ["2026-08"],
  next_cycle: "2026-09",
};

function renderPage() {
  useAuthStore.setState({
    user: {
      user_id: 1,
      username: "demo",
      email: "demo@example.com",
      role_id: 1,
      role_name: "admin",
      student_id: null,
      teacher_id: null,
    },
  });
  vi.spyOn(api, "get").mockImplementation(
    async path =>
      ({
        data:
          path === "/finance/billing-plans"
            ? [plan]
            : String(path).startsWith("/careers")
              ? [{ career_id: 1, code: "ING", name: "Ingeniería" }]
              : [],
        headers: {},
      }) as never,
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BillingPlansPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it("labels cycles in Spanish", () => {
  expect(cycleLabel("2026-08")).toBe("ago 2026");
  expect(cycleLabel("2026-12", true)).toBe("diciembre 2026");
});

it("shows plan progress and generates the next month after the preview", async () => {
  const post = vi.spyOn(api, "post").mockImplementation(
    async path =>
      ({
        data: String(path).endsWith("/preview")
          ? {
              cycle: "2026-09",
              cycle_label: "septiembre 2026",
              due_date: "2026-09-05",
              amount: "8500.00",
              charge_description: "Mensualidad · septiembre 2026",
              to_charge: 2,
              already_charged: 0,
              total: "17000.00",
              with_payment_plan: 1,
              students: [
                {
                  student_id: 7,
                  enrollment_number: "M-7",
                  student_name: "Ana Pérez",
                  has_payment_plan: true,
                },
                {
                  student_id: 8,
                  enrollment_number: "M-8",
                  student_name: "Luis Gómez",
                  has_payment_plan: false,
                },
              ],
            }
          : { charge_count: 2, total: "17000.00" },
      }) as never,
  );
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();
  expect(await screen.findByText("Mensualidad 2026-2027")).toBeInTheDocument();
  expect(screen.getByText("1 de 3 meses generados")).toBeInTheDocument();
  expect(await screen.findByText("Ingeniería")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Generar cargos" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByLabelText("Mes a cobrar")).toHaveValue("2026-09");
  expect(await within(dialog).findByText("Ana Pérez")).toBeInTheDocument();
  expect(within(dialog).getByText(/con plan de pago activo/)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: "Generar 2 cargos" }));
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith(
      "/finance/billing-plans/3/runs",
      expect.objectContaining({ cycle: "2026-09", idempotency_key: expect.any(String) }),
    ),
  );
});

it("creates a plan for the chosen careers", async () => {
  const post = vi.spyOn(api, "post").mockResolvedValue({ data: plan } as never);
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Nuevo plan" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Nombre del plan"), {
    target: { value: "Mensualidad 2027" },
  });
  fireEvent.change(within(dialog).getByLabelText("Texto del cargo"), {
    target: { value: "Mensualidad" },
  });
  fireEvent.change(within(dialog).getByLabelText("Monto RD$"), { target: { value: "9000" } });
  fireEvent.change(within(dialog).getByLabelText("Primer mes"), { target: { value: "2027-01" } });
  fireEvent.change(within(dialog).getByLabelText("Último mes"), { target: { value: "2027-06" } });
  fireEvent.click(await within(dialog).findByRole("checkbox", { name: /Ingeniería/ }));
  fireEvent.click(within(dialog).getByRole("button", { name: "Crear plan" }));
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith(
      "/finance/billing-plans",
      expect.objectContaining({
        name: "Mensualidad 2027",
        amount: "9000",
        start_month: "2027-01",
        end_month: "2027-06",
        targets: { career_ids: [1], student_ids: [], excluded_student_ids: [] },
      }),
    ),
  );
});
