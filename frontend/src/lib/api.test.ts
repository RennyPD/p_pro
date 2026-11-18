import axios, { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useAuthStore } from "../store/auth";
import type { User } from "../types";
import { api, renewSession, resolveApiUrl, tokenNeedsRefresh } from "./api";

const user: User = {
  user_id: 1,
  username: "test",
  email: "test@example.com",
  role_id: 1,
  role_name: "admin",
  student_id: null,
  teacher_id: null,
};
const originalAdapter = api.defaults.adapter;
const response = (config: InternalAxiosRequestConfig, data: unknown = {}) => ({
  data,
  status: 200,
  statusText: "OK",
  headers: new AxiosHeaders(),
  config,
});
const unauthorized = (config?: InternalAxiosRequestConfig, status = 401) =>
  new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, undefined, {
    data: {},
    status,
    statusText: "Unauthorized",
    headers: new AxiosHeaders(),
    config: config!,
  });

beforeEach(() => {
  useAuthStore.getState().clearSession();
  useAuthStore.getState().setSession("old-token", user);
});
afterEach(() => {
  api.defaults.adapter = originalAdapter;
  vi.restoreAllMocks();
  useAuthStore.getState().clearSession();
});

it("shares a single refresh between simultaneous unauthorized requests", async () => {
  const post = vi
    .spyOn(axios, "post")
    .mockResolvedValue({ data: { access_token: "fresh-token", user } });
  api.defaults.adapter = async config => {
    if (config.headers.Authorization === "Bearer old-token") throw unauthorized(config);
    return response(config, { ok: true });
  };
  const results = await Promise.all([
    api.get("/dashboard"),
    api.get("/teachers"),
    api.get("/students"),
    api.get("/sections"),
  ]);
  expect(results.every(item => item.data.ok)).toBe(true);
  expect(post).toHaveBeenCalledTimes(1);
  expect(post).toHaveBeenCalledWith(
    expect.stringContaining("/auth/refresh"),
    {},
    expect.objectContaining({ withCredentials: true }),
  );
  expect(useAuthStore.getState().token).toBe("fresh-token");
});

it("reuses the renewed token when a delayed old 401 arrives", async () => {
  const post = vi
    .spyOn(axios, "post")
    .mockResolvedValue({ data: { access_token: "fresh-token", user } });
  let release!: () => void;
  const delayed = new Promise<void>(resolve => {
    release = resolve;
  });
  api.defaults.adapter = async config => {
    if (config.headers.Authorization === "Bearer old-token") {
      if (config.url === "/late") await delayed;
      throw unauthorized(config);
    }
    return response(config);
  };
  const late = api.get("/late");
  await api.get("/first");
  release();
  await late;
  expect(post).toHaveBeenCalledTimes(1);
});

it.each([new AxiosError("offline", "ERR_NETWORK"), unauthorized(undefined, 500)])(
  "retains session when refresh fails temporarily: %s",
  async error => {
    vi.spyOn(axios, "post").mockRejectedValue(error);
    await expect(renewSession()).rejects.toBe(error);
    expect(useAuthStore.getState().token).toBe("old-token");
  },
);

it("clears a genuinely expired or revoked refresh session", async () => {
  vi.spyOn(axios, "post").mockRejectedValue(unauthorized());
  await expect(renewSession()).rejects.toBeInstanceOf(AxiosError);
  expect(useAuthStore.getState().token).toBeNull();
});

it("does not restore a session after logout during renewal", async () => {
  let finish!: (value: unknown) => void;
  const post = vi.spyOn(axios, "post").mockImplementation(
    () =>
      new Promise(resolve => {
        finish = resolve;
      }),
  );
  const renewal = renewSession();
  const result = expect(renewal).rejects.toThrow("La sesión ha cambiado");
  await vi.waitFor(() => expect(post).toHaveBeenCalledTimes(1));
  useAuthStore.getState().clearSession();
  finish({ data: { access_token: "fresh-token", user } });
  await result;
  expect(useAuthStore.getState().token).toBeNull();
});

it("does not loop when a renewed access token is also rejected", async () => {
  const post = vi
    .spyOn(axios, "post")
    .mockResolvedValue({ data: { access_token: "fresh-token", user } });
  api.defaults.adapter = async config => {
    throw unauthorized(config);
  };
  await expect(api.get("/protected")).rejects.toBeInstanceOf(AxiosError);
  expect(post).toHaveBeenCalledTimes(1);
  expect(useAuthStore.getState().token).toBeNull();
});

it("does not silently switch profiles if another tab changed the refresh account", async () => {
  vi.spyOn(axios, "post").mockResolvedValue({
    data: { access_token: "another-account", user: { ...user, user_id: 2, role_name: "teacher" } },
  });
  await expect(renewSession()).rejects.toThrow("La cuenta de esta sesión ha cambiado");
  expect(useAuthStore.getState().token).toBeNull();
});

it("does not refresh a rejected login", async () => {
  const post = vi.spyOn(axios, "post");
  api.defaults.adapter = async config => {
    throw unauthorized(config);
  };
  await expect(api.post("/auth/login", {})).rejects.toBeInstanceOf(AxiosError);
  expect(post).not.toHaveBeenCalled();
});

it("aligns local cookie hosts without altering remote server addresses", () => {
  expect(resolveApiUrl("http://127.0.0.1:8000", "localhost")).toBe("http://localhost:8000");
  expect(resolveApiUrl("http://localhost:8000", "127.0.0.1")).toBe("http://127.0.0.1:8000");
  expect(resolveApiUrl("https://api.example.com", "localhost")).toBe("https://api.example.com");
});

it("identifies tokens near expiry and tolerates malformed tokens", () => {
  const token = (exp: number) => `header.${btoa(JSON.stringify({ exp }))}.signature`;
  expect(tokenNeedsRefresh(token(150), 100_000)).toBe(true);
  expect(tokenNeedsRefresh(token(300), 100_000)).toBe(false);
  expect(tokenNeedsRefresh("test-token")).toBe(false);
});
