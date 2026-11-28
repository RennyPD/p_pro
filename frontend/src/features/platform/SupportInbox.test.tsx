import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { platformApi } from "../../lib/platformApi";
import { SupportInbox } from "./SupportInbox";

const ticket = {
  support_ticket_id: 7,
  subject: "No veo la sección",
  category: "uso",
  priority: "alta",
  status: "open",
  requester_name: "Ana Pérez",
  requester_email: "ana@liceo.edu.do",
  institution: "Liceo Horizonte",
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
  ],
};

describe("SupportInbox", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("lists open tickets and answers one with a new status", async () => {
    const get = vi
      .spyOn(platformApi, "get")
      .mockImplementation(async url =>
        url === "/platform/support" ? ({ data: [ticket] } as never) : ({ data: ticket } as never),
      );
    const post = vi.spyOn(platformApi, "post").mockResolvedValue({ data: ticket });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SupportInbox />
      </QueryClientProvider>,
    );
    expect(get).toHaveBeenCalledWith("/platform/support", { params: { status: "open" } });
    await userEvent.click(await screen.findByRole("button", { name: /No veo la sección/ }));
    const dialog = await screen.findByRole("dialog");
    expect(await screen.findByText("Desde ayer no aparece.")).toBeInTheDocument();
    expect(dialog).toHaveTextContent("ana@liceo.edu.do");
    await userEvent.type(screen.getByLabelText(/Respuesta/), "Ya está.");
    await userEvent.click(screen.getByRole("button", { name: "Responder" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/platform/support/7/reply", {
        body: "Ya está.",
        status: "waiting",
      }),
    );
  });
});
