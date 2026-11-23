import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { GradingScalesPage } from "./GradingScalesPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const letter = {
  name: "Letras A–F con índice 4.0",
  kind: "letter",
  passing_value: 70,
  decimals: 0,
  completivo_average_weight: 50,
  extraordinario_average_weight: 30,
  bands: [
    { label: "F", min_value: 0, max_value: 70, stored_value: 60, points: 0 },
    { label: "A", min_value: 70, max_value: 100, stored_value: 95, points: 4 },
  ],
};
const saved = {
  ...letter,
  grading_scale_id: 4,
  name: "Numérica 0–100",
  kind: "numeric",
  is_default: true,
  program_count: 3,
  bands: [],
};

function renderPage() {
  vi.spyOn(api, "get").mockImplementation(url =>
    Promise.resolve({
      data: url === "/grading-scales/presets" ? [{ key: "letter", scale: letter }] : [saved],
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <GradingScalesPage />
    </QueryClientProvider>,
  );
}

describe("GradingScalesPage", () => {
  it("lists the default scale and creates one from a preset with a live preview", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: saved });
    renderPage();
    expect(await screen.findByText("Numérica 0–100")).toBeInTheDocument();
    expect(screen.getByText("Predeterminada")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Hacer predeterminada/ })).toBeNull();
    await userEvent.click(await screen.findByRole("button", { name: /Letras/ }));
    const dialog = screen.getByRole("dialog");
    const preview = within(dialog).getByRole("spinbutton", { name: /Vista previa/ });
    expect(within(dialog).getByText("A")).toBeInTheDocument();
    await userEvent.clear(preview);
    await userEvent.type(preview, "65");
    expect(within(dialog).getByText(/no aprueba/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Guardar escala" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        "/grading-scales/",
        expect.objectContaining({
          kind: "letter",
          passing_value: 70,
          bands: [
            expect.objectContaining({ label: "F", min_value: 0, max_value: 70, points: 0 }),
            expect.objectContaining({ label: "A", stored_value: 95 }),
          ],
        }),
      ),
    );
  });
});
