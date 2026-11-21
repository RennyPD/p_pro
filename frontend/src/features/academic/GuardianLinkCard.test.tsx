import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { GuardianLinkCard, type GuardianLink } from "./GuardianLinkCard";

const link: GuardianLink = {
  student_guardian_id: 4,
  student_id: 1,
  guardian_id: 2,
  relationship: "Madre",
  guardian_name: "Rosa Tutora",
  guardian_email: "rosa@example.com",
  primary_contact: true,
  emergency_contact: false,
  authorized_pickup: false,
  can_view_academic: true,
  can_view_attendance: true,
  can_view_finance: true,
  can_view_tasks: true,
  financial_responsible: false,
};

function renderCard(value: GuardianLink, canManage = true) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <GuardianLinkCard link={value} studentId={1} canManage={canManage} />
    </QueryClientProvider>,
  );
}

describe("GuardianLinkCard", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows that the guardian sees everything by default", () => {
    renderCard(link);
    expect(screen.getByText("Ve toda la información")).toBeInTheDocument();
  });

  it("lists restricted areas and hides the editor without permission", () => {
    renderCard({ ...link, can_view_finance: false }, false);
    expect(screen.getByText("Sin acceso a: finanzas")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Accesos/ })).not.toBeInTheDocument();
  });

  it("saves the guardian's access for this link", async () => {
    const patch = vi.spyOn(api, "patch").mockResolvedValue({ data: link } as never);
    renderCard(link);
    fireEvent.click(screen.getByRole("button", { name: /Accesos/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Finanzas/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Responsable de pago/ }));
    fireEvent.click(screen.getByRole("button", { name: "Guardar accesos" }));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith("/community/guardian-links/4", {
        can_view_academic: true,
        can_view_attendance: true,
        can_view_finance: false,
        can_view_tasks: true,
        financial_responsible: true,
      }),
    );
  });
});
