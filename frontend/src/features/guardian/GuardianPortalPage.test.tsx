import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { GuardianPortalPage } from "./GuardianPortalPage";

describe("GuardianPortalPage", () => {
  afterEach(() => vi.restoreAllMocks());
  it("shows the linked student's academic and financial summary", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [{ student_id: 1, student_name: "Sofía García", enrollment_number: "ITH-2026-001", career_name: "Desarrollo de Software", active: true, average_grade: 88.5, attendance_percentage: 94, balance: 1250, schedule: [], alerts: [] }] } as never);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><GuardianPortalPage /></QueryClientProvider>);
    expect(await screen.findByText("Sofía García")).toBeInTheDocument();
    expect(screen.getByText("88.5")).toBeInTheDocument();
    expect(screen.getByText("94%")).toBeInTheDocument();
    expect(screen.getByText(/1,250/)).toBeInTheDocument();
  });
});
