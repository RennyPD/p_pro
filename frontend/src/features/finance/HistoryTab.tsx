import { type UseQueryResult } from "@tanstack/react-query";
import { apiMessage } from "../../lib/api";
import { auditDetail, auditNames, dateLabel, type FinanceEvent } from "./financeData";
import "./finance.css";

export function HistoryTab({ history }: { history: UseQueryResult<FinanceEvent[]> }) {
  return (
    <section className="panel">
      <h2>Auditoría financiera</h2>
      <p className="muted">
        Autor, fecha y detalle de las operaciones registradas desde esta mejora. No se inventan
        autores para movimientos antiguos.
      </p>
      {history.error && <p className="form-error">{apiMessage(history.error)}</p>}
      <div className="finance-mini-list">
        {history.data?.map(h => (
          <article key={h.id}>
            <strong>
              {auditNames[h.action] || h.action} · {h.actor}
            </strong>
            <small>{dateLabel(h.created_at)}</small>
            <p>{auditDetail(h.detail)}</p>
          </article>
        ))}
      </div>
      {history.data?.length === 0 && <p className="muted">Todavía no hay eventos auditados.</p>}
    </section>
  );
}
