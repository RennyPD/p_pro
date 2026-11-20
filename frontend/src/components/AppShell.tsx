import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  BarChart3,
  Bell,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  ClipboardCheck,
  FileText,
  GraduationCap,
  KeyRound,
  LayoutDashboard,
  Library,
  LogOut,
  Menu,
  NotebookPen,
  Settings2,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { Fragment, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { isCustomRole, useModuleViews } from "../lib/moduleViews";
import { api } from "../lib/api";
import { type MyPermissions, resolvePermissions } from "../lib/permissions";
import { useAuthStore } from "../store/auth";
import type { Role } from "../types";

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard; group?: string };
const adminNav: NavItem[] = [
  { to: "/", label: "Vista general", icon: LayoutDashboard },
  { to: "/students", label: "Estudiantes", icon: GraduationCap, group: "Académico" },
  { to: "/teachers", label: "Docentes", icon: Users, group: "Académico" },
  { to: "/careers", label: "Carreras", icon: Library, group: "Académico" },
  { to: "/subjects", label: "Asignaturas", icon: BookOpen, group: "Académico" },
  { to: "/sections", label: "Secciones", icon: CalendarDays, group: "Académico" },
  { to: "/equivalences", label: "Equivalencias", icon: ArrowLeftRight, group: "Académico" },
  { to: "/assessments", label: "Evaluaciones", icon: NotebookPen, group: "Seguimiento" },
  { to: "/grades", label: "Calificaciones", icon: BarChart3, group: "Seguimiento" },
  { to: "/attendances", label: "Asistencia", icon: ClipboardCheck, group: "Seguimiento" },
  { to: "/operations", label: "Agenda y tareas", icon: CalendarCheck, group: "Seguimiento" },
  { to: "/finance", label: "Finanzas", icon: Wallet, group: "Institución" },
  { to: "/communications", label: "Comunicaciones", icon: Bell, group: "Institución" },
  {
    to: "/institutional-control",
    label: "Control institucional",
    icon: FileText,
    group: "Institución",
  },
  { to: "/settings", label: "Configuración", icon: Settings2, group: "Institución" },
];
const teacherNav: NavItem[] = [
  { to: "/", label: "Mi jornada", icon: LayoutDashboard },
  { to: "/my-schedule", label: "Mi horario", icon: CalendarDays, group: "Docencia" },
  { to: "/sections", label: "Mis secciones", icon: Library, group: "Docencia" },
  { to: "/students", label: "Mis estudiantes", icon: Users, group: "Docencia" },
  { to: "/assessments", label: "Evaluaciones", icon: NotebookPen, group: "Seguimiento" },
  { to: "/grades", label: "Calificaciones", icon: BarChart3, group: "Seguimiento" },
  { to: "/attendances", label: "Asistencia", icon: ClipboardCheck, group: "Seguimiento" },
  { to: "/operations", label: "Agenda y tareas", icon: CalendarCheck, group: "Seguimiento" },
  { to: "/communications", label: "Comunicaciones", icon: Bell, group: "Seguimiento" },
];
const studentNav: NavItem[] = [
  { to: "/", label: "Mi resumen", icon: LayoutDashboard },
  { to: "/my-catalog", label: "Elegir asignaturas", icon: BookOpen, group: "Mis estudios" },
  { to: "/my-schedule", label: "Mi horario", icon: CalendarDays, group: "Mis estudios" },
  { to: "/operations", label: "Agenda y tareas", icon: CalendarCheck, group: "Mis estudios" },
  { to: "/my-grades", label: "Mis notas", icon: BarChart3, group: "Mis estudios" },
  { to: "/my-attendance", label: "Mi asistencia", icon: ClipboardCheck, group: "Mis estudios" },
  { to: "/my-progress", label: "Mi progreso", icon: GraduationCap, group: "Trayectoria" },
  { to: "/my-graduation", label: "Mi graduación", icon: Library, group: "Trayectoria" },
  { to: "/my-transcript", label: "Mi expediente", icon: FileText, group: "Trayectoria" },
  { to: "/my-finance", label: "Mi cuenta", icon: Wallet, group: "Institución" },
  { to: "/communications", label: "Comunicaciones", icon: Bell, group: "Institución" },
];
const guardianNav: NavItem[] = [
  { to: "/guardian", label: "Seguimiento familiar", icon: Users },
  { to: "/operations", label: "Agenda y tareas", icon: CalendarCheck },
  { to: "/communications", label: "Comunicaciones", icon: Bell },
];
const approvalsNav: NavItem = {
  to: "/approvals",
  label: "Mis solicitudes",
  icon: FileText,
  group: "Mi cuenta",
};
const accountNav: NavItem = {
  to: "/account",
  label: "Mi seguridad",
  icon: KeyRound,
  group: "Mi cuenta",
};
const navPermissions: Record<string, string> = {
  "/institutional-control": "reports.view",
  "/finance": "finance.manage",
  "/grades": "grades.manage",
  "/attendances": "grades.manage",
  "/students": "academic.manage",
  "/teachers": "academic.manage",
  "/careers": "academic.manage",
  "/subjects": "academic.manage",
  "/sections": "academic.manage",
  "/assessments": "grades.manage",
  "/equivalences": "academic.manage",
  "/roles": "access.manage",
  "/users": "access.manage",
};
const roleLabels: Record<Role, string> = {
  admin: "Administración",
  teacher: "Docente",
  student: "Estudiante",
  guardian: "Tutor",
};

