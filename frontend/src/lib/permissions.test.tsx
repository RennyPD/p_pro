import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import { useAuthStore } from "../store/auth";

afterEach(() => vi.restoreAllMocks());

it("decides access from permissions and scope, not from the role name", async () => {
  // The global test setup replaces useAccess; this test checks the real hook.
  const { useAccess } = await vi.importActual<typeof import("./permissions")>("./permissions");
  useAuthStore.setState({
    user: {
      user_id: 9,
      username: "caja",
      email: "caja@example.com",
      role_id: 9,
      role_name: "admin",
      student_id: null,
      teacher_id: null,
    },
  });
  vi.spyOn(api, "get").mockResolvedValue({
    data: { permissions: ["finance.view"], scope: "institution", role_title: "Caja" },
  } as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useAccess(), { wrapper });
  await waitFor(() => expect(result.current.ready).toBe(true));
  expect(result.current.institution).toBe(true);
  expect(result.current.roleTitle).toBe("Caja");
  expect(result.current.can("finance.view")).toBe(true);
  // Even with the "admin" role name, nothing beyond the granted permissions.
  expect(result.current.canAny("users.manage", "grades.manage")).toBe(false);
});
