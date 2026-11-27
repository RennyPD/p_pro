import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { resources } from "./config/resources";
import { LoginPage } from "./features/auth/LoginPage";
import { api } from "./lib/api";
import { useSessionRenewal } from "./lib/useSessionRenewal";
import { useAuthStore } from "./store/auth";
import type { User } from "./types";
import { useAccess } from "./lib/permissions";
import { Spinner } from "./components/ui";

const CustomModuleRoute = lazy(() =>
  import("./features/settings/CustomModulePage").then(module => ({
    default: module.CustomModuleRoute,
  })),
);
const MyAttendancePage = lazy(() =>
  import("./features/academic/AcademicPages").then(module => ({
    default: module.MyAttendancePage,
  })),
);
const MyGradesPage = lazy(() =>
  import("./features/academic/AcademicPages").then(module => ({ default: module.MyGradesPage })),
);
const MyProgressPage = lazy(() =>
  import("./features/academic/AcademicPages").then(module => ({ default: module.MyProgressPage })),
);
const SectionWorkspacePage = lazy(() =>
  import("./features/academic/AcademicPages").then(module => ({
    default: module.SectionWorkspacePage,
  })),
);
const TeachersPage = lazy(() =>
  import("./features/academic/TeachersPage").then(module => ({ default: module.TeachersPage })),
);
const TeacherDossierPage = lazy(() =>
  import("./features/academic/TeacherDossierPage").then(module => ({
    default: module.TeacherDossierPage,
  })),
);
const StudentsPage = lazy(() =>
  import("./features/academic/StudentsPage").then(module => ({ default: module.StudentsPage })),
);
const SubjectsPage = lazy(() =>
  import("./features/academic/SubjectsPage").then(module => ({ default: module.SubjectsPage })),
);
const SubjectProgramPage = lazy(() =>
  import("./features/academic/SubjectProgramPage").then(module => ({
    default: module.SubjectProgramPage,
  })),
);
const CareersPage = lazy(() =>
  import("./features/academic/CareersPage").then(module => ({ default: module.CareersPage })),
);
const CareerProgramPage = lazy(() =>
  import("./features/academic/CareerProgramPage").then(module => ({
    default: module.CareerProgramPage,
  })),
);
const CourseCatalogPage = lazy(() =>
  import("./features/academic/CourseCatalogPage").then(module => ({
    default: module.CourseCatalogPage,
  })),
);
const GraduationAuditPage = lazy(() =>
  import("./features/academic/GraduationAuditPage").then(module => ({
    default: module.GraduationAuditPage,
  })),
);
const SchedulePage = lazy(() =>
  import("./features/academic/SchedulePage").then(module => ({ default: module.SchedulePage })),
);
const SectionResultsDetailPage = lazy(() =>
  import("./features/academic/SectionResultsPages").then(module => ({
    default: module.SectionResultsDetailPage,
  })),
);
const SectionResultsPage = lazy(() =>
  import("./features/academic/SectionResultsPages").then(module => ({
    default: module.SectionResultsPage,
  })),
);
const ChoosePasswordPage = lazy(() =>
  import("./features/auth/PasswordPages").then(module => ({ default: module.ChoosePasswordPage })),
);
const ForgotPasswordPage = lazy(() =>
  import("./features/auth/PasswordPages").then(module => ({ default: module.ForgotPasswordPage })),
);
const CommunityPage = lazy(() =>
  import("./features/community/CommunityPage").then(module => ({ default: module.CommunityPage })),
);
const DashboardPage = lazy(() =>
  import("./features/dashboard/DashboardPage").then(module => ({ default: module.DashboardPage })),
);
const ApprovalsPage = lazy(() =>
  import("./features/operations/ApprovalsPage").then(module => ({ default: module.ApprovalsPage })),
);
const ResourcePage = lazy(() =>
  import("./features/resources/ResourcePage").then(module => ({ default: module.ResourcePage })),
);
const AuditPage = lazy(() =>
  import("./features/settings/AuditPage").then(module => ({ default: module.AuditPage })),
);
const AccountPage = lazy(() =>
  import("./features/settings/AccountPage").then(module => ({ default: module.AccountPage })),
);
const BulkToolsPage = lazy(() =>
  import("./features/settings/BulkToolsPage").then(module => ({ default: module.BulkToolsPage })),
);
const EquivalencesPage = lazy(() =>
  import("./features/settings/EquivalencesPage").then(module => ({
    default: module.EquivalencesPage,
  })),
);
const RolesPage = lazy(() =>
  import("./features/settings/RolesPage").then(module => ({ default: module.RolesPage })),
);
const InstitutionSettingsPage = lazy(() =>
  import("./features/settings/InstitutionSettingsPage").then(module => ({
    default: module.InstitutionSettingsPage,
  })),
);
const PeriodsPage = lazy(() =>
  import("./features/settings/PeriodsPage").then(module => ({ default: module.PeriodsPage })),
);
const GradingScalesPage = lazy(() =>
  import("./features/settings/GradingScalesPage").then(module => ({
    default: module.GradingScalesPage,
  })),
);
const ClassGroupPage = lazy(() =>
  import("./features/groups/ClassGroupPage").then(module => ({ default: module.ClassGroupPage })),
);
const ClassGroupsPage = lazy(() =>
  import("./features/groups/ClassGroupsPage").then(module => ({ default: module.ClassGroupsPage })),
);
const SettingsPage = lazy(() =>
  import("./features/settings/SettingsPage").then(module => ({ default: module.SettingsPage })),
);
const StudentProfilePage = lazy(() =>
  import("./features/academic/StudentDossierPage").then(module => ({
    default: module.StudentDossierPage,
  })),
);
const TranscriptPage = lazy(() =>
  import("./features/academic/TranscriptPage").then(module => ({ default: module.TranscriptPage })),
);
const GuardianPortalPage = lazy(() =>
  import("./features/guardian/GuardianPortalPage").then(module => ({
    default: module.GuardianPortalPage,
  })),
);
const AssessmentsPage = lazy(() =>
  import("./features/academic/AssessmentsPage").then(module => ({
    default: module.AssessmentsPage,
  })),
);
const FinancePage = lazy(() =>
  import("./features/finance/FinancePages").then(module => ({ default: module.FinancePage })),
);
const BillingPlansPage = lazy(() =>
  import("./features/finance/BillingPlansPage").then(module => ({
    default: module.BillingPlansPage,
  })),
);
const FinanceReportsPage = lazy(() =>
  import("./features/finance/FinanceReportsPage").then(module => ({
    default: module.FinanceReportsPage,
  })),
);
const FinancePolicyPage = lazy(() =>
  import("./features/finance/FinancePolicyPage").then(module => ({
    default: module.FinancePolicyPage,
  })),
);
const OperationsPage = lazy(() =>
  import("./features/operations/OperationsPage").then(module => ({
    default: module.OperationsPage,
  })),
);
const InstitutionalControlPage = lazy(() =>
  import("./features/settings/InstitutionalControlPage").then(module => ({
    default: module.InstitutionalControlPage,
  })),
);
const UsersPage = lazy(() =>
  import("./features/settings/UsersPage").then(module => ({ default: module.UsersPage })),
);
const BillingPage = lazy(() =>
  import("./features/billing/BillingPage").then(module => ({ default: module.BillingPage })),
);
const SandboxCheckoutPage = lazy(() =>
  import("./features/billing/SandboxCheckoutPage").then(module => ({
    default: module.SandboxCheckoutPage,
  })),
);
const OnlinePaymentResultPage = lazy(() =>
  import("./features/payments/OnlinePaymentPages").then(module => ({
    default: module.OnlinePaymentResultPage,
  })),
);
const SandboxGatewayPage = lazy(() =>
  import("./features/payments/OnlinePaymentPages").then(module => ({
    default: module.SandboxGatewayPage,
  })),
);
const OnlinePaymentsAdminPage = lazy(() =>
  import("./features/payments/OnlinePaymentsAdminPage").then(module => ({
    default: module.OnlinePaymentsAdminPage,
  })),
);
const FiscalPage = lazy(() =>
  import("./features/fiscal/FiscalPage").then(module => ({ default: module.FiscalPage })),
);
const DemoPage = lazy(() =>
  import("./features/demo/DemoPage").then(module => ({ default: module.DemoPage })),
);
const LegalPage = lazy(() =>
  import("./features/legal/LegalPage").then(module => ({ default: module.LegalPage })),
);
const SignupPage = lazy(() =>
  import("./features/signup/SignupPage").then(module => ({ default: module.SignupPage })),
);
const PlatformPage = lazy(() =>
  import("./features/platform/PlatformPage").then(module => ({ default: module.PlatformPage })),
);
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
  if (!hydrated) return null;
  if (!token || !user) return <Navigate to="/login" replace />;
  return <AppShell />;
}

