import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { DemoBanner } from "./DemoBanner";
import { DemoPage } from "./DemoPage";

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/demo"]}>
        <Routes>
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/" element={<DemoBanner />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Demo", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    useAuthStore.getState().clearSession();
  });

  it("enters as a role with one click and reminds it is the demo", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: {
        enabled: true,
        roles: [
          { role: "admin", label: "Administración" },
          { role: "teacher", label: "Docente" },
        ],
      },
    });
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: { access_token: "demo-token", user: { user_id: 9, username: "profesor.01" } },
    });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Entrar como docente" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/public/demo/login", { role: "teacher" }),
    );
    expect(useAuthStore.getState().token).toBe("demo-token");
    expect(await screen.findByRole("note")).toHaveTextContent("Estás en la demo");
  });

  it("explains when the demo is closed", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: { enabled: false, roles: [] } });
    renderPage();
    expect(await screen.findByText(/no está disponible/)).toBeInTheDocument();
  });
});
