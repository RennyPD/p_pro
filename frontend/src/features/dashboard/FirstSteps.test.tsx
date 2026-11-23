import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { FirstSteps } from "./FirstSteps";

const step = (key: string, done: boolean) => ({
  key,
  label: `Paso ${key}`,
  description: "Descripción",
  done,
  to: `/${key}`,
});

function renderCard() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <FirstSteps />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("FirstSteps", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("links the pending steps and shows the progress", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      data: { steps: [step("periods", true), step("students", false)], completed: 1, total: 2 },
    });
    renderCard();
    expect(await screen.findByText("1 de 2 completados")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Paso students" })).toHaveAttribute(
      "href",
      "/students",
    );
    expect(screen.queryByRole("link", { name: "Paso periods" })).toBeNull();
  });

  it("disappears once everything is set up", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({
      data: { steps: [step("periods", true)], completed: 1, total: 1 },
    });
    const { container } = renderCard();
    await vi.waitFor(() => expect(get).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
