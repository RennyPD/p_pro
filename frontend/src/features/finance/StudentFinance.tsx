import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarClock,
  CalendarCog,
  ClipboardList,
  History,
  Inbox,
  ListChecks,
  Plus,
  Receipt,
  Wallet,
  X,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { Metric, MetricRow, Tabs, type TabItem } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDate } from "../../lib/format";
import { useAuthStore } from "../../store/auth";
import { StatementInstallments } from "../payments/StatementInstallments";
import { AccountDaysDialog, ReasonDialog } from "./FinanceDialogs";
import {
  money,
  type FinanceEvent,
  type FinanceOptions,
  type Plan,
  type Summary,
  type Transaction,
  type Transfer,
} from "./financeData";
import { HistoryTab } from "./HistoryTab";
import { MovementsTab } from "./MovementsTab";
import { PaymentSimulator } from "./PaymentSimulator";
import { PlansTab } from "./PlansTab";
import { RecordMovementPanel } from "./RecordMovementPanel";
import { TransfersTab } from "./TransfersTab";
import "./finance.css";

type Statement = ApiSchema<"AccountStatement">;
type Tab = "installments" | "movements" | "transfers" | "plans" | "history";

/**
 * One student's account for the finance office: what is owed and when first,
 * then installments, movements, transfers, plans and the audit trail.
 */
