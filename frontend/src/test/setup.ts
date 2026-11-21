import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Components read permissions through useAccess (GET /access/me). Tests derive
// them from the test user's built-in role instead; see accessMock.ts.
vi.mock("../lib/permissions", async importOriginal => {
  const actual = await importOriginal<typeof import("../lib/permissions")>();
  const { useAccessMock } = await import("./accessMock");
  return {
    ...actual,
    useAccess: useAccessMock,
    useHasPermission: (permission: string) => useAccessMock().can(permission),
  };
});
