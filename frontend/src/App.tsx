import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { resources } from "./config/resources";
import { MyAttendancePage, MyGradesPage, MyProgressPage, SectionWorkspacePage } from "./features/academic/AcademicPages";
import { StudentDossierPage as StudentProfilePage } from "./features/academic/StudentDossierPage";
import { TeachersPage } from "./features/academic/TeachersPage";
import { TeacherDossierPage } from "./features/academic/TeacherDossierPage";
import { StudentsPage } from "./features/academic/StudentsPage";
import { AssessmentsPage } from "./features/academic/AssessmentsPage";
import { SubjectsPage } from "./features/academic/SubjectsPage";
import { SubjectProgramPage } from "./features/academic/SubjectProgramPage";
import { CareersPage } from "./features/academic/CareersPage";
import { CareerProgramPage } from "./features/academic/CareerProgramPage";
import { CourseCatalogPage } from "./features/academic/CourseCatalogPage";
import { GraduationAuditPage } from "./features/academic/GraduationAuditPage";
import { SchedulePage } from "./features/academic/SchedulePage";
import { SectionResultsDetailPage, SectionResultsPage } from "./features/academic/SectionResultsPages";
import { TranscriptPage } from "./features/academic/TranscriptPage";
import { LoginPage } from "./features/auth/LoginPage";
import { CommunityPage } from "./features/community/CommunityPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { FinancePage } from "./features/finance/FinancePages";
import { GuardianPortalPage } from "./features/guardian/GuardianPortalPage";
import { OperationsPage } from "./features/operations/OperationsPage";
import { ResourcePage } from "./features/resources/ResourcePage";
import { AccountPage } from "./features/settings/AccountPage";
import { BulkToolsPage } from "./features/settings/BulkToolsPage";
import { EquivalencesPage } from "./features/settings/EquivalencesPage";
import { AccessSettingsPage } from "./features/settings/AccessSettingsPage";
import { InstitutionSettingsPage } from "./features/settings/InstitutionSettingsPage";
import { InstitutionalControlPage } from "./features/settings/InstitutionalControlPage";
import { PeriodsPage } from "./features/settings/PeriodsPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { api } from "./lib/api";
import { useAuthStore } from "./store/auth";
import type { Role, User } from "./types";

function SessionGate() {
  const { token, user, setUser, clearSession, hydrate } = useAuthStore();
  const query = useQuery({ queryKey: ["session"], queryFn: () => api.get<User>("/auth/me").then(response => response.data), enabled: Boolean(token && !user), retry: false });
  useEffect(() => { if (query.data) setUser(query.data); if (query.isError) clearSession(); if (!token || query.isSuccess || query.isError || user) hydrate(); }, [query.data, query.isError, query.isSuccess, token, user, setUser, clearSession, hydrate]);
  if (token && !user && !query.isError) return <div className="app-loader"><span className="brand-symbol">N</span><p>Preparando tu espacio…</p></div>;
  return <Outlet />;
}

function Protected() {
  const { token, user, hydrated } = useAuthStore();
  if (!hydrated) return null;
  if (!token || !user) return <Navigate to="/login" replace />;
  return <AppShell />;
}

function RoleRoute({ roles }: { roles: Role[] }) {
  const role = useAuthStore(state => state.user?.role_name);
  return role && roles.includes(role) ? <Outlet /> : <Navigate to="/" replace />;
}

function Home() {
  const role = useAuthStore(state => state.user?.role_name);
  return role === "guardian" ? <Navigate to="/guardian" replace /> : <DashboardPage />;
}

export default function App() {
  return <Routes><Route element={<SessionGate />}><Route path="/login" element={<LoginPage />} /><Route element={<Protected />}><Route index element={<Home />} /><Route path="account" element={<AccountPage />} /><Route path="communications" element={<CommunityPage />} /><Route element={<RoleRoute roles={["guardian"]} />}><Route path="guardian" element={<GuardianPortalPage />} /></Route><Route path="operations" element={<OperationsPage />} /><Route path="my-transcript" element={<TranscriptPage />} /><Route path="my-grades" element={<MyGradesPage />} /><Route path="my-schedule" element={<SchedulePage />} /><Route path="my-catalog" element={<CourseCatalogPage />} /><Route path="my-attendance" element={<MyAttendancePage />} /><Route path="my-progress" element={<MyProgressPage />} /><Route path="my-graduation" element={<GraduationAuditPage />} /><Route path="my-finance" element={<FinancePage />} /><Route element={<RoleRoute roles={["admin", "teacher"]} />}>{["students", "sections"].map(key => <Route key={key} path={key} element={key === "students" ? <StudentsPage /> : <ResourcePage config={resources[key]} />} />)}<Route path="grades" element={<SectionResultsPage mode="grades" />} /><Route path="attendances" element={<SectionResultsPage mode="attendance" />} /><Route path="section-results/:sectionId/:mode" element={<SectionResultsDetailPage />} /><Route path="assessments" element={<AssessmentsPage />} /><Route path="students/:studentId" element={<StudentProfilePage />} /><Route path="students/:studentId/graduation" element={<GraduationAuditPage />} /><Route path="sections/:sectionId" element={<SectionWorkspacePage />} /></Route><Route element={<RoleRoute roles={["admin"]} />}>{["subjects", "roles", "users", "curriculum"].map(key => <Route key={key} path={key} element={key === "subjects" ? <SubjectsPage /> : <ResourcePage config={resources[key]} />} />)}<Route path="subjects/:subjectId" element={<SubjectProgramPage />} /><Route path="teachers" element={<TeachersPage />} /><Route path="teachers/:teacherId" element={<TeacherDossierPage />} /><Route path="periods" element={<PeriodsPage />} /><Route path="careers" element={<CareersPage />} /><Route path="careers/:careerId" element={<CareerProgramPage />} /><Route path="equivalences" element={<EquivalencesPage />} /><Route path="finance" element={<FinancePage />} /><Route path="finance/:studentId" element={<FinancePage />} /><Route path="institutional-control" element={<InstitutionalControlPage />} /><Route path="settings" element={<SettingsPage />} /><Route path="settings/access" element={<AccessSettingsPage />} /><Route path="settings/institution" element={<InstitutionSettingsPage />} /><Route path="settings/bulk" element={<BulkToolsPage />} /></Route><Route path="*" element={<Navigate to="/" replace />} /></Route></Route></Routes>;
}
