import { useQuery } from "@tanstack/react-query";
import { CalendarClock, Receipt, Send } from "lucide-react";
import { useState } from "react";
import { DocumentDownload } from "../../components/DocumentDownload";
import { Badge, Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { formatDate, formatDateTime, formatMoney } from "../../lib/format";
import {
  obligationStatus,
  paymentMethods,
  transferStatus,
  type FinanceOptions,
  type Statement,
  type Transfer,
} from "./paymentsData";
import { StatementInstallments } from "./StatementInstallments";
import { TransferDialog } from "./TransferDialog";
import "./payments.css";

/**
 * Account of one student for the student and the guardian: what to pay next,
 * installments with their status, receipts and reported transfers.
 */
export function AccountView({
  studentId,
  statementPath,
}: {
  studentId: number;
  statementPath: string;
}) {
  const [reporting, setReporting] = useState(false);
  const statement = useQuery({
    queryKey: ["payments", "statement", studentId, statementPath],
    queryFn: () => api.get<Statement>(statementPath).then(response => response.data),
  });
  const transfers = useQuery({
    queryKey: ["payments", "transfers", studentId],
    queryFn: () =>
      api
        .get<Transfer[]>(`/finance/students/${studentId}/transfers`)
        .then(response => response.data),
  });
  const options = useQuery({
    queryKey: ["payments", "options"],
    queryFn: () => api.get<FinanceOptions>("/finance/options").then(response => response.data),
  });

  if (statement.isPending) return <Spinner />;
  if (statement.isError)
    return (
      <EmptyState
        icon={<Receipt />}
        title="No pudimos cargar la cuenta"
        description={apiMessage(statement.error)}
      />
    );
  const data = statement.data;
  const overdue = data.overdue_balance > 0;
  const instructions = options.data?.transfer_instructions ?? "";
  const suggested = overdue ? data.overdue_balance : (data.next_due_amount ?? data.balance);

  return (
    <div className="payments-account">
      <section className="panel payments-lead" aria-label="Resumen de la cuenta">
        <div>
          <span className="kicker">Balance pendiente</span>
          <strong className={overdue ? "is-low" : undefined}>{formatMoney(data.balance)}</strong>
          <small>
            {overdue ? `${formatMoney(data.overdue_balance)} vencido` : "Sin montos vencidos"}
          </small>
        </div>
        <div className="payments-next">
          <CalendarClock aria-hidden="true" />
          <div>
            <span>{overdue ? "Pagar ahora" : "Próximo vencimiento"}</span>
            {overdue ? (
              <b className="is-low">{formatMoney(data.overdue_balance)}</b>
            ) : data.next_due_date ? (
              <>
                <b>{formatMoney(data.next_due_amount)}</b>
                <small>{formatDate(data.next_due_date)}</small>
              </>
            ) : (
              <b>Al día</b>
            )}
          </div>
        </div>
        {data.balance > 0 && instructions && (
          <Button className="payments-action" onClick={() => setReporting(true)}>
            <Send size={16} /> Reportar pago
          </Button>
        )}
        {data.balance > 0 && options.isSuccess && !instructions && (
          <p className="muted payments-action">
            La institución aún no publicó sus datos bancarios. Paga en caja.
          </p>
        )}
      </section>

      <StatementInstallments obligations={data.obligations} />

      {data.payment_plans.map(plan => (
        <section key={plan.payment_plan_id} className="panel payments-section">
          <h2>Plan de pago · {plan.name}</h2>
          <ul className="payments-list">
            {plan.installments.map(item => {
              const state = obligationStatus[item.status] ?? obligationStatus.pending;
              return (
                <li key={item.installment_id}>
                  <div>
                    <strong>{formatDate(item.due_date)}</strong>
                    {item.status === "partial" && (
                      <small>abonado {formatMoney(item.paid_amount)}</small>
                    )}
                  </div>
                  <div className="payments-figure">
                    <b>{formatMoney(item.amount)}</b>
                    <Badge tone={state.tone}>{state.label}</Badge>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      <section className="panel payments-section" aria-label="Pagos y recibos">
        <h2>Pagos y recibos</h2>
        {data.payments.length ? (
          <ul className="payments-list">
            {data.payments.map(payment => (
              <li key={payment.payment_id}>
                <div>
                  <strong>{formatMoney(payment.amount)}</strong>
                  <small>
                    {paymentMethods[payment.method] ?? payment.method} ·{" "}
                    {formatDate(payment.paid_at)} · {payment.reference}
                  </small>
                </div>
                <DocumentDownload
                  path={`/finance/payments/${payment.payment_id}/receipt.pdf`}
                  filename={`recibo-${payment.receipt_number ?? payment.payment_id}.pdf`}
                  label="Recibo"
                  accessibleLabel={`Recibo del pago de ${formatMoney(payment.amount)}`}
                />
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Todavía no hay pagos registrados.</p>
        )}
        <div className="payments-downloads">
          <DocumentDownload
            path={`/documents/students/${studentId}/statement.pdf`}
            filename={`estado-${data.enrollment_number}.pdf`}
            label="Estado de cuenta PDF"
          />
        </div>
      </section>

      {transfers.data && transfers.data.length > 0 && (
        <section className="panel payments-section" aria-label="Pagos reportados">
          <h2>Pagos reportados</h2>
          <ul className="payments-list">
            {transfers.data.map(item => {
              const state = transferStatus[item.status] ?? transferStatus.pending;
              return (
                <li key={item.transfer_request_id}>
                  <div>
                    <strong>
                      {formatMoney(item.amount)} · {item.batch_reference ?? item.reference}
                    </strong>
                    <small>
                      {item.bank} · {formatDateTime(item.submitted_at)}
                      {item.batch_size && item.batch_size > 1
                        ? ` · parte de un pago familiar de ${formatMoney(item.batch_total)}`
                        : ""}
                    </small>
                    {item.review_reason && item.status === "rejected" && (
                      <small className="is-low">{item.review_reason}</small>
                    )}
                  </div>
                  <Badge tone={state.tone}>{state.label}</Badge>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {reporting && (
        <TransferDialog
          studentId={studentId}
          instructions={instructions}
          suggested={suggested}
          balance={data.balance}
          onClose={() => setReporting(false)}
        />
      )}
    </div>
  );
}
