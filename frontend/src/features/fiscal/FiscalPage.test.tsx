import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { FiscalPage } from "./FiscalPage";

const profile = {
  enabled: true,
  mode: "ncf",
  rnc: "131012345",
  legal_name: "Instituto Técnico Horizonte, SRL",
  trade_name: "",
  fiscal_address: "Santo Domingo",
  issue_on: "payment",
  doc_types: { B01: "Factura de crédito fiscal", B02: "Factura de consumo" },
};

function renderPage() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <FiscalPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Comprobantes fiscales", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "t",
      user: {
        user_id: 1,
        username: "admin",
        email: "a@b.do",
        role_id: 1,
        role_name: "admin",
        student_id: null,
        teacher_id: null,
      },
    });
    vi.spyOn(api, "get").mockImplementation(async url =>
      url === "/fiscal/profile"
        ? ({ data: profile } as never)
        : url === "/fiscal/sequences"
          ? ({
              data: {
                sequences: [
                  {
                    fiscal_sequence_id: 1,
                    doc_type: "B02",
                    label: "Factura de consumo",
                    range_start: 1,
                    range_end: 100,
                    next_number: 96,
                    remaining: 5,
                    expires_on: "2027-12-31",
                    active: true,
                  },
                ],
                alerts: [{ fiscal_sequence_id: 1, kind: "low", message: "Quedan 5 números B02" }],
              },
            } as never)
          : ({
              data: [
                {
                  fiscal_document_id: 7,
                  doc_type: "B02",
                  label: "Factura de consumo",
                  ncf: "B0200000095",
                  status: "issued",
                  issued_at: "2026-11-26T15:00:00",
                  buyer_name: "Sofía García",
                  buyer_tax_id: "",
                  itbis: "180.00",
                  total: "3180.00",
                },
              ],
              headers: { "x-total-count": "1" },
            } as never),
    );
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("warns about low ranges and registers a new DGII range", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    renderPage();
    expect(await screen.findByText("Quedan 5 números B02")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Desde"), "101");
    await userEvent.type(screen.getByLabelText("Hasta"), "600");
    await userEvent.click(screen.getByRole("button", { name: "Registrar secuencia" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/fiscal/sequences", {
        doc_type: "B02",
        range_start: 101,
        range_end: 600,
        expires_on: null,
      }),
    );
  });

  it("voids a receipt with a DGII reason", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    renderPage();
    const row = (await screen.findByText("B0200000095")).closest("tr") as HTMLElement;
    expect(within(row).getByText("Consumidor final")).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: "Anular" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Detalle"), "Cliente equivocado");
    await userEvent.click(within(dialog).getByRole("button", { name: "Anular comprobante" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/fiscal/documents/7/void", {
        reason: "04",
        note: "Cliente equivocado",
      }),
    );
  });
});
