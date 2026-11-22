import { Wallet } from "lucide-react";
import { EmptyState } from "../../components/ui";
import { useAuthStore } from "../../store/auth";
import { AccountView } from "./AccountView";

/** «Mi cuenta» of the signed-in student. */
export function MyAccountPage() {
  const user = useAuthStore(state => state.user);
  const studentId = user?.student_id;
  if (!studentId)
    return (
      <div className="page">
        <EmptyState
          icon={<Wallet />}
          title="Cuenta no disponible"
          description="Tu usuario no está vinculado a un expediente de estudiante."
        />
      </div>
    );
  return (
    <div className="page payments-page">
      <header className="payments-header">
        <span className="kicker">Mis pagos</span>
        <h1>Mi cuenta</h1>
      </header>
      <AccountView
        studentId={studentId}
        statementPath={`/finance/students/${studentId}/statement`}
      />
    </div>
  );
}
