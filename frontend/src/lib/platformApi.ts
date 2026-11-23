import axios from "axios";
import { create } from "zustand";
import { api } from "./api";

const KEY = "nexo_platform_token";

function stored() {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

interface PlatformSession {
  token: string | null;
  signIn: (token: string) => void;
  signOut: () => void;
}

/** Platform super administration keeps its own session, never mixed with an institution's. */
export const usePlatformSession = create<PlatformSession>(set => ({
  token: stored(),
  signIn: token => {
    sessionStorage.setItem(KEY, token);
    set({ token });
  },
  signOut: () => {
    sessionStorage.removeItem(KEY);
    set({ token: null });
  },
}));

export const platformApi = axios.create({
  baseURL: api.defaults.baseURL,
  headers: { "Content-Type": "application/json" },
});

platformApi.interceptors.request.use(config => {
  const token = usePlatformSession.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

platformApi.interceptors.response.use(undefined, error => {
  const status = axios.isAxiosError(error) ? error.response?.status : undefined;
  const login = axios.isAxiosError(error) && error.config?.url?.includes("/platform/auth/login");
  if ((status === 401 || status === 403) && !login) usePlatformSession.getState().signOut();
  return Promise.reject(error);
});
