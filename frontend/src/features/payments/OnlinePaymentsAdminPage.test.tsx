import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { OnlinePaymentsAdminPage } from "./OnlinePaymentsAdminPage";

const row = (id: string, status: string) => ({
  id,
  status,
  amount: "700.00",
  gateway: "azul",
  authorization_code: status === "approved" ? "OK1" : null,
  message: null,
  receipts: status === "approved" ? ["REC-1"] : [],
  created_at: "2026-11-26T14:00:00",
  payer: "rosa.pena",
  students: [{ student_id: 1, name: "Sofía García", amount: "700.00" }],
  provider_reference: null,
  overpaid: false,
});
const config = {
  enabled: true,
  gateway: "azul",
  merchant_id: "390",
  merchant_name: "Colegio",
  min_amount: "100.00",
  environment: "test",
  auth_key: "••••1234",
  terminal: "",
  merchant_type: "",
  gateways: ["azul", "cardnet", "sandbox"],
};

function renderPage() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <OnlinePaymentsAdminPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Pagos en línea (finanzas)", () => {
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
      url === "/online-payments/config/gateway"
        ? ({ data: config } as never)
        : ({
            data: [row("aaaaaaaaaaaaaaaaaaaa", "expired"), row("bbbbbbbbbbbbbbbbbbbb", "approved")],
            headers: { "x-total-count": "2" },
          } as never),
    );
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("resolves a payment the bank never answered with its authorization code", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    renderPage();
    expect(await screen.findByText("REC-1")).toBeInTheDocument();
    const pending = screen
      .getAllByRole("row")
      .find(item => within(item).queryByText("Sin respuesta")) as HTMLElement;
    await userEvent.click(within(pending).getByRole("button", { name: "Resolver" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Código de autorización"), "AZ99");
    await userEvent.type(within(dialog).getByLabelText("Motivo"), "Visto en el portal");
    await userEvent.click(within(dialog).getByRole("button", { name: "Guardar resultado" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/online-payments/aaaaaaaaaaaaaaaaaaaa/resolve", {
        outcome: "approved",
        authorization_code: "AZ99",
        reason: "Visto en el portal",
      }),
    );
  });

  it("saves the gateway without resending stored keys", async () => {
    const put = vi.spyOn(api, "put").mockResolvedValue({ data: config });
    renderPage();
    expect(await screen.findByText(/guardada: ••••1234/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Guardar pasarela" }));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith(
        "/online-payments/config/gateway",
        expect.objectContaining({ gateway: "azul", merchant_id: "390", auth_key: null }),
      ),
    );
  });
});
