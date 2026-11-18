import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "../store/auth";
import type { TokenResponse } from "../types";

export function resolveApiUrl(configured: string, hostname = window.location.hostname) {
  const url = new URL(configured, window.location.origin);
  // localhost and 127.0.0.1 are different cookie sites. Keep development
  // same-site so the HttpOnly SameSite=Lax refresh cookie can travel.
  if (["localhost", "127.0.0.1"].includes(hostname) && ["localhost", "127.0.0.1"].includes(url.hostname))
    url.hostname = hostname;
  return url.toString().replace(/\/$/, "");
}

export const api = axios.create({
  baseURL: resolveApiUrl(import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"),
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});
type SessionRequest = InternalAxiosRequestConfig & { _retried?: boolean; _sessionGeneration?: number };
let pendingRefresh: { generation: number; promise: Promise<string> } | undefined;
const authenticationEndpoint = (url = "") => /\/auth\/(login|bootstrap|refresh|logout)(?:[/?]|$)/.test(url);

export function isAuthenticationError(error: unknown) {
  return axios.isAxiosError(error) && (error.response?.status === 401 || error.response?.status === 403);
}

export function tokenNeedsRefresh(token: string, now = Date.now()) {
  try {
    const payload = token.split(".")[1];
    const { exp } = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    return typeof exp === "number" && exp * 1000 <= now + 60_000;
  } catch {
    return false;
  }
}

/** One refresh per session, shared by proactive renewal and failed requests. */
export function renewSession(): Promise<string> {
  const { token, user, sessionGeneration: generation } = useAuthStore.getState();
  if (!token) return Promise.reject(new Error("No hay una sesión activa."));
  if (pendingRefresh?.generation === generation) return pendingRefresh.promise;
  const perform = async () => {
    if (useAuthStore.getState().sessionGeneration !== generation) throw new Error("La sesión ha cambiado.");
    try {
      const { data } = await axios.post<TokenResponse>(
        `${api.defaults.baseURL}/auth/refresh`,
        {},
        { withCredentials: true, timeout: 15_000 },
      );
      if (useAuthStore.getState().sessionGeneration !== generation) throw new Error("La sesión ha cambiado.");
      if (user && data.user.user_id !== user.user_id) {
        useAuthStore.getState().clearSession();
        throw new Error("La cuenta de esta sesión ha cambiado. Inicia sesión de nuevo.");
      }
      useAuthStore.getState().setSession(data.access_token, data.user);
      return data.access_token;
    } catch (error) {
      // Offline connections and server errors must not discard the session.
      if (isAuthenticationError(error) && useAuthStore.getState().sessionGeneration === generation)
        useAuthStore.getState().clearSession();
      throw error;
    }
  };
  // Tabs share a rotating refresh cookie, but not their access token/store.
  const operation = Promise.resolve(
    navigator.locks ? navigator.locks.request("nexo-session-refresh", perform) : perform(),
  );
  const promise = operation.finally(() => {
    if (pendingRefresh?.promise === promise) pendingRefresh = undefined;
  });
  pendingRefresh = { generation, promise };
  return promise;
}

api.interceptors.request.use((config: SessionRequest) => {
  const { token, sessionGeneration } = useAuthStore.getState();
  config._sessionGeneration = sessionGeneration;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  response => response,
  async (error: AxiosError) => {
    const request = error.config as SessionRequest | undefined;
    const state = useAuthStore.getState();
    if (
      error.response?.status !== 401 ||
      !request ||
      authenticationEndpoint(request.url) ||
      !state.token ||
      request._sessionGeneration !== state.sessionGeneration
    )
      return Promise.reject(error);
    if (request._retried) {
      state.clearSession();
      return Promise.reject(error);
    }
    request._retried = true;
    const generation = state.sessionGeneration;
    // A delayed 401 may arrive after another request already renewed the token.
    const token = request.headers.Authorization !== `Bearer ${state.token}` ? state.token : await renewSession();
    if (useAuthStore.getState().sessionGeneration !== generation) return Promise.reject(error);
    request.headers.Authorization = `Bearer ${token}`;
    return api(request);
  },
);

export function apiMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (Array.isArray(detail)) return detail.map(item => item.msg).join(". ");
    if (typeof detail === "string") return detail;
  }
  return "No pudimos completar la operación. Inténtalo de nuevo.";
}
