import { Wallet } from "lucide-react";
import { useParams } from "react-router-dom";
import { EmptyState } from "../../components/ui";
import { useAccess } from "../../lib/permissions";
import { useAuthStore } from "../../store/auth";
import { MyAccountPage } from "../payments/MyAccountPage";
import { FinanceAccounts } from "./FinanceAccounts";
import { StudentFinance } from "./StudentFinance";
import "./finance.css";

export function FinancePage() {
  const user = useAuthStore(s => s.user);
  const { studentId } = useParams();
  const access = useAccess();
  const id = studentId ?? user?.student_id;
  if (access.institution && access.can("finance.view") && !id) return <FinanceAccounts />;
  // A student's own account: the shared, mobile-first view (payments module).
  if (!studentId && user?.student_id) return <MyAccountPage />;
  if (!id || !Number.isInteger(Number(id)) || Number(id) <= 0)
    return (
      <div className="page">
        <EmptyState
          icon={<Wallet />}
          title="Cuenta no disponible"
          description="Selecciona un estudiante con una cuenta válida."
        />
      </div>
    );
  return (
    <StudentFinance
      key={String(id)}
      studentId={Number(id)}
      canManage={access.institution && access.can("finance.manage")}
    />
  );
}
