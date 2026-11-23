import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DateInput } from "../../components/DateInput";
import { Button } from "../../components/ui";
import { api } from "../../lib/api";
import { confirmAction } from "../../lib/confirm";
import { useAuthStore } from "../../store/auth";
import { labels, money, useActions, type Concept } from "./financeData";
import "./finance.css";

/** Charge, cash received or adjustment for one account (finance.manage). */
export function RecordMovementPanel({
  studentId,
  dueDay,
  balance,
}: {
  studentId: number;
  dueDay: number;
  balance: number;
}) {
  const uid = useAuthStore(s => s.user?.user_id);
  const action = useActions();
  const base = `/finance/students/${studentId}`;
  const concepts = useQuery({
    queryKey: ["finance-concepts", uid],
    queryFn: () => api.get<Concept[]>("/finance/billing-concepts").then(r => r.data),
  });
  const [charge, setCharge] = useState({ description: "", amount: "", due_date: "" });
  const [payment, setPayment] = useState({
    amount: "",
    reference: "",
    note: "",
    key: crypto.randomUUID(),
  });
  const [adjustment, setAdjustment] = useState({
    kind: "scholarship",
    description: "",
    amount: "",
    due_date: "",
  });
  return (
    <section className="panel finance-office" aria-label="Registrar cargo, efectivo o ajuste">
      <h2 className="finance-office__title">Registrar cargo, efectivo o ajuste</h2>
      <div className="finance-actions finance-actions--three">
        <form
          className="finance-form"
          onSubmit={e => {
            e.preventDefault();
            action.mutate({
              path: base + "/charges",
              payload: { ...charge, due_date: charge.due_date || null },
              done: () => setCharge({ description: "", amount: "", due_date: "" }),
            });
          }}
        >
          <h2>Nuevo cargo</h2>
          <label className="form-field">
            <span>Usar concepto del catálogo</span>
            <select
              defaultValue=""
              onChange={e => {
                const c = concepts.data?.find(c => c.billing_concept_id === Number(e.target.value));
                if (c) setCharge({ ...charge, description: c.name, amount: String(c.amount) });
              }}
            >
              <option value="">Cargo personalizado</option>
              {concepts.data
                ?.filter(c => c.active)
                .map(c => (
                  <option key={c.billing_concept_id} value={c.billing_concept_id}>
                    {c.name} · {money(c.amount)}
                  </option>
                ))}
            </select>
          </label>
          <label className="form-field">
            <span>Concepto del cargo</span>
            <input
              required
              minLength={2}
              maxLength={200}
              value={charge.description}
              onChange={e => setCharge({ ...charge, description: e.target.value })}
            />
          </label>
          <label className="form-field">
            <span>Monto del cargo RD$</span>
            <input
              required
              type="number"
              min=".01"
              step=".01"
              value={charge.amount}
              onChange={e => setCharge({ ...charge, amount: e.target.value })}
            />
          </label>
          <label className="form-field">
            <span>Vencimiento del cargo</span>
            <DateInput
              value={charge.due_date}
              onValueChange={e => setCharge({ ...charge, due_date: e })}
            />
          </label>
          <small className="muted">Vacío: próximo día {dueDay}, adaptado al mes.</small>
          <Button disabled={action.isPending}>Registrar cargo</Button>
        </form>
        <form
          className="finance-form"
          onSubmit={async e => {
            e.preventDefault();
            if (
              await confirmAction(
                `¿Confirmas que recibiste ${money(Number(payment.amount))} en efectivo?`,
              )
            )
              action.mutate({
                path: base + "/payments",
                payload: {
                  amount: payment.amount,
                  reference: payment.reference,
                  note: payment.note,
                  method: "cash",
                  idempotency_key: payment.key,
                },
                done: () =>
                  setPayment({ amount: "", reference: "", note: "", key: crypto.randomUUID() }),
              });
          }}
        >
          <h2>Efectivo recibido</h2>
          <p className="muted">
            Registra únicamente dinero recibido en caja. Las transferencias se revisan en su
            pestaña.
          </p>
          <label className="form-field">
            <span>Monto recibido RD$</span>
            <input
              required
              type="number"
              min=".01"
              max={Math.max(balance, 0)}
              step=".01"
              value={payment.amount}
              onChange={e => setPayment({ ...payment, amount: e.target.value })}
            />
          </label>
          <label className="form-field">
            <span>Referencia del efectivo</span>
            <input
              required
              minLength={2}
              maxLength={100}
              value={payment.reference}
              onChange={e => setPayment({ ...payment, reference: e.target.value })}
            />
          </label>
          <label className="form-field">
            <span>Nota del pago</span>
            <input
              maxLength={250}
              value={payment.note}
              onChange={e => setPayment({ ...payment, note: e.target.value })}
            />
          </label>
          <Button disabled={action.isPending || balance <= 0}>Registrar efectivo</Button>
        </form>
        <form
          className="finance-form"
          onSubmit={e => {
            e.preventDefault();
            action.mutate({
              path: base + "/adjustments",
              payload: { ...adjustment, due_date: adjustment.due_date || null },
              done: () =>
                setAdjustment({
                  kind: "scholarship",
                  description: "",
                  amount: "",
                  due_date: "",
                }),
            });
          }}
        >
          <h2>Becas y ajustes</h2>
          <label className="form-field">
            <span>Tipo de ajuste</span>
            <select
              value={adjustment.kind}
              onChange={e => setAdjustment({ ...adjustment, kind: e.target.value })}
            >
              {["scholarship", "discount", "credit", "late_fee", "debit"].map(k => (
                <option key={k} value={k}>
                  {labels[k]} ·{" "}
                  {["late_fee", "debit"].includes(k) ? "aumenta deuda" : "reduce deuda"}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Motivo del ajuste</span>
            <input
              required
              minLength={2}
              maxLength={200}
              value={adjustment.description}
              onChange={e => setAdjustment({ ...adjustment, description: e.target.value })}
            />
          </label>
          <label className="form-field">
            <span>Monto del ajuste RD$</span>
            <input
              required
              type="number"
              min=".01"
              step=".01"
              value={adjustment.amount}
              onChange={e => setAdjustment({ ...adjustment, amount: e.target.value })}
            />
          </label>
          {["late_fee", "debit"].includes(adjustment.kind) && (
            <label className="form-field">
              <span>Vencimiento del ajuste</span>
              <DateInput
                value={adjustment.due_date}
                onValueChange={e => setAdjustment({ ...adjustment, due_date: e })}
              />
            </label>
          )}
          <Button disabled={action.isPending}>Registrar ajuste</Button>
        </form>
      </div>
    </section>
  );
}
