/**
 * Test double for useAccess: derives permissions from the signed-in test user's
 * built-in role, mirroring SYSTEM_ROLE_DEFAULTS in app/permissions.py. Component
 * tests then do not need to mock GET /access/me.
 */
import { useAuthStore } from "../store/auth";
import type { Scope } from "../lib/permissions";

const teacher = [
  "students.view",
  "sections.view",
  "grades.view",
  "grades.manage",
  "attendance.view",
  "attendance.manage",
  "tasks.manage",
  "calendar.manage",
  "cases.manage",
  "communications.manage",
];
const admin = [
  ...teacher,
  "students.manage",
  "teachers.view",
  "teachers.manage",
  "programs.manage",
  "equivalences.manage",
  "sections.manage",
  "schedule.manage",
  "classrooms.manage",
  "enrollments.manage",
  "finance.view",
  "finance.manage",
  "finance.collect",
  "finance.supervise",
  "admissions.manage",
  "approvals.manage",
  "reports.view",
  "audit.view",
  "settings.manage",
  "users.manage",
  "roles.manage",
];
const defaults: Record<string, [Scope, string[]]> = {
  admin: ["institution", admin],
  teacher: ["sections", teacher],
  student: ["own", ["records.own", "selection.own"]],
  guardian: ["linked", ["records.own"]],
};

export function accessFor(role?: string) {
  const [scope, slugs] = defaults[role ?? ""] ?? ["institution", []];
  const granted = new Set(slugs);
  return {
    ready: true,
    scope,
    roleTitle: role,
    permissions: granted,
    can: (...list: string[]) => list.every(slug => granted.has(slug)),
    canAny: (...list: string[]) => list.some(slug => granted.has(slug)),
    institution: scope === "institution",
    teaching: scope === "sections",
    student: scope === "own",
    guardian: scope === "linked",
  };
}

export const useAccessMock = () => accessFor(useAuthStore(state => state.user?.role_name));
