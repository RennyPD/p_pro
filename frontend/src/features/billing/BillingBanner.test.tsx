import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { BillingBanner } from "./BillingBanner";

function renderBanner(status: object, role: "admin" | "teacher" = "admin") {
  useAuthStore.setState({
    token: "t",
    user: {
      user_id: 1,
      username: role,
      email: `${role}@example.com`,
      role_id: 1,
      role_name: role,
      student_id: null,
      teacher_id: null,
    },
  });
  vi.spyOn(api, "get").mockImplementation(async url =>
    url === "/billing/status" ? ({ data: status } as never) : ({ data: {} } as never),
  );
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <BillingBanner />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BillingBanner", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("warns everyone in read-only mode and links managers to billing", async () => {
    renderBanner({ status: "read_only", read_only: true, days_left: 12 });
    expect(await screen.findByRole("alert")).toHaveTextContent("modo de solo lectura");
    expect(screen.getByText(/en 12 días, el acceso se suspenderá/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a Plan y facturación" })).toHaveAttribute(
      "href",
      "/billing",
    );
  });

  it("tells teachers about read-only mode without billing details", async () => {
    renderBanner({ status: "read_only", read_only: true, days_left: 12 }, "teacher");
    expect(await screen.findByRole("alert")).toHaveTextContent("modo de solo lectura");
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("reminds managers of the end of the trial", async () => {
    renderBanner({ status: "trialing", read_only: false, days_left: 3 });
    expect(await screen.findByText(/Tu prueba gratuita termina en 3 días/)).toBeInTheDocument();
  });

  it("stays quiet when the plan is paid", async () => {
    const { container } = renderBanner({ status: "active", read_only: false });
    await vi.waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
