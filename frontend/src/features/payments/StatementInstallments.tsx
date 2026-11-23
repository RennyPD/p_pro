import { useState } from "react";
import { Badge, Button } from "../../components/ui";
import { formatDate, formatMoney } from "../../lib/format";
import { obligationStatus, type Obligation } from "./paymentsData";
import "./payments.css";

/** Installments of an account with their status; paid ones on demand. */
export function StatementInstallments({ obligations }: { obligations: Obligation[] }) {
  const [showPaid, setShowPaid] = useState(false);
  const unpaid = obligations.filter(item => item.status !== "paid");
  const shown = showPaid ? obligations : unpaid;
  return (
    <section className="panel payments-section" aria-label="Cuotas">
      <div className="payments-heading">
        <h2>Cuotas</h2>
        {obligations.length > unpaid.length && (
          <Button variant="ghost" onClick={() => setShowPaid(value => !value)}>
            {showPaid ? "Ocultar pagadas" : "Ver pagadas"}
          </Button>
        )}
      </div>
      {shown.length ? (
        <ul className="payments-list">
          {shown.map(item => {
            const state = obligationStatus[item.status] ?? obligationStatus.pending;
            return (
              <li key={`${item.type}-${item.obligation_id}`}>
                <div>
                  <strong>{item.description}</strong>
                  <small>
                    {item.concept !== item.description && `${item.concept} · `}
                    vence {formatDate(item.due_date)}
                    {item.status !== "paid" &&
                      item.paid_amount > 0 &&
                      ` · abonado ${formatMoney(item.paid_amount)}`}
                  </small>
                </div>
                <div className="payments-figure">
                  <b>{formatMoney(item.status === "paid" ? item.amount : item.remaining)}</b>
                  <Badge tone={state.tone}>{state.label}</Badge>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="muted">No hay cuotas pendientes.</p>
      )}
    </section>
  );
}
