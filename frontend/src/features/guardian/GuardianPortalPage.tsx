import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  CalendarCheck,
  ClipboardList,
  GraduationCap,
  LayoutDashboard,
  UserRound,
  Users,
  Wallet,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { GuardianAttendance } from "./GuardianAttendance";
import { GuardianGrades } from "./GuardianGrades";
import { GuardianPerformance } from "./GuardianPerformance";
import { GuardianSummary } from "./GuardianSummary";
import { GuardianTasks } from "./GuardianTasks";
import { AccountView } from "../payments/AccountView";
import { FamilyPayments } from "../payments/FamilyPayments";
import "./guardian-portal.css";

export type StudentOverview = ApiSchema<"GuardianStudentOverview">;
type Area = keyof StudentOverview["permissions"];
type TabKey = "summary" | "attendance" | "grades" | "tasks" | "finance" | "performance";

const TABS: { key: TabKey; label: string; icon: ReactNode; area?: Area }[] = [
  { key: "summary", label: "Resumen", icon: <LayoutDashboard /> },
  { key: "attendance", label: "Asistencia", icon: <CalendarCheck />, area: "attendance" },
  { key: "grades", label: "Notas", icon: <GraduationCap />, area: "academic" },
  { key: "tasks", label: "Tareas", icon: <ClipboardList />, area: "tasks" },
  { key: "finance", label: "Pagos", icon: <Wallet />, area: "finance" },
  { key: "performance", label: "Desempeño", icon: <BarChart3 />, area: "academic" },
];

function initials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase())
    .join("");
}

export function GuardianPortalPage() {
  const query = useQuery<StudentOverview[]>({
    queryKey: ["guardian-overview"],
    queryFn: () => api.get("/operations/guardian/overview").then(response => response.data),
  });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [tab, setTab] = useState<TabKey>("summary");
  const [familyView, setFamilyView] = useState(false);
  if (query.isLoading)
    return (
      <div className="page">
        <Spinner />
      </div>
    );
  if (query.error)
    return (
      <div className="page">
        <EmptyState
          icon={<UserRound />}
          title="No pudimos cargar el seguimiento"
          description={apiMessage(query.error)}
        />
      </div>
    );
  if (!query.data?.length)
    return (
      <div className="page">
        <EmptyState
          icon={<UserRound />}
          title="Sin estudiantes vinculados"
          description="Administración debe asociar al menos un estudiante a esta cuenta familiar."
        />
      </div>
    );
  const students = query.data;
  const student = students.find(item => item.student_id === selectedId) ?? students[0];
  const tabs = TABS.filter(item => !item.area || student.permissions[item.area]);
  const payers = students.filter(item => item.permissions.finance);
  const showFamily = familyView && payers.length > 1;
  const current = tabs.some(item => item.key === tab) ? tab : "summary";

  return (
    <div className="page guardian-page">
      <header className="guardian-header">
        <span className="kicker">Portal familiar</span>
        <h1>Seguimiento familiar</h1>
      </header>

      {students.length > 1 && (
        <div className="guardian-children" role="tablist" aria-label="Estudiantes vinculados">
          {students.map(item => {
            const active = !showFamily && item.student_id === student.student_id;
            return (
              <button
                key={item.student_id}
                type="button"
                role="tab"
                aria-selected={active}
                className={active ? "is-active" : undefined}
                onClick={() => {
                  setSelectedId(item.student_id);
                  setFamilyView(false);
                }}
              >
                <span className="guardian-initials" aria-hidden="true">
                  {initials(item.student_name)}
                </span>
                <span>{item.student_name.split(" ")[0]}</span>
              </button>
            );
          })}
          {payers.length > 1 && (
            <button
              type="button"
              role="tab"
              aria-selected={showFamily}
              className={showFamily ? "is-active" : undefined}
              onClick={() => setFamilyView(true)}
            >
              <span className="guardian-initials" aria-hidden="true">
                <Users size={16} />
              </span>
              <span>Pagos de la familia</span>
            </button>
          )}
        </div>
      )}

      {showFamily ? (
        <FamilyPayments />
      ) : (
        <>
          <section className="guardian-hero" aria-label="Estudiante seleccionado">
            <span className="guardian-initials guardian-initials--large" aria-hidden="true">
              {initials(student.student_name)}
            </span>
            <div>
              <h2>{student.student_name}</h2>
              <p>
                {student.enrollment_number} · {student.career_name}
              </p>
            </div>
            <span className={student.active ? "status-active" : "status-inactive"}>
              {student.active ? "Activo" : "Inactivo"}
            </span>
          </section>

          <nav className="guardian-tabs" role="tablist" aria-label="Información del estudiante">
            {tabs.map(item => (
              <button
                key={item.key}
                type="button"
                role="tab"
                id={`guardian-tab-${item.key}`}
                aria-selected={current === item.key}
                aria-controls="guardian-panel"
                className={current === item.key ? "is-active" : undefined}
                onClick={() => setTab(item.key)}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </nav>

          <div
            id="guardian-panel"
            role="tabpanel"
            aria-labelledby={`guardian-tab-${current}`}
            className="guardian-panel"
          >
            {current === "summary" && <GuardianSummary student={student} onOpen={setTab} />}
            {current === "attendance" && <GuardianAttendance studentId={student.student_id} />}
            {current === "grades" && <GuardianGrades studentId={student.student_id} />}
            {current === "tasks" && <GuardianTasks studentId={student.student_id} />}
            {current === "finance" && (
              <AccountView
                studentId={student.student_id}
                statementPath={`/guardian/students/${student.student_id}/statement`}
              />
            )}
            {current === "performance" && <GuardianPerformance studentId={student.student_id} />}
          </div>
        </>
      )}
    </div>
  );
}