export function StudentFinance({
  studentId,
  canManage,
}: {
  studentId: number;
  canManage: boolean;
}) {
  const uid = useAuthStore(s => s.user?.user_id);
  const base = `/finance/students/${studentId}`;
  const query = useQuery({
    queryKey: ["finance", uid, studentId],
    queryFn: () => api.get<Summary>(base).then(r => r.data),
  });
  const statement = useQuery({
    queryKey: ["finance", uid, studentId, "statement"],
    queryFn: () => api.get<Statement>(base + "/statement").then(r => r.data),
  });
  const options = useQuery({
    queryKey: ["finance-options", uid],
    queryFn: () => api.get<FinanceOptions>(`/finance/options`).then(r => r.data),
  });
  const transfers = useQuery({
    queryKey: ["finance-transfers", uid, studentId],
    queryFn: () => api.get<Transfer[]>(base + "/transfers").then(r => r.data),
  });
  const plans = useQuery({
    queryKey: ["finance-plans", uid, studentId],
    queryFn: () => api.get<Plan[]>(base + "/payment-plans").then(r => r.data),
  });
  const history = useQuery({
    queryKey: ["finance-history", uid, studentId],
    queryFn: () => api.get<FinanceEvent[]>(base + "/history").then(r => r.data),
    enabled: canManage,
  });
  const [tab, setTab] = useState<Tab>("installments");
  const [office, setOffice] = useState(false);
  const [editingDays, setEditingDays] = useState(false);
  const [review, setReview] = useState<Transfer>();
  const [reverse, setReverse] = useState<Transaction>();
  const [cancelPlan, setCancelPlan] = useState<Plan>();
  if (query.isLoading)
    return (
      <div className="page">
        <Spinner />
      </div>
    );
  if (query.error || !query.data)
    return (
      <div className="page">
        <EmptyState
          icon={<Wallet />}
          title="No pudimos cargar la cuenta"
          description={apiMessage(query.error)}
        />
      </div>
    );
  const data = query.data;
  const pending = (transfers.data ?? []).filter(item => item.status === "pending").length;
  const overdue = data.overdue_balance > 0;
  const tabs: TabItem<Tab>[] = [
    { key: "installments", label: "Cuotas", icon: <ListChecks /> },
    { key: "movements", label: "Movimientos", icon: <Receipt /> },
    { key: "transfers", label: "Transferencias", icon: <Inbox />, count: pending },
    { key: "plans", label: "Planes de pago", icon: <ClipboardList /> },
    ...(canManage ? [{ key: "history" as const, label: "Auditoría", icon: <History /> }] : []),
  ];
  const closeDialogs = () => {
    setReview(undefined);
    setReverse(undefined);
    setCancelPlan(undefined);
  };

  return (
    <div className="page finance-page">
      {canManage && (
        <Link to="/finance" className="back-link">
          <ArrowLeft /> Cuentas
        </Link>
      )}
      <header className="finance-account-header">
        <div>
          <span className="kicker">Cuenta estudiantil · RD$</span>
          <h1>{data.student_name}</h1>
          <p>
            {data.enrollment_number} · Corte día {data.cutoff_day} · Vencimiento sugerido día{" "}
            {data.due_day}
          </p>
        </div>
        {canManage && (
          <div className="section-heading__actions">
            <Button variant="secondary" onClick={() => setEditingDays(true)}>
              <CalendarCog size={16} /> Días de la cuenta
            </Button>
            <Button aria-expanded={office} onClick={() => setOffice(open => !open)}>
              {office ? <X size={16} /> : <Plus size={16} />}{" "}
              {office ? "Cerrar registro" : "Registrar movimiento"}
            </Button>
          </div>
        )}
      </header>

      <MetricRow label="Resumen de la cuenta">
        <Metric
          label="Balance pendiente"
          value={money(data.balance)}
          tone={overdue ? "danger" : "default"}
          icon={<Wallet />}
        />
        <Metric
          label="Vencido"
          value={money(data.overdue_balance)}
          note={overdue ? "Requiere gestión de cobro" : "Sin atrasos"}
          tone={overdue ? "danger" : "success"}
        />
        <Metric
          label="Próximo vencimiento"
          value={
            statement.data?.next_due_date ? money(statement.data.next_due_amount ?? 0) : "Al día"
          }
          note={
            statement.data?.next_due_date
              ? formatDate(statement.data.next_due_date)
              : "Sin cuotas futuras"
          }
          icon={<CalendarClock />}
        />
        <Metric
          label="Transferencias por revisar"
          value={pending}
          note={pending ? "Pendientes de confirmar en el banco" : "Ninguna"}
          tone={pending ? "warning" : "default"}
          onClick={pending ? () => setTab("transfers") : undefined}
        />
      </MetricRow>

      {canManage && office && (
        <RecordMovementPanel studentId={studentId} dueDay={data.due_day} balance={data.balance} />
      )}

      <Tabs
        label="Vistas de la cuenta"
        items={tabs}
        value={tab}
        onChange={setTab}
        panelId="finance-account-panel"
      />
      <div id="finance-account-panel" role="tabpanel" className="finance-account-panel">
        {tab === "installments" &&
          (statement.isPending ? (
            <Spinner />
          ) : statement.isError ? (
            <p className="form-error">{apiMessage(statement.error)}</p>
          ) : (
            <StatementInstallments obligations={statement.data.obligations} />
          ))}
        {tab === "movements" && (
          <MovementsTab
            transactions={data.transactions}
            canManage={canManage}
            onReverse={setReverse}
          />
        )}
        {tab === "transfers" && (
          <TransfersTab transfers={transfers} canManage={canManage} onReview={setReview} />
        )}
        {tab === "plans" && (
          <PlansTab
            studentId={studentId}
            plans={plans}
            balance={data.balance}
            canManage={canManage}
            onCancel={setCancelPlan}
          />
        )}
        {tab === "history" && canManage && <HistoryTab history={history} />}
      </div>

      {canManage && options.data?.simulator_enabled && <PaymentSimulator studentId={studentId} />}
      {editingDays && (
        <AccountDaysDialog
          studentId={studentId}
          cutoffDay={data.cutoff_day}
          dueDay={data.due_day}
          onClose={() => setEditingDays(false)}
        />
      )}
      {(review || reverse || cancelPlan) && (
        <ReasonDialog
          studentId={studentId}
          review={review}
          reverse={reverse}
          cancelPlan={cancelPlan}
          onClose={closeDialogs}
        />
      )}
    </div>
  );
}
