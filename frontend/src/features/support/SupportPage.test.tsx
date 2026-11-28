import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { SupportPage } from "./SupportPage";

const ticket = {
  support_ticket_id: 7,
  subject: "No veo la sección",
  category: "uso",
  priority: "alta",
  status: "waiting",
  requester_name: "Ana Pérez",
  created_at: "2026-11-28T10:00:00",
  updated_at: "2026-11-28T11:00:00",
  messages: [
    {
      support_message_id: 1,
      author_kind: "institution",
      author_name: "Ana Pérez",
      body: "Desde ayer no aparece.",
      created_at: "2026-11-28T10:00:00",
    },
    {
      support_message_id: 2,
      author_kind: "platform",
      author_name: "Equipo de Nexo",
      body: "Estaba en otro período.",
      created_at: "2026-11-28T11:00:00",
    },
  ],
};

function renderAt(path: string) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/support" element={<SupportPage />} />
          <Route path="/support/:ticketId" element={<SupportPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Soporte", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("opens a ticket and shows its thread", async () => {
    vi.spyOn(api, "get").mockImplementation(async url =>
      url === "/support/tickets" ? ({ data: [] } as never) : ({ data: ticket } as never),
    );
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: ticket });
    renderAt("/support");
    expect(await screen.findByText("Sin tickets")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Asunto"), "No veo la sección");
    await userEvent.selectOptions(screen.getByLabelText("Prioridad"), "alta");
    await userEvent.type(screen.getByLabelText("Cuéntanos qué pasa"), "Desde ayer no aparece.");
    await userEvent.click(screen.getByRole("button", { name: "Enviar a soporte" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/support/tickets", {
        subject: "No veo la sección",
        category: "uso",
        priority: "alta",
        body: "Desde ayer no aparece.",
      }),
    );
    expect(await screen.findByText("Estaba en otro período.")).toBeInTheDocument();
    expect(screen.getByText("Esperando tu respuesta")).toBeInTheDocument();
  });

  it("replies on an open ticket but not on a closed one", async () => {
    let current = ticket;
    vi.spyOn(api, "get").mockImplementation(async () => ({ data: current }) as never);
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: ticket });
    const view = renderAt("/support/7");
    await userEvent.type(await screen.findByLabelText("Responder"), "¡Gracias!");
    await userEvent.click(screen.getByRole("button", { name: "Enviar respuesta" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/support/tickets/7/messages", { body: "¡Gracias!" }),
    );
    view.unmount();
    current = { ...ticket, status: "closed" };
    renderAt("/support/7");
    expect(await screen.findByText("Cerrado")).toBeInTheDocument();
    expect(screen.queryByLabelText("Responder")).not.toBeInTheDocument();
  });
});
