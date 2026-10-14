import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BookOpen, CalendarDays, ChevronDown, ClipboardCheck, FileText, GraduationCap, LayoutDashboard, LogOut, Menu, Settings2, Users, Wallet, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuthStore } from "../store/auth";
import type { Role } from "../types";

const adminNav = [
  { to: "/", label: "Vista general", icon: LayoutDashboard }, { to: "/students", label: "Estudiantes", icon: GraduationCap },
  { to: "/teachers", label: "Docentes", icon: Users }, { to: "/careers", label: "Carreras", icon: GraduationCap },
  { to: "/subjects", label: "Asignaturas", icon: BookOpen }, { to: "/sections", label: "Secciones", icon: CalendarDays },
  { to: "/assessments", label: "Evaluaciones", icon: BookOpen }, { to: "/operations", label: "Agenda y tareas", icon: CalendarDays },
  { to: "/grades", label: "Calificaciones", icon: BookOpen }, { to: "/attendances", label: "Asistencia", icon: ClipboardCheck },
  { to: "/equivalences", label: "Equivalencias", icon: BookOpen }, { to: "/finance", label: "Finanzas", icon: Wallet },
  { to: "/communications", label: "Comunicaciones", icon: Bell }, { to: "/institutional-control", label: "Control institucional", icon: FileText },
  { to: "/settings", label: "Configuración", icon: Settings2 },
];
const teacherNav = [
  { to: "/", label: "Mi jornada", icon: LayoutDashboard }, { to: "/my-schedule", label: "Mi horario", icon: CalendarDays },
  { to: "/sections", label: "Mis secciones", icon: CalendarDays }, { to: "/students", label: "Mis estudiantes", icon: Users },
  { to: "/assessments", label: "Evaluaciones", icon: BookOpen }, { to: "/operations", label: "Agenda y tareas", icon: CalendarDays },
  { to: "/grades", label: "Calificaciones", icon: BookOpen }, { to: "/attendances", label: "Asistencia", icon: ClipboardCheck },
  { to: "/communications", label: "Comunicaciones", icon: Bell },
];
const studentNav = [
  { to: "/", label: "Mi resumen", icon: LayoutDashboard }, { to: "/my-catalog", label: "Elegir asignaturas", icon: BookOpen },
  { to: "/my-schedule", label: "Mi horario", icon: CalendarDays }, { to: "/operations", label: "Agenda y tareas", icon: CalendarDays },
  { to: "/my-grades", label: "Mis notas", icon: BookOpen }, { to: "/my-attendance", label: "Mi asistencia", icon: ClipboardCheck },
  { to: "/my-progress", label: "Mi progreso", icon: GraduationCap }, { to: "/my-graduation", label: "Mi graduación", icon: GraduationCap },
  { to: "/my-transcript", label: "Mi expediente", icon: FileText }, { to: "/my-finance", label: "Mi cuenta", icon: Wallet },
  { to: "/communications", label: "Comunicaciones", icon: Bell },
];
const guardianNav = [{ to: "/guardian", label: "Seguimiento familiar", icon: Users }, { to: "/operations", label: "Agenda y tareas", icon: CalendarDays }, { to: "/communications", label: "Comunicaciones", icon: Bell }, { to: "/account", label: "Mi cuenta", icon: Settings2 }];
const navPermissions: Record<string, string> = { "/institutional-control": "reports.view", "/finance": "finance.manage", "/grades": "grades.manage", "/attendances": "grades.manage", "/students": "academic.manage", "/teachers": "academic.manage", "/careers": "academic.manage", "/subjects": "academic.manage", "/sections": "academic.manage", "/assessments": "grades.manage", "/equivalences": "academic.manage", "/roles": "access.manage", "/users": "access.manage" };
const legacyPermissions: Record<Role, string[]> = { admin: ["academic.manage", "grades.manage", "finance.manage", "reports.view", "communications.manage", "access.manage", "operations.manage"], teacher: ["academic.manage", "grades.manage", "communications.manage", "operations.manage"], student: ["records.own"], guardian: ["records.own"] };
const roleLabels: Record<Role, string> = { admin: "Administración", teacher: "Docente", student: "Estudiante", guardian: "Tutor" };

export function AppShell() {
  const { user, clearSession } = useAuthStore();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const permissionsQuery = useQuery<{ permissions: string[]; configured?: boolean }>({ queryKey: ["my-permissions", user?.user_id], queryFn: () => api.get("/access/me").then(response => response.data), enabled: Boolean(user) });
  const institution = useQuery<{ institution_name: string }>({ queryKey: ["institution-settings", user?.user_id], queryFn: () => api.get("/configuration/institution").then(r => r.data), enabled: Boolean(user) });
  const periods = useQuery<{ name: string; active: boolean }[]>({ queryKey: ["periods", "shell", user?.user_id], queryFn: () => api.get("/periods/").then(r => r.data), enabled: Boolean(user) });
  if (!user) return null;
  const baseNav = user.role_name === "admin" ? adminNav : user.role_name === "teacher" ? teacherNav : user.role_name === "guardian" ? guardianNav : studentNav;
  const configuredPermissions = permissionsQuery.data?.configured === false ? legacyPermissions[user.role_name] : permissionsQuery.data?.permissions ?? legacyPermissions[user.role_name];
  const nav = baseNav.filter(item => !navPermissions[item.to] || configuredPermissions.includes(navPermissions[item.to]));
  async function logout() { try { await api.post("/auth/logout"); } finally { queryClient.clear(); clearSession(); navigate("/login"); } }
  return <div className="app-layout"><button className="mobile-menu" onClick={() => setOpen(true)} aria-label="Abrir menú"><Menu /></button><aside className={`sidebar ${open ? "sidebar--open" : ""}`}><div className="sidebar__top"><div className="brand-lockup brand-lockup--compact"><span className="brand-symbol"><GraduationCap /></span><strong>Nexo</strong></div><button className="sidebar-close" onClick={() => setOpen(false)} aria-label="Cerrar menú"><X /></button></div><div className="workspace-switch"><span className="workspace-mark">PA</span><div><strong title={institution.data?.institution_name}>{institution.data?.institution_name || "Portal académico"}</strong><small>{periods.data?.find(p => p.active)?.name || "Sin período vigente"}</small></div><ChevronDown size={16} /></div><nav className="sidebar-nav" aria-label="Navegación principal"><span className="nav-caption">Espacio de trabajo</span>{nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)} className={({ isActive }) => isActive ? "active" : ""}><Icon size={19} /><span>{label}</span></NavLink>)}</nav><div className="sidebar__profile"><span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span><div><strong>{user.username}</strong><small>{roleLabels[user.role_name]}</small></div><button onClick={logout} title="Cerrar sesión" aria-label="Cerrar sesión"><LogOut size={18} /></button></div></aside>{open && <div className="sidebar-scrim" onClick={() => setOpen(false)} />}<main className="main-surface"><Outlet /></main></div>;
}
