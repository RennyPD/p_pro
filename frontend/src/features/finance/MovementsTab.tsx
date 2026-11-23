import { ArrowDownLeft, ArrowUpRight, Download, SlidersHorizontal, Undo2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button } from "../../components/ui";
import { dateLabel, download, labels, money, type Transaction } from "./financeData";
import "./finance.css";

export function MovementsTab({
  transactions,
  canManage,
  onReverse,
}: {
  transactions: Transaction[];
  canManage: boolean;
  onReverse: (item: Transaction) => void;
}) {
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("");
  const movements = transactions.filter(
    t =>
      (!filterType || t.type === filterType) &&
      `${t.description} ${t.receipt_number || ""}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Movimientos</h2>
        <span className="muted">
          {movements.length} {movements.length === 1 ? "movimiento" : "movimientos"}
        </span>
      </div>
      <div className="finance-filters">
        <label className="form-field">
          <span>Buscar movimientos</span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Concepto, referencia o recibo"
          />
        </label>
        <label className="form-field">
          <span>Tipo de movimiento</span>
          <select value={filterType} onChange={e => setFilterType(e.target.value)}>
            <option value="">Todos</option>
            {["charge", "payment", "adjustment"].map(t => (
              <option key={t} value={t}>
                {labels[t]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="finance-movements">
        {movements.map(t => (
          <article
            className={t.status === "reversed" ? "is-reversed" : ""}
            key={`${t.type}-${t.transaction_id}`}
          >
            <span
              className={`finance-kind finance-kind--${
                t.direction === "credit" || t.type === "payment" ? "credit" : "debit"
              }`}
              aria-hidden="true"
            >
              {t.type === "payment" ? (
                <ArrowDownLeft size={16} />
              ) : t.type === "adjustment" ? (
                <SlidersHorizontal size={16} />
              ) : (
                <ArrowUpRight size={16} />
              )}
            </span>
            <div>
              <strong>{t.description}</strong>
              <small>
                {labels[t.kind || t.type]} · {dateLabel(t.date)}
                {t.due_date ? " · vence " + dateLabel(t.due_date) : ""}
                {t.method ? " · " + labels[t.method] : ""}
              </small>
              {t.receipt_number && <small>Recibo {t.receipt_number}</small>}
              {t.reversal_reason && <small>Reverso: {t.reversal_reason}</small>}
            </div>
            <strong
              className={
                t.direction === "credit" || t.type === "payment"
                  ? "finance-credit"
                  : "finance-debit"
              }
            >
              {t.direction === "credit" || t.type === "payment" ? "−" : "+"}
              {money(t.amount)}
            </strong>
            {t.status === "reversed" && <Badge tone="neutral">{labels.reversed}</Badge>}
            <div className="finance-row-actions">
              {t.type === "payment" && (
                <Button
                  variant="secondary"
                  onClick={() =>
                    download(
                      `/finance/payments/${t.transaction_id}/receipt.pdf`,
                      `recibo-${t.transaction_id}.pdf`,
                    )
                  }
                >
                  <Download size={15} /> Recibo
                </Button>
              )}
              {canManage && t.status !== "reversed" && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    onReverse(t);
                  }}
                >
                  <Undo2 size={15} /> Reversar
                </Button>
              )}
            </div>
          </article>
        ))}
      </div>
      {!movements.length && <p className="muted">No hay movimientos para estos filtros.</p>}
    </section>
  );
}
