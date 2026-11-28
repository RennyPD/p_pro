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
  CreditCard,
  LifeBuoy,
  MessageCircle,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { Fragment, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useModuleViews } from "../lib/moduleViews";
import { api } from "../lib/api";
import { useAccess } from "../lib/permissions";
import { useAuthStore } from "../store/auth";
import { BillingBanner } from "../features/billing/BillingBanner";
import { LegalGate } from "../features/legal/LegalGate";
import { DemoBanner } from "../features/demo/DemoBanner";

type Access = ReturnType<typeof useAccess>;
type NavItem = {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  group?: string;
  /** Visible when this returns true: permissions and scope, never the role name. */
  show?: (access: Access) => boolean;
};
const staff = (a: Access) => a.institution || a.teaching;
const own = (a: Access) => a.student && a.can("records.own");

/** One menu for every role: each entry declares the permission it needs. */
const NAV: NavItem[] = [
  { to: "/", label: "Inicio", icon: LayoutDashboard, show: a => !a.guardian },
  {
    to: "/guardian",
    label: "Seguimiento familiar",
    icon: Users,
    show: a => a.guardian && a.can("records.own"),
  },
  {
    to: "/my-catalog",
    label: "Elegir asignaturas",
    icon: BookOpen,
    group: "Mis estudios",
    show: a => a.student && a.can("selection.own"),
  },
  { to: "/my-schedule", label: "Mi horario", icon: CalendarDays, group: "Mis estudios", show: own },
  { to: "/my-grades", label: "Mis notas", icon: BarChart3, group: "Mis estudios", show: own },
  {
    to: "/my-attendance",
    label: "Mi asistencia",
    icon: ClipboardCheck,
    group: "Mis estudios",
    show: own,
  },
  {
    to: "/my-progress",
    label: "Mi progreso",
    icon: GraduationCap,
    group: "Trayectoria",
    show: own,
  },
  { to: "/my-graduation", label: "Mi graduación", icon: Library, group: "Trayectoria", show: own },
  { to: "/my-transcript", label: "Mi expediente", icon: FileText, group: "Trayectoria", show: own },
  { to: "/my-finance", label: "Mi cuenta", icon: Wallet, group: "Trayectoria", show: own },
  {
    to: "/my-schedule",
    label: "Mi horario",
    icon: CalendarDays,
    group: "Académico",
    show: a => a.teaching,
  },
  {
    to: "/students",
    label: "Estudiantes",
    icon: GraduationCap,
    group: "Académico",
    show: a => staff(a) && a.canAny("students.view", "students.manage"),
  },
  {
    to: "/teachers",
    label: "Docentes",
    icon: Users,
    group: "Académico",
    show: a => a.institution && a.canAny("teachers.view", "teachers.manage"),
  },
  {
    to: "/careers",
    label: "Carreras",
    icon: Library,
    group: "Académico",
    show: a => a.institution && a.can("programs.manage"),
  },
  {
    to: "/subjects",
    label: "Asignaturas",
    icon: BookOpen,
    group: "Académico",
    show: a => a.institution && a.can("programs.manage"),
  },
  {
    to: "/sections",
    label: "Secciones",
    icon: CalendarDays,
    group: "Académico",
    show: a => staff(a) && a.canAny("sections.view", "sections.manage"),
  },
  {
    to: "/class-groups",
    label: "Grupos",
    icon: Users,
    group: "Académico",
    show: a => staff(a) && a.canAny("sections.view", "sections.manage", "enrollments.manage"),
  },
  {
    to: "/equivalences",
    label: "Equivalencias",
    icon: ArrowLeftRight,
    group: "Académico",
    show: a => a.institution && a.can("equivalences.manage"),
  },
  {
    to: "/assessments",
    label: "Evaluaciones",
    icon: NotebookPen,
    group: "Seguimiento",
    show: a => staff(a) && a.can("grades.manage"),
  },
  {
    to: "/grades",
    label: "Calificaciones",
    icon: BarChart3,
    group: "Seguimiento",
    show: a => staff(a) && a.canAny("grades.view", "grades.manage"),
  },
  {
    to: "/attendances",
    label: "Asistencia",
    icon: ClipboardCheck,
    group: "Seguimiento",
    show: a => staff(a) && a.canAny("attendance.view", "attendance.manage"),
  },
  { to: "/operations", label: "Agenda y tareas", icon: CalendarCheck, group: "Seguimiento" },
  {
    to: "/finance",
    label: "Finanzas",
    icon: Wallet,
    group: "Institución",
    show: a => a.institution && a.can("finance.view"),
  },
  { to: "/communications", label: "Comunicaciones", icon: Bell, group: "Institución" },
  {
    to: "/institutional-control",
    label: "Control institucional",
    icon: FileText,
    group: "Institución",
    show: a => a.institution && a.canAny("reports.view", "cases.manage", "admissions.manage"),
  },
  {
    to: "/billing",
    label: "Plan y facturación",
    icon: CreditCard,
    group: "Institución",
    show: a => a.institution && a.can("billing.manage"),
  },
  {
    to: "/settings",
    label: "Configuración",
    icon: Settings2,
    group: "Institución",
    show: a =>
      a.institution &&
      a.canAny("settings.manage", "users.manage", "roles.manage", "audit.view", "students.manage"),
  },
];
const ACCOUNT_NAV: NavItem[] = [
  { to: "/approvals", label: "Mis solicitudes", icon: FileText, group: "Mi cuenta" },
  { to: "/account", label: "Mi seguridad", icon: KeyRound, group: "Mi cuenta" },
  { to: "/help", label: "Ayuda", icon: LifeBuoy, group: "Mi cuenta" },
  { to: "/support", label: "Soporte", icon: MessageCircle, group: "Mi cuenta" },
];

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
  const access = useAccess();
  const modules = useModuleViews();
  const institution = useQuery<{
    institution_name: string;
    students_view_finance?: boolean;
    institution_type?: string;
  }>({
    queryKey: ["institution-settings", user?.user_id],
    queryFn: () => api.get("/configuration/institution").then(r => r.data),
    enabled: Boolean(user),
  });
  const periods = useQuery<{ name: string; active: boolean }[]>({
    queryKey: ["periods", "shell", user?.user_id],
    queryFn: () => api.get("/periods/", { params: { active: true, limit: 1 } }).then(r => r.data),
    enabled: Boolean(user),
  });
  if (!user) return null;
  const labels: Record<string, string> = access.teaching
    ? { "/": "Mi jornada", "/sections": "Mis secciones", "/students": "Mis estudiantes" }
    : access.student
      ? { "/": "Mi resumen" }
      : access.institution
        ? { "/": "Vista general" }
        : {};
  const nav: NavItem[] = access.ready
    ? [
        ...NAV.filter(item => !item.show || item.show(access))
          .filter(
            item => item.to !== "/my-finance" || institution.data?.students_view_finance !== false,
          )
          // Fixed groups are a school feature (Fase 3 C).
          .filter(
            item =>
              item.to !== "/class-groups" ||
              (institution.data?.institution_type ?? "university") !== "university",
          )
          .map(item => ({
            ...item,
            label: labels[item.to] ?? item.label,
          })),
        ...(modules.data ?? []).map(item => ({
          to: `/modules/${item.key}`,
          label: item.label,
          icon: BookOpen,
          group: "Consulta",
        })),
        ...ACCOUNT_NAV,
      ]
    : ACCOUNT_NAV;
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
            <small>
              {periods.data?.find(p => p.active)?.name
                ? `Período vigente · ${periods.data[0].name}`
                : "Sin período vigente"}
            </small>
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
            <small>{access.roleTitle ?? ""}</small>
          </div>
          <button onClick={logout} title="Cerrar sesión" aria-label="Cerrar sesión">
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      {open && <div className="sidebar-scrim" onClick={() => setOpen(false)} />}
      <main className="main-surface">
        <DemoBanner />
        <BillingBanner />
        <LegalGate />
        <Outlet />
      </main>
    </div>
  );
}
