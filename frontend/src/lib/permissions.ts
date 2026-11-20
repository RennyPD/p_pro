import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";
import { api } from "./api";

export type Scope = "institution" | "sections" | "own" | "linked";

/** Shape of GET /access/me: effective permissions and the role's data scope. */
export interface MyPermissions {
  permissions: string[];
  scope?: Scope;
  role_title?: string;
  configured?: boolean;
}

export function resolvePermissions(data: MyPermissions | undefined): string[] {
  return Array.isArray(data?.permissions) ? data.permissions : [];
}

/**
 * Everything the interface may show is decided here, from the role's permissions
 * and scope (never from the role's name).
 */
export function useAccess() {
  const user = useAuthStore(state => state.user);
  const query = useQuery<MyPermissions>({
    queryKey: ["my-permissions", user?.user_id],
    queryFn: () => api.get("/access/me").then(response => response.data),
    enabled: Boolean(user),
    staleTime: 60_000,
  });
  const granted = new Set(resolvePermissions(query.data));
  const scope = query.data?.scope;
  return {
    ready: query.isSuccess,
    scope,
    roleTitle: query.data?.role_title,
    permissions: granted,
    /** Holds every listed permission. */
    can: (...slugs: string[]) => slugs.every(slug => granted.has(slug)),
    /** Holds at least one of the listed permissions. */
    canAny: (...slugs: string[]) => slugs.some(slug => granted.has(slug)),
    institution: scope === "institution",
    teaching: scope === "sections",
    student: scope === "own",
    guardian: scope === "linked",
  };
}

/** Whether the signed-in account holds a permission. False while loading. */
export function useHasPermission(permission: string): boolean {
  return useAccess().can(permission);
}