/** "Instituto Técnico Horizonte" → "IH" (skips short connector words). */
const initials = (name: string) => {
  const words = name.split(/\s+/).filter(word => word.length > 3);
  return (
    words.length > 1 ? words[0][0] + words[words.length - 1][0] : (words[0] ?? "N").slice(0, 2)
  ).toUpperCase();
};

export function AppShell() {
  const { user, clearSession } = useAuthStore();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const custom = isCustomRole(user?.role_name);
  const modules = useModuleViews();
  const permissionsQuery = useQuery<MyPermissions>({
    queryKey: ["my-permissions", user?.user_id],
    queryFn: () => api.get("/access/me").then(response => response.data),
    enabled: Boolean(user) && !custom,
  });
  const institution = useQuery<{ institution_name: string }>({
    queryKey: ["institution-settings", user?.user_id],
    queryFn: () => api.get("/configuration/institution").then(r => r.data),
    enabled: Boolean(user) && !custom,
  });
  const periods = useQuery<{ name: string; active: boolean }[]>({
    queryKey: ["periods", "shell", user?.user_id],
    queryFn: () => api.get("/periods/", { params: { active: true, limit: 1 } }).then(r => r.data),
    enabled: Boolean(user) && !custom,
  });
  if (!user) return null;
  const baseNav =
    user.role_name === "admin"
      ? adminNav
      : user.role_name === "teacher"
        ? teacherNav
        : user.role_name === "guardian"
          ? guardianNav
          : studentNav;
  const configuredPermissions = resolvePermissions(permissionsQuery.data, user.role_name);
  const nav = custom
    ? [
        { to: "/", label: "Módulos de consulta", icon: LayoutDashboard },
        ...(modules.data ?? []).map(item => ({
          to: `/modules/${item.key}`,
          label: item.label,
          icon: BookOpen,
        })),
        accountNav,
      ]
    : [
        ...baseNav.filter(
          item =>
            (user.role_name === "teacher" && ["/sections", "/students"].includes(item.to)) ||
            !navPermissions[item.to] ||
            configuredPermissions.includes(navPermissions[item.to]),
        ),
        approvalsNav,
        accountNav,
      ];
  async function logout() {
    try {
      await api.post("/auth/logout");
    } finally {
      queryClient.clear();
      clearSession();
      navigate("/login");
    }
  }
  return (
    <div className="app-layout">
      <button className="mobile-menu" onClick={() => setOpen(true)} aria-label="Abrir menú">
        <Menu />
      </button>
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`}>
        <div className="sidebar__top">
          <div className="brand-lockup brand-lockup--compact">
            <span className="brand-symbol">
              <GraduationCap />
            </span>
            <strong>Nexo</strong>
          </div>
          <button className="sidebar-close" onClick={() => setOpen(false)} aria-label="Cerrar menú">
            <X />
          </button>
        </div>
        <div className="workspace-switch">
          <span className="workspace-mark" aria-hidden="true">
            {initials(institution.data?.institution_name || "Portal académico")}
          </span>
          <div>
            <strong title={institution.data?.institution_name}>
              {institution.data?.institution_name || "Portal académico"}
            </strong>
            {!custom && (
              <small>
                {periods.data?.find(p => p.active)?.name
                  ? `Período vigente · ${periods.data[0].name}`
                  : "Sin período vigente"}
              </small>
            )}
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="Navegación principal">
          {nav.map(({ to, label, icon: Icon, group }, index) => (
            <Fragment key={to}>
              {group !== nav[index - 1]?.group && group && (
                <span className="nav-caption">{group}</span>
              )}
              <NavLink
                to={to}
                end={to === "/"}
                onClick={() => setOpen(false)}
                className={({ isActive }) => (isActive ? "active" : "")}
              >
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            </Fragment>
          ))}
        </nav>
        <div className="sidebar__profile">
          <span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span>
          <div>
            <strong>{user.username}</strong>
            <small>{roleLabels[user.role_name] ?? "Rol personalizado"}</small>
          </div>
          <button onClick={logout} title="Cerrar sesión" aria-label="Cerrar sesión">
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      {open && <div className="sidebar-scrim" onClick={() => setOpen(false)} />}
      <main className="main-surface">
        <Outlet />
      </main>
    </div>
  );
}
