import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";
import type { Role } from "../types";
import { api } from "./api";

/** Shape of GET /access/me. */
export interface MyPermissions {
  permissions: string[];
  configured?: boolean;
}

/**
 * Grants each built-in role had before permissions were configured. Mirrors the
 * backend fallback: with no permission rows at all, the role name decides.
 */
export const legacyPermissions: Record<Role, string[]> = {
  admin: [
    "academic.manage",
    "grades.manage",
    "finance.manage",
    "reports.view",
    "communications.manage",
    "access.manage",
    "operations.manage",
    "schedule.manage",
  ],
  teacher: ["grades.manage", "communications.manage", "operations.manage"],
  student: ["records.own"],
  guardian: ["records.own"],
};

/** Effective grants: configured ones, or the legacy role defaults. */
export function resolvePermissions(data: MyPermissions | undefined, role: Role): string[] {
  const legacy = legacyPermissions[role] ?? [];
  if (!data || data.configured === false || !Array.isArray(data.permissions)) return legacy;
  return data.permissions;
}

/** Whether the signed-in account holds a permission. False while loading. */
export function useHasPermission(permission: string): boolean {
  const user = useAuthStore(state => state.user);
  const query = useQuery<MyPermissions>({
    queryKey: ["my-permissions", user?.user_id],
    queryFn: () => api.get("/access/me").then(response => response.data),
    enabled: Boolean(user),
  });
  if (!user || !query.isSuccess) return false;
  return resolvePermissions(query.data, user.role_name).includes(permission);
}
