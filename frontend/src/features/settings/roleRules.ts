/** Role editor rules shared by the roles page and its tests. */

export type RoleRow = {
  role_id: number;
  name: string;
  label?: string | null;
  role_title: string;
  description: string;
  scope: string;
  user_count: number;
  permission_count: number;
};
export type PermissionDef = {
  slug: string;
  module: string;
  label: string;
  description: string;
  institutional: boolean;
};
export type ScopeOption = { value: string; label: string };
export type Change = { id: number; actor: string; detail: string; created_at: string };

export const SYSTEM_ROLES = ["admin", "teacher", "student", "guardian"];
const PERSONAL = ["records.own", "selection.own"];
export const scopeTone: Record<string, "info" | "success" | "warning" | "neutral"> = {
  institution: "info",
  sections: "success",
  own: "warning",
  linked: "neutral",
};
export const scopeShort: Record<string, string> = {
  institution: "Toda la institución",
  sections: "Sus secciones",
  own: "Su expediente",
  linked: "Estudiantes vinculados",
};

/** "Coordinación académica" → "coordinacion_academica" (internal role code). */
export function roleCode(label: string) {
  return label
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 50);
}

/** Whether a permission can be used with a scope (mirrors the backend rules). */
export function fitsScope(permission: PermissionDef, scope: string) {
  if (PERSONAL.includes(permission.slug)) return scope === "own" || scope === "linked";
  if (scope === "own" || scope === "linked") return false;
  return !permission.institutional || scope === "institution";
}

/**
 * Toggles a permission. Managing implies consulting: choosing "x.manage" also
 * selects "x.view", and removing "x.view" removes "x.manage".
 */
export function togglePermission(selected: string[], slug: string, on: boolean): string[] {
  const [module, action] = slug.split(".");
  const next = new Set(selected);
  if (on) {
    next.add(slug);
    if (action === "manage") next.add(`${module}.view`);
  } else {
    next.delete(slug);
    if (action === "view") next.delete(`${module}.manage`);
  }
  return [...next];
}
