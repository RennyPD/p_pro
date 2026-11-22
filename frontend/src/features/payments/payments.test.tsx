import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { AccountView } from "./AccountView";
import { FamilyPayments } from "./FamilyPayments";
import { groupTransfers, type InboxItem } from "./paymentsData";
import { TransferInbox } from "./TransferInbox";

const statement = {
  student_id: 7,
  student_name: "Daniel Santos",
  enrollment_number: "EST-7",
  balance: 1500,
  overdue_balance: 500,
  next_due_date: "2026-12-30",
  next_due_amount: 1000,
  obligations: [
    {
      type: "charge",
      obligation_id: 1,
      concept: "Mensualidad",
      description: "Septiembre",
      due_date: "2026-09-30",
      amount: 1000,
      paid_amount: 1000,
      remaining: 0,
      status: "paid",
    },
    {
      type: "charge",
      obligation_id: 2,
      concept: "Mensualidad",
      description: "Octubre",
      due_date: "2026-10-30",
      amount: 1000,
      paid_amount: 500,
      remaining: 500,
      status: "overdue",
    },
    {
      type: "charge",
      obligation_id: 3,
      concept: "Mensualidad",
      description: "Diciembre",
      due_date: "2026-12-30",
      amount: 1000,
      paid_amount: 0,
      remaining: 1000,
      status: "pending",
    },
  ],
  concepts: [],
  payments: [
    {
      payment_id: 9,
      amount: 1500,
      reference: "CAJA-1",
      method: "cash",
      paid_at: "2026-09-20T10:00:00",
      receipt_number: "REC-2026-00000009",
    },
  ],
  payment_plans: [],
};

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

function mockGet(routes: Record<string, unknown>) {
  return vi.spyOn(api, "get").mockImplementation((url: string) => {
    const key = Object.keys(routes).find(path => url.endsWith(path));
    return Promise.resolve({ data: key ? routes[key] : [], headers: {} });
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AccountView", () => {
  it("puts what to pay first and lists unpaid installments with their status", async () => {
    mockGet({
      "/statement": statement,
      "/transfers": [],
      "/finance/options": { transfer_instructions: "Banco ficticio 123", simulator_enabled: false },
    });
    wrap(<AccountView studentId={7} statementPath="/finance/students/7/statement" />);
    expect(await screen.findByText("Pagar ahora")).toBeInTheDocument();
    const installments = screen.getByRole("region", { name: "Cuotas" });
    expect(within(installments).getByText("Vencida")).toBeInTheDocument();
    expect(within(installments).queryByText("Septiembre")).not.toBeInTheDocument();
    fireEvent.click(within(installments).getByRole("button", { name: "Ver pagadas" }));
    expect(within(installments).getByText("Pagada")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Recibo del pago/ })).toBeInTheDocument();
  });

  it("reports a transfer with the overdue amount suggested", async () => {
    mockGet({
      "/statement": statement,
      "/transfers": [],
      "/finance/options": { transfer_instructions: "Banco ficticio 123", simulator_enabled: false },
    });
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} } as never);
    wrap(<AccountView studentId={7} statementPath="/finance/students/7/statement" />);
    fireEvent.click(await screen.findByRole("button", { name: /Reportar pago/ }));
    expect(screen.getByLabelText(/Monto transferido/)).toHaveValue("500.00");
    fireEvent.change(screen.getByLabelText("Número de referencia"), { target: { value: "TRF-1" } });
    fireEvent.change(screen.getByLabelText("Banco de origen"), { target: { value: "Banco" } });
    const file = new File(["%PDF-1.4"], "comprobante.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText(/Comprobante/), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar reporte" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/finance/students/7/transfers",
        expect.objectContaining({ amount: "500.00", reference: "TRF-1", bank: "Banco" }),
      ),
    );
  });
});

describe("FamilyPayments", () => {
  const family = {
    total_balance: 2700,
    total_overdue: 1300,
    next_due_date: "2026-12-30",
    students: [
      {
        student_id: 1,
        student_name: "Sofía García",
        enrollment_number: "E-1",
        balance: 1500,
        overdue_balance: 500,
        next_due_date: null,
        next_due_amount: null,
        financial_responsible: true,
      },
      {
        student_id: 2,
        student_name: "Mateo García",
        enrollment_number: "E-2",
        balance: 1200,
        overdue_balance: 800,
        next_due_date: null,
        next_due_amount: null,
        financial_responsible: false,
      },
    ],
    concepts: [
      {
        concept: "Mensualidad",
        remaining: 2700,
        students: [
          { student_id: 1, remaining: 1500 },
          { student_id: 2, remaining: 1200 },
        ],
      },
    ],
  };

  it("suggests a split and sends one transfer for both children", async () => {
    mockGet({
      "/guardian/finance": family,
      "/guardian/transfers": [],
      "/finance/options": { transfer_instructions: "Banco ficticio 123", simulator_enabled: false },
      "/guardian/finance/allocation": [
        { student_id: 1, amount: 500 },
        { student_id: 2, amount: 800 },
      ],
    });
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} } as never);
    wrap(<FamilyPayments />);
    expect(await screen.findByText("Total de la familia")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pagar a varios hijos" }));
    fireEvent.click(screen.getByRole("button", { name: "Sugerir reparto" }));
    await waitFor(() => expect(screen.getByLabelText(/Sofía García/)).toHaveValue("500.00"));
    expect(screen.getByLabelText(/Mateo García/)).toHaveValue("800.00");
    fireEvent.change(screen.getByLabelText("Número de referencia"), {
      target: { value: "LOTE-1" },
    });
    fireEvent.change(screen.getByLabelText("Banco de origen"), { target: { value: "Banco" } });
    const file = new File(["%PDF-1.4"], "c.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText(/Comprobante/), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar pago familiar" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/guardian/transfers",
        expect.objectContaining({
          reference: "LOTE-1",
          allocations: [
            { student_id: 1, amount: "500.00" },
            { student_id: 2, amount: "800.00" },
          ],
        }),
      ),
    );
  });
});

describe("TransferInbox", () => {
  const item = (id: number, batch: number | null, name: string): InboxItem => ({
    transfer_request_id: id,
    student_id: id,
    reference: batch ? `LOTE (${id}/2)` : `TRF-${id}`,
    bank: "Banco",
    note: "",
    status: "pending",
    submitted_at: "2026-11-22T10:00:00Z",
    reviewed_at: null,
    review_reason: null,
    payment_id: null,
    amount: 100,
    batch_id: batch,
    batch_reference: batch ? "LOTE" : null,
    batch_total: batch ? 200 : null,
    batch_size: batch ? 2 : null,
    student_name: name,
    enrollment_number: `E-${id}`,
  });

  it("groups the shares of a family transfer", () => {
    const groups = groupTransfers([item(1, 5, "Sofía"), item(2, 5, "Mateo"), item(3, null, "Eva")]);
    expect(groups.map(group => group.items.length)).toEqual([2, 1]);
    expect(groups[0].batch).toBe(true);
  });

  it("approves a family transfer as a whole from the cashier inbox", async () => {
    mockGet({ "/finance/transfers": [item(1, 5, "Sofía"), item(2, 5, "Mateo")] });
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} } as never);
    wrap(<TransferInbox />);
    fireEvent.click(await screen.findByRole("button", { name: "Revisar" }));
    expect(screen.getByText(/se aprueba o rechaza completa/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: "Depósito verificado" } });
    fireEvent.click(screen.getByRole("button", { name: "Aprobar" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/finance/transfers/1/review", {
        approve: true,
        reason: "Depósito verificado",
      }),
    );
  });
});
