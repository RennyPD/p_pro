import { DocumentDownload } from "../../components/DocumentDownload";
import { Badge } from "../../components/ui";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDate, formatMoney } from "../../lib/format";
import { Loaded } from "./guardianShared";
import { useGuardianDetail } from "./guardianData";

type Finance = ApiSchema<"GuardianFinance">;
const TYPES: Record<string, string> = {
  charge: "Cargo",
  payment: "Pago",
  adjustment: "Ajuste",
};

export function GuardianFinance({
  studentId,
  enrollmentNumber,
}: {
  studentId: number;
  enrollmentNumber: string;
}) {
  const query = useGuardianDetail<Finance>(studentId, "finance");
  return (
    <Loaded query={query}>
      {data => (
        <>
          <section className="panel guardian-section guardian-lead">
            <div>
              <span className="kicker">Balance pendiente</span>
              <strong className={data.overdue_balance > 0 ? "is-low" : undefined}>
                {formatMoney(data.balance)}
              </strong>
              <small>
                {data.overdue_balance > 0
                  ? `${formatMoney(data.overdue_balance)} vencido`
                  : "Sin montos vencidos"}
              </small>
            </div>
            <div className="guardian-due">
              <span>Próximo vencimiento</span>
              {data.next_due_date ? (
                <>
                  <b>{formatMoney(data.next_due_amount)}</b>
                  <small>{formatDate(data.next_due_date)}</small>
                </>
              ) : data.overdue_balance > 0 ? (
                <b className="is-low">Pago vencido</b>
              ) : (
                <b>Al día</b>
              )}
              {data.financial_responsible && <Badge tone="info">Responsable de pago</Badge>}
            </div>
          </section>

          <section className="panel guardian-section" aria-label="Movimientos">
            <h2>Movimientos</h2>
            {data.transactions.length ? (
              <ul className="guardian-rows">
                {data.transactions.map(item => (
                  <li key={`${item.type}-${item.transaction_id}`}>
                    <div>
                      <strong>{item.description}</strong>
                      <small>
                        {TYPES[item.type] ?? item.type} · {formatDate(item.date)}
                        {item.status !== "posted" && " · Reversado"}
                      </small>
                    </div>
                    <span
                      className={
                        item.direction === "credit"
                          ? "guardian-amount is-credit"
                          : "guardian-amount"
                      }
                    >
                      {item.direction === "credit" ? "−" : ""}
                      {formatMoney(item.amount)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Sin movimientos registrados.</p>
            )}
            <div className="guardian-downloads">
              <DocumentDownload
                path={`/documents/students/${studentId}/statement.pdf`}
                filename={`estado-${enrollmentNumber}.pdf`}
                label="Estado de cuenta PDF"
              />
            </div>
          </section>
        </>
      )}
    </Loaded>
  );
}
