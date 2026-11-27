import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { HelpPage } from "./HelpPage";

const guides = [
  { slug: "primeros-pasos", title: "Primeros pasos", summary: "x", audience: ["admin"] },
  { slug: "docentes", title: "Guía para docentes", summary: "x", audience: ["teacher"] },
  {
    slug: "seguridad-de-la-cuenta",
    title: "Seguridad de tu cuenta",
    summary: "x",
    audience: ["all"],
  },
];

function renderAt(path: string) {
  vi.spyOn(api, "get").mockImplementation(async url =>
    url === "/public/help"
      ? ({ data: guides } as never)
      : ({ data: { ...guides[1], text: "# Guía para docentes\nPase de lista." } } as never),
  );
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/help" element={<HelpPage base="/help" />} />
          <Route path="/help/:slug" element={<HelpPage base="/help" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Centro de ayuda", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    useAuthStore.getState().clearSession();
  });

  it("lists first the guides of the reader's role", async () => {
    useAuthStore.setState({
      token: "t",
      user: {
        user_id: 2,
        username: "profesor.01",
        email: "p@b.do",
        role_id: 2,
        role_name: "teacher",
        student_id: null,
        teacher_id: 1,
      },
    });
    renderAt("/help");
    const index = await screen.findByRole("navigation", { name: "Guías" });
    const lists = await within(index).findAllByRole("list");
    expect(within(lists[0]).getByText("Guía para docentes")).toBeInTheDocument();
    expect(within(lists[0]).getByText("Seguridad de tu cuenta")).toBeInTheDocument();
    expect(within(lists[1]).getByText("Primeros pasos")).toBeInTheDocument();
  });

  it("shows a guide", async () => {
    renderAt("/help/docentes");
    expect(await screen.findByText("Pase de lista.")).toBeInTheDocument();
  });
});
