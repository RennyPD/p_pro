import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { SchoolYearsPanel } from "./SchoolYearsPanel";

vi.mock("../../lib/permissions", () => ({
  useAccess: () => ({ can: () => true }),
}));

const year = {
  school_year_id: 3,
  name: "2026-2027",
  start_date: "2026-08-17",
  end_date: "2027-06-18",
  period_scheme: "quarters",
  period_count: 0,
};

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SchoolYearsPanel />
    </QueryClientProvider>,
  );
}

describe("SchoolYearsPanel", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(cleanup);

  it("generates the periods of a year without periods", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [year] });
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: [{}, {}, {}, {}] });
    renderPanel();
    expect(await screen.findByText("4 períodos (MINERD)")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Generar períodos de 2026-2027" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/school-years/3/generate-periods"));
  });

  it("creates a year with the institution's default scheme", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [{ ...year, period_count: 4 }] });
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: year });
    renderPanel();
    expect(await screen.findByText("4 períodos")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generar períodos/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Nuevo año/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "2027-2028");
    await userEvent.type(screen.getByLabelText("Inicio"), "2027-08-16");
    await userEvent.type(screen.getByLabelText("Fin"), "2028-06-16");
    await userEvent.click(screen.getByRole("button", { name: "Crear año" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/school-years/", {
        name: "2027-2028",
        start_date: "2027-08-16",
        end_date: "2028-06-16",
        period_scheme: null,
      }),
    );
  });
});
