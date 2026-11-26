import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { LegalGate } from "./LegalGate";
import { LegalText } from "./LegalText";

describe("Documentos legales", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders headings, lists, tables and bold without raw HTML", () => {
    render(
      <LegalText
        text={[
          "# Política",
          "**BORRADOR** para revisión.",
          "## Datos",
          "- uno",
          "- dos <script>",
          "| Nombre | Para qué |",
          "|---|---|",
          "| Sesión | Iniciar sesión |",
        ].join("\n")}
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Política" })).toBeInTheDocument();
    expect(screen.getByText("BORRADOR").tagName).toBe("STRONG");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("dos <script>")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Iniciar sesión" })).toBeInTheDocument();
  });

  it("asks the administrator to accept pending documents", async () => {
    vi.spyOn(api, "get").mockImplementation(async url =>
      url === "/legal/pending"
        ? ({
            data: {
              documents: [
                {
                  kind: "dpa",
                  title: "Acuerdo de tratamiento de datos",
                  version: "2026-11-26",
                  slug: "tratamiento-de-datos",
                },
              ],
            },
          } as never)
        : ({
            data: {
              kind: "dpa",
              title: "Acuerdo de tratamiento de datos",
              version: "2026-11-26",
              slug: "tratamiento-de-datos",
              text: "# Acuerdo\nTexto.",
            },
          } as never),
    );
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: { documents: [] } });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <LegalGate />
      </QueryClientProvider>,
    );
    const accept = await screen.findByRole("button", { name: "Aceptar y continuar" });
    expect(accept).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(accept);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/legal/accept", { kinds: ["dpa"] }));
  });
});
