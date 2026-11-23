import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DateInput } from "../../components/DateInput";
import { Button } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { confirmAction } from "../../lib/confirm";
import { useAuthStore } from "../../store/auth";
import {
  dateLabel,
  day,
  labels,
  money,
  useActions,
  type Closing,
  type Concept,
} from "./financeData";
import "./finance.css";

export function FinanceOffice() {
  const uid = useAuthStore(s => s.user?.user_id);
  const action = useActions();
  const concepts = useQuery({
    queryKey: ["finance-concepts", uid],
    queryFn: () => api.get<Concept[]>("/finance/billing-concepts").then(r => r.data),
  });
  const closings = useQuery({
    queryKey: ["finance-closings", uid],
    queryFn: () => api.get<Closing[]>("/finance/cash-closings").then(r => r.data),
  });
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [frequency, setFrequency] = useState("once");
  const [closingDate, setClosingDate] = useState(day());
  return (
    <details className="panel finance-office">
      <summary>Caja y catálogo de conceptos</summary>
      <div className="finance-actions">
        <section>
          <h2>Conceptos de cobro</h2>
          <p className="muted">
            Plantillas de importes. Para cobrar cada mes a un grupo, crea un plan en «Planes de
            cobro».
          </p>
          <form
            className="finance-form"
            onSubmit={e => {
              e.preventDefault();
              action.mutate({
                path: "/finance/billing-concepts",
                payload: { name, amount, frequency },
                done: () => {
                  setName("");
                  setAmount("");
                },
              });
            }}
          >
            <label className="form-field">
              <span>Nombre del concepto</span>
              <input
                required
                minLength={2}
                maxLength={120}
                value={name}
                onChange={e => setName(e.target.value)}
              />
            </label>
            <label className="form-field">
              <span>Importe RD$</span>
              <input
                required
                type="number"
                min=".01"
                step=".01"
                value={amount}
                onChange={e => setAmount(e.target.value)}
              />
            </label>
            <label className="form-field">
              <span>Frecuencia informativa</span>
              <select value={frequency} onChange={e => setFrequency(e.target.value)}>
                {["once", "monthly", "term", "annual"].map(f => (
                  <option key={f} value={f}>
                    {labels[f]}
                  </option>
                ))}
              </select>
            </label>
            <Button disabled={action.isPending}>Crear concepto</Button>
          </form>
          {concepts.error && <p className="form-error">{apiMessage(concepts.error)}</p>}
          <div className="finance-mini-list">
            {concepts.data?.map(c => (
              <article key={c.billing_concept_id}>
                <strong>{c.name}</strong>
                <small>
                  {money(c.amount)} · {labels[c.frequency]}
                </small>
              </article>
            ))}
          </div>
        </section>
        <section>
          <h2>Cierre diario</h2>
          <p className="muted">
            Un cierre impide registrar pagos y reversos para ese día. Los registros anteriores no se
            reclasifican como efectivo.
          </p>
          <form
            className="finance-form"
            onSubmit={async e => {
              e.preventDefault();
              if (
                await confirmAction(
                  `¿Cerrar la caja del ${closingDate}? No podrás registrar pagos hoy si cierras el día actual.`,
                )
              )
                action.mutate({ path: `/finance/cash-closings/${closingDate}`, payload: {} });
            }}
          >
            <label className="form-field">
              <span>Fecha de caja (República Dominicana)</span>
              <DateInput
                required
                max={day()}
                value={closingDate}
                onValueChange={e => setClosingDate(e)}
              />
            </label>
            <Button disabled={action.isPending} variant="secondary">
              Confirmar cierre de caja
            </Button>
          </form>
          {closings.error && <p className="form-error">{apiMessage(closings.error)}</p>}
          <div className="finance-mini-list">
            {closings.data?.map(c => (
              <article key={c.cash_closing_id}>
                <strong>
                  {dateLabel(c.closing_date)} · {money(c.total_payments)}
                </strong>
                <small>
                  {c.payment_count} pagos · Efectivo {money(c.cash_total)} · Transferencias{" "}
                  {money(c.transfer_total)} · Anteriores{" "}
                  {money(c.total_payments - c.cash_total - c.transfer_total)}
                </small>
              </article>
            ))}
          </div>
        </section>
      </div>
    </details>
  );
}
