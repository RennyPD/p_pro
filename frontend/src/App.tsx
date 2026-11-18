import { isCustomRole } from "./lib/moduleViews";
import { CustomModuleHome, CustomModuleRoute } from "./features/settings/CustomModulePage";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { resources } from "./config/resources";
import {
  MyAttendancePage,
  MyGradesPage,
  MyProgressPage,
  SectionWorkspacePage,
} from "./features/academic/AcademicPages";
import { TeachersPage } from "./features/academic/TeachersPage";
import { TeacherDossierPage } from "./features/academic/TeacherDossierPage";
import { StudentsPage } from "./features/academic/StudentsPage";
import { SubjectsPage } from "./features/academic/SubjectsPage";
import { SubjectProgramPage } from "./features/academic/SubjectProgramPage";
import { CareersPage } from "./features/academic/CareersPage";
import { CareerProgramPage } from "./features/academic/CareerProgramPage";
import { CourseCatalogPage } from "./features/academic/CourseCatalogPage";
import { GraduationAuditPage } from "./features/academic/GraduationAuditPage";
import { SchedulePage } from "./features/academic/SchedulePage";
import { SectionResultsDetailPage, SectionResultsPage } from "./features/academic/SectionResultsPages";
import { LoginPage } from "./features/auth/LoginPage";
import { CommunityPage } from "./features/community/CommunityPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { ApprovalsPage } from "./features/operations/ApprovalsPage";
import { ResourcePage } from "./features/resources/ResourcePage";
import { AuditPage } from "./features/settings/AuditPage";
import { AccountPage } from "./features/settings/AccountPage";
import { BulkToolsPage } from "./features/settings/BulkToolsPage";
import { EquivalencesPage } from "./features/settings/EquivalencesPage";
import { AccessSettingsPage } from "./features/settings/AccessSettingsPage";
import { InstitutionSettingsPage } from "./features/settings/InstitutionSettingsPage";
import { PeriodsPage } from "./features/settings/PeriodsPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { api } from "./lib/api";
import { useSessionRenewal } from "./lib/useSessionRenewal";
import { useAuthStore } from "./store/auth";
import type { Role, User } from "./types";
import { Spinner } from "./components/ui";

const StudentProfilePage = lazy(() =>
  import("./features/academic/StudentDossierPage").then(module => ({ default: module.StudentDossierPage })),
);
const TranscriptPage = lazy(() =>
  import("./features/academic/TranscriptPage").then(module => ({ default: module.TranscriptPage })),
);
const GuardianPortalPage = lazy(() =>
  import("./features/guardian/GuardianPortalPage").then(module => ({ default: module.GuardianPortalPage })),
);
const AssessmentsPage = lazy(() =>
  import("./features/academic/AssessmentsPage").then(module => ({ default: module.AssessmentsPage })),
);
const FinancePage = lazy(() =>
  import("./features/finance/FinancePages").then(module => ({ default: module.FinancePage })),
);
const OperationsPage = lazy(() =>
  import("./features/operations/OperationsPage").then(module => ({ default: module.OperationsPage })),
);
const InstitutionalControlPage = lazy(() =>
  import("./features/settings/InstitutionalControlPage").then(module => ({ default: module.InstitutionalControlPage })),
);
const UsersPage = lazy(() => import("./features/settings/UsersPage").then(module => ({ default: module.UsersPage })));
const SectionsPage = lazy(() =>
  import("./features/academic/SectionsPage").then(module => ({ default: module.SectionsPage })),
);

function SessionGate() {
  const { token, user, sessionGeneration, setUser, hydrate } = useAuthStore();
  useSessionRenewal();
  const query = useQuery({
    queryKey: ["session", sessionGeneration],
    queryFn: () => api.get<User>("/auth/me").then(response => response.data),
    enabled: Boolean(token && !user),
    retry: false,
  });
  useEffect(() => {
    if (query.data && token) setUser(query.data);
    if (!token || query.isSuccess || query.isError || user) hydrate();
  }, [query.data, query.isError, query.isSuccess, token, user, setUser, hydrate]);
  if (token && !user && query.isError)
    return (
      <div className="app-loader">
        <p>No pudimos comprobar tu sesión. Revisa la conexión y vuelve a intentar.</p>
        <button type="button" onClick={() => query.refetch()}>
          Reintentar conexión
        </button>
      </div>
    );
  if (token && !user && !query.isError)
    return (
      <div className="app-loader">
        <span className="brand-symbol">N</span>
        <p>Preparando tu espacio…</p>
      </div>
    );
  return <Outlet />;
}

