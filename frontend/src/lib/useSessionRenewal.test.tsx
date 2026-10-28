import { act, cleanup, fireEvent, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useAuthStore } from "../store/auth";
import type { User } from "../types";
import { renewSession, tokenNeedsRefresh } from "./api";
import { useSessionRenewal } from "./useSessionRenewal";

vi.mock("./api", () => ({ renewSession: vi.fn(), tokenNeedsRefresh: vi.fn() }));
const user: User = { user_id: 1, username: "test", email: "test@example.com", role_id: 1, role_name: "teacher", student_id: null, teacher_id: 1 };

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-28T12:00:00Z"));
  vi.mocked(renewSession).mockResolvedValue("fresh-token");
  vi.mocked(tokenNeedsRefresh).mockReturnValue(false);
  useAuthStore.getState().setSession("token", user);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.clearAllMocks(); useAuthStore.getState().clearSession(); });

it("renews near expiry even when editing without making API requests", async () => {
  renderHook(() => useSessionRenewal());
  vi.mocked(tokenNeedsRefresh).mockReturnValue(true);
  await act(async () => { vi.advanceTimersByTime(30_000); });
  expect(renewSession).toHaveBeenCalledTimes(1);
});

it("does not keep abandoned tabs alive, but renews on return to activity", async () => {
  renderHook(() => useSessionRenewal());
  await act(async () => { vi.advanceTimersByTime(6 * 60_000); });
  vi.mocked(tokenNeedsRefresh).mockReturnValue(true);
  await act(async () => { vi.advanceTimersByTime(30_000); });
  expect(renewSession).not.toHaveBeenCalled();
  await act(async () => { fireEvent.keyDown(window, { key: "a" }); });
  expect(renewSession).toHaveBeenCalledTimes(1);
});

it("retries a temporary failure without discarding authentication", async () => {
  vi.mocked(tokenNeedsRefresh).mockReturnValue(true);
  vi.mocked(renewSession).mockRejectedValue(new Error("offline"));
  renderHook(() => useSessionRenewal());
  await act(async () => { vi.advanceTimersByTime(30_000); });
  expect(renewSession).toHaveBeenCalledTimes(2);
  expect(useAuthStore.getState().token).toBe("token");
});