type Access = ReturnType<typeof useAccess>;

/** Renders its routes only when the account's permissions and scope allow it. */
function Allow({ when }: { when: (access: Access) => boolean }) {
  const access = useAccess();
  if (!access.ready) return <Spinner label="Comprobando permisos" />;
  return when(access) ? <Outlet /> : <Navigate to="/" replace />;
}
const staff = (a: Access) => a.institution || a.teaching;
const institution =
  (...slugs: string[]) =>
  (a: Access) =>
    a.institution && a.canAny(...slugs);

function Home() {
  const access = useAccess();
  if (!access.ready) return <Spinner label="Preparando tu espacio" />;
  return access.guardian ? <Navigate to="/guardian" replace /> : <DashboardPage />;
}

export default function App() {
  return (
    <Suspense fallback={<Spinner label="Cargando página" />}>
      <Routes>
        <Route path="/plataforma" element={<PlatformPage />} />
        <Route element={<SessionGate />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/recuperar" element={<ForgotPasswordPage />} />
          <Route path="/registro" element={<SignupPage />} />
          <Route path="/legal/:slug" element={<LegalPage />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/pagos/resultado" element={<OnlinePaymentResultPage />} />
          <Route path="/pagos/sandbox" element={<SandboxGatewayPage />} />
          <Route path="/restablecer" element={<ChoosePasswordPage mode="reset" />} />
          <Route path="/activar" element={<ChoosePasswordPage mode="activate" />} />
          <Route element={<Protected />}>
            <Route index element={<Home />} />
            <Route path="modules/:module" element={<CustomModuleRoute />} />
            <Route path="account" element={<AccountPage />} />
            <Route path="approvals" element={<ApprovalsPage />} />
            <Route path="communications" element={<CommunityPage />} />
            <Route element={<Allow when={a => a.guardian && a.can("records.own")} />}>
              <Route path="guardian" element={<GuardianPortalPage />} />
            </Route>
            <Route path="operations" element={<OperationsPage />} />
            <Route path="my-schedule" element={<SchedulePage />} />
            <Route element={<Allow when={a => a.student && a.can("records.own")} />}>
              <Route path="my-transcript" element={<TranscriptPage />} />
              <Route path="my-grades" element={<MyGradesPage />} />
              <Route path="my-attendance" element={<MyAttendancePage />} />
              <Route path="my-progress" element={<MyProgressPage />} />
              <Route path="my-graduation" element={<GraduationAuditPage />} />
              <Route path="my-finance" element={<FinancePage />} />
            </Route>
            <Route element={<Allow when={a => a.student && a.can("selection.own")} />}>
              <Route path="my-catalog" element={<CourseCatalogPage />} />
            </Route>
            <Route
              element={
                <Allow when={a => staff(a) && a.canAny("students.view", "students.manage")} />
              }
            >
              <Route path="students" element={<StudentsPage />} />
              <Route path="students/:studentId" element={<StudentProfilePage />} />
              <Route path="students/:studentId/graduation" element={<GraduationAuditPage />} />
            </Route>
            <Route
              element={
                <Allow when={a => staff(a) && a.canAny("sections.view", "sections.manage")} />
              }
            >
              <Route path="sections" element={<SectionsPage />} />
              <Route path="sections/:sectionId" element={<SectionWorkspacePage />} />
            </Route>
            <Route element={<Allow when={a => staff(a) && a.can("grades.manage")} />}>
              <Route path="assessments" element={<AssessmentsPage />} />
            </Route>
            <Route
              element={
                <Allow
                  when={a =>
                    staff(a) &&
                    a.canAny("grades.view", "grades.manage", "attendance.view", "attendance.manage")
                  }
                />
              }
            >
              <Route path="grades" element={<SectionResultsPage mode="grades" />} />
              <Route path="attendances" element={<SectionResultsPage mode="attendance" />} />
              <Route
                path="section-results/:sectionId/:mode"
                element={<SectionResultsDetailPage />}
              />
            </Route>
            <Route element={<Allow when={institution("programs.manage")} />}>
              <Route path="careers" element={<CareersPage />} />
              <Route path="careers/:careerId" element={<CareerProgramPage />} />
              <Route path="subjects" element={<SubjectsPage />} />
              <Route path="subjects/:subjectId" element={<SubjectProgramPage />} />
              <Route path="curriculum" element={<ResourcePage config={resources.curriculum} />} />
            </Route>
            <Route element={<Allow when={institution("teachers.view", "teachers.manage")} />}>
              <Route path="teachers" element={<TeachersPage />} />
              <Route path="teachers/:teacherId" element={<TeacherDossierPage />} />
            </Route>
            <Route
              element={
                <Allow
                  when={a =>
                    staff(a) && a.canAny("sections.view", "sections.manage", "enrollments.manage")
                  }
                />
              }
            >
              <Route path="class-groups" element={<ClassGroupsPage />} />
              <Route path="class-groups/:groupId" element={<ClassGroupPage />} />
            </Route>
            <Route element={<Allow when={institution("equivalences.manage")} />}>
              <Route path="equivalences" element={<EquivalencesPage />} />
            </Route>
            <Route element={<Allow when={institution("finance.view", "reports.view")} />}>
              <Route path="finance/reports" element={<FinanceReportsPage />} />
            </Route>
            <Route element={<Allow when={institution("finance.view")} />}>
              <Route path="finance" element={<FinancePage />} />
              <Route path="finance/plans" element={<BillingPlansPage />} />
              <Route path="finance/policy" element={<FinancePolicyPage />} />
              <Route path="finance/online" element={<OnlinePaymentsAdminPage />} />
              <Route path="finance/fiscal" element={<FiscalPage />} />
              <Route path="finance/:studentId" element={<FinancePage />} />
            </Route>
            <Route
              element={
                <Allow when={institution("reports.view", "cases.manage", "admissions.manage")} />
              }
            >
              <Route path="institutional-control" element={<InstitutionalControlPage />} />
            </Route>
            <Route
              element={
                <Allow
                  when={institution(
                    "settings.manage",
                    "users.manage",
                    "roles.manage",
                    "audit.view",
                    "students.manage",
                  )}
                />
              }
            >
              <Route path="settings" element={<SettingsPage />} />
            </Route>
            <Route element={<Allow when={institution("settings.manage")} />}>
              <Route path="periods" element={<PeriodsPage />} />
              <Route path="settings/institution" element={<InstitutionSettingsPage />} />
              <Route path="settings/grading-scales" element={<GradingScalesPage />} />
            </Route>
            <Route element={<Allow when={institution("billing.manage")} />}>
              <Route path="billing" element={<BillingPage />} />
              <Route path="billing/sandbox" element={<SandboxCheckoutPage />} />
            </Route>
            <Route element={<Allow when={institution("roles.manage")} />}>
              <Route path="roles" element={<RolesPage />} />
              <Route path="settings/access" element={<Navigate to="/roles" replace />} />
            </Route>
            <Route element={<Allow when={institution("users.manage")} />}>
              <Route path="users" element={<UsersPage />} />
            </Route>
            <Route element={<Allow when={institution("audit.view")} />}>
              <Route path="settings/audit" element={<AuditPage />} />
            </Route>
            <Route element={<Allow when={institution("students.manage")} />}>
              <Route path="settings/bulk" element={<BulkToolsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