function Protected() {
  const { token, user, hydrated } = useAuthStore();
  const { pathname } = useLocation();
  if (!hydrated) return null;
  if (!token || !user) return <Navigate to="/login" replace />;
  if (isCustomRole(user.role_name) && !["/", "/account"].includes(pathname) && !pathname.startsWith("/modules/"))
    return <Navigate to="/" replace />;
  return <AppShell />;
}

function RoleRoute({ roles }: { roles: Role[] }) {
  const role = useAuthStore(state => state.user?.role_name);
  return role && roles.includes(role) ? <Outlet /> : <Navigate to="/" replace />;
}

function Home() {
  const role = useAuthStore(state => state.user?.role_name);
  if (isCustomRole(role)) return <CustomModuleHome />;
  return role === "guardian" ? <Navigate to="/guardian" replace /> : <DashboardPage />;
}

export default function App() {
  return (
    <Suspense fallback={<Spinner label="Cargando página" />}>
      <Routes>
        <Route element={<SessionGate />}>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Protected />}>
            <Route index element={<Home />} />
            <Route path="modules/:module" element={<CustomModuleRoute />} />
            <Route path="account" element={<AccountPage />} />
            <Route path="approvals" element={<ApprovalsPage />} />
            <Route path="communications" element={<CommunityPage />} />
            <Route element={<RoleRoute roles={["guardian"]} />}>
              <Route path="guardian" element={<GuardianPortalPage />} />
            </Route>
            <Route path="operations" element={<OperationsPage />} />
            <Route path="my-transcript" element={<TranscriptPage />} />
            <Route path="my-grades" element={<MyGradesPage />} />
            <Route path="my-schedule" element={<SchedulePage />} />
            <Route path="my-catalog" element={<CourseCatalogPage />} />
            <Route path="my-attendance" element={<MyAttendancePage />} />
            <Route path="my-progress" element={<MyProgressPage />} />
            <Route path="my-graduation" element={<GraduationAuditPage />} />
            <Route path="my-finance" element={<FinancePage />} />
            <Route element={<RoleRoute roles={["admin", "teacher"]} />}>
              {["students", "sections"].map(key => (
                <Route key={key} path={key} element={key === "students" ? <StudentsPage /> : <SectionsPage />} />
              ))}
              <Route path="grades" element={<SectionResultsPage mode="grades" />} />
              <Route path="attendances" element={<SectionResultsPage mode="attendance" />} />
              <Route path="section-results/:sectionId/:mode" element={<SectionResultsDetailPage />} />
              <Route path="assessments" element={<AssessmentsPage />} />
              <Route path="students/:studentId" element={<StudentProfilePage />} />
              <Route path="students/:studentId/graduation" element={<GraduationAuditPage />} />
              <Route path="sections/:sectionId" element={<SectionWorkspacePage />} />
            </Route>
            <Route element={<RoleRoute roles={["admin"]} />}>
              {["subjects", "roles", "curriculum"].map(key => (
                <Route
                  key={key}
                  path={key}
                  element={key === "subjects" ? <SubjectsPage /> : <ResourcePage config={resources[key]} />}
                />
              ))}
              <Route path="subjects/:subjectId" element={<SubjectProgramPage />} />
              <Route path="teachers" element={<TeachersPage />} />
              <Route path="teachers/:teacherId" element={<TeacherDossierPage />} />
              <Route path="periods" element={<PeriodsPage />} />
              <Route path="careers" element={<CareersPage />} />
              <Route path="careers/:careerId" element={<CareerProgramPage />} />
              <Route path="equivalences" element={<EquivalencesPage />} />
              <Route path="finance" element={<FinancePage />} />
              <Route path="finance/:studentId" element={<FinancePage />} />
              <Route path="institutional-control" element={<InstitutionalControlPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="settings/access" element={<AccessSettingsPage />} />
              <Route path="settings/audit" element={<AuditPage />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="settings/institution" element={<InstitutionSettingsPage />} />
              <Route path="settings/bulk" element={<BulkToolsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
