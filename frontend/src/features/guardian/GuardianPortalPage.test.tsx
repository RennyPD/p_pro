import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { GuardianPortalPage } from "./GuardianPortalPage";

describe("GuardianPortalPage", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });
  it("shows the linked student's academic and financial summary", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [{ student_id: 1, student_name: "Sofía García", enrollment_number: "ITH-2026-001", career_name: "Desarrollo de Software", active: true, average_grade: 88.5, attendance_percentage: 94, balance: 1250, schedule: [], alerts: [] }] } as never);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><GuardianPortalPage /></QueryClientProvider>);
    expect(await screen.findByText("Sofía García")).toBeInTheDocument();
    expect(screen.getByText("88.5")).toBeInTheDocument();
    expect(screen.getByText("94%")).toBeInTheDocument();
    expect(screen.getByText(/1,250/)).toBeInTheDocument();
  });
  it("translates alert categories and priorities", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: [{ student_id: 1, student_name: "Sofía", enrollment_number: "ITH-001", career_name: "Software", active: true, average_grade: 90, attendance_percentage: 100, balance: 0, schedule: [], alerts: [{ early_alert_id: 1, category: "academic", severity: "high", reason: "Revisar progreso", follow_up_date: null }] }] } as never);
    render(<QueryClientProvider client={new QueryClient()}><GuardianPortalPage /></QueryClientProvider>);
    expect(await screen.findByText("Académica")).toBeInTheDocument();
    expect(screen.getByText("Prioridad Alta")).toBeInTheDocument();
    expect(screen.queryByText("academic")).not.toBeInTheDocument();
    expect(screen.queryByText("high")).not.toBeInTheDocument();
  });
  it("lets the guardian download the linked student's documents", async () => {
    const get = vi.spyOn(api, "get").mockResolvedValue({ data: [{ student_id: 7, student_name: "Sofía", enrollment_number: "ITH-007", career_name: "Software", active: true, average_grade: 90, attendance_percentage: 100, balance: 0, schedule: [], alerts: [] }] } as never);
    render(<QueryClientProvider client={new QueryClient()}><GuardianPortalPage /></QueryClientProvider>);
    expect(await screen.findByRole("region", { name: "Documentos de Sofía" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Estado de cuenta PDF/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Boletín PDF/ }));
    await waitFor(() => expect(get).toHaveBeenCalledWith("/documents/students/7/report-card.pdf", { responseType: "blob" }));
  });
});
