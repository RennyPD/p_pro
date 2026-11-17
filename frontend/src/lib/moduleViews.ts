import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useAuthStore } from "../store/auth";

export type ModuleView = { key: string; label: string };

export function isCustomRole(role?: string) {
  return Boolean(role && !["admin", "teacher", "student", "guardian"].includes(role));
}

export function useModuleViews() {
  const user = useAuthStore(state => state.user);
  return useQuery({
    queryKey: ["module-views", "mine", user?.user_id],
    queryFn: () => api.get<ModuleView[]>("/module-views/mine").then(response => response.data),
    enabled: isCustomRole(user?.role_name),
    refetchOnWindowFocus: "always",
  });
}
