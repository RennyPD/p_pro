import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { UsersPage } from "./UsersPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const accounts = [
  {
    user_id: 7,
    username: "elena",
    email: "elena@example.com",
    role_id: 2,
    role_name: "teacher",
    linked_person: "Elena Demo",
    active: true,
  },
  {
    user_id: 8,
    username: "daniel",
    email: "daniel@example.com",
    role_id: 3,
    role_name: "student",
    linked_person: "Daniel Demo",
    active: false,
  },
];

function renderPage() {
  useAuthStore.setState({
    user: {
      user_id: 1,
      username: "admin",
      email: "admin@example.com",
      role_id: 1,
      role_name: "admin",
      student_id: null,
      teacher_id: null,
    },
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it("shows the account status and deactivates after confirmation", async () => {
  vi.spyOn(api, "get").mockImplementation(async path => ({
    data: String(path).startsWith("/users") ? accounts : [],
    headers: {},
  }) as never);
  const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} } as never);
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage();

  expect(await screen.findByText("Desactivada")).toBeInTheDocument();
  expect(screen.getByText("Activa")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reactivar la cuenta de daniel" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Desactivar la cuenta de elena" }));
  expect(confirm).toHaveBeenCalledWith(expect.stringContaining("Se cerrarán sus sesiones"));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/users/7/deactivate"));
});

it("does nothing when the deactivation is not confirmed", async () => {
  vi.spyOn(api, "get").mockImplementation(async path => ({
    data: String(path).startsWith("/users") ? accounts : [],
    headers: {},
  }) as never);
  const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} } as never);
  vi.spyOn(window, "confirm").mockReturnValue(false);
  renderPage();

  fireEvent.click(await screen.findByRole("button", { name: "Desactivar la cuenta de elena" }));
  expect(post).not.toHaveBeenCalled();
});
