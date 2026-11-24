import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { OnlinePayDialog } from "./OnlinePayDialog";
import { OnlinePaymentResultPage } from "./OnlinePaymentPages";
import { goToGateway } from "./onlinePayments";

const children = [
  { student_id: 1, name: "Sofía García", balance: "2500.00" },
  { student_id: 2, name: "Luis García", balance: "800.00" },
];

describe("Pagos en línea", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("splits a card payment between children and opens the bank", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        id: "abc",
        redirect: { method: "GET", url: "/pagos/sandbox", fields: { id: "abc" } },
      },
    });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    render(<OnlinePayDialog students={children} minAmount="100.00" onClose={() => {}} />);
    const luis = screen.getByLabelText(/Luis García/);
    await userEvent.clear(luis);
    await userEvent.type(luis, "300");
    expect(screen.getByText(/Total/)).toHaveTextContent("2,800.00");
    await userEvent.click(screen.getByRole("button", { name: /Continuar al pago/ }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/online-payments", {
        allocations: [
          { student_id: 1, amount: "2500.00" },
          { student_id: 2, amount: "300.00" },
        ],
      }),
    );
    expect(assign).toHaveBeenCalledWith("/pagos/sandbox?id=abc");
  });

  it("posts a form to banks that receive one", () => {
    const submit = vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(() => {});
    goToGateway({
      method: "POST",
      url: "https://pruebas.azul.com.do/PaymentPage/",
      fields: { MerchantId: "390", AuthHash: "x" },
    });
    const form = document.querySelector("form") as HTMLFormElement;
    expect(form.action).toBe("https://pruebas.azul.com.do/PaymentPage/");
    expect(form.method).toBe("post");
    expect(new FormData(form).get("AuthHash")).toBe("x");
    expect(submit).toHaveBeenCalled();
    form.remove();
  });

  it("confirms the bank's answer and shows the receipt", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        id: "abc",
        status: "approved",
        amount: "1000.00",
        currency: "DOP",
        gateway: "azul",
        authorization_code: "OK1234",
        message: "APROBADA",
        receipts: ["REC-2026-00000042"],
      },
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/pagos/resultado?id=abc&IsoCode=00&AuthHash=f00"]}>
          <Routes>
            <Route path="/pagos/resultado" element={<OnlinePaymentResultPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Pago aprobado" })).toBeInTheDocument();
    expect(screen.getByText("Recibo: REC-2026-00000042")).toBeInTheDocument();
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith("/online-payments/abc/complete", {
      params: { id: "abc", IsoCode: "00", AuthHash: "f00" },
    });
  });
});
