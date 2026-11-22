import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { EmailPreferencesCard } from "./EmailPreferencesCard";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("saves each email notice preference as soon as it changes", async () => {
  const current = { email_announcements: true, email_grades: true, email_due_reminders: true };
  vi.spyOn(api, "get").mockResolvedValue({ data: current } as never);
  const put = vi
    .spyOn(api, "put")
    .mockResolvedValue({ data: { ...current, email_grades: false } } as never);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <EmailPreferencesCard />
    </QueryClientProvider>,
  );
  const grades = await screen.findByRole("checkbox", { name: /Notas publicadas/ });
  expect(grades).toBeChecked();
  fireEvent.click(grades);
  await waitFor(() =>
    expect(put).toHaveBeenCalledWith("/auth/email-preferences", {
      ...current,
      email_grades: false,
    }),
  );
  await waitFor(() => expect(grades).not.toBeChecked());
});
