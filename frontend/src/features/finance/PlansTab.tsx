import { type UseQueryResult } from "@tanstack/react-query";
import { useState } from "react";
import { DateInput } from "../../components/DateInput";
import { Badge, Button } from "../../components/ui";
import { apiMessage } from "../../lib/api";
import { dateLabel, day, labels, money, useActions, type Plan } from "./financeData";
import "./finance.css";

export function PlansTab({
  studentId,
  plans,
  balance,
  canManage,
  onCancel,
}: {
  studentId: number;
  plans: UseQueryResult<Plan[]>;
  balance: number;
  canManage: boolean;
  onCancel: (plan: Plan) => void;
}) {
  const action = useActions();
  const base = `/finance/students/${studentId}`;
  const [plan, setPlan] = useState({ name: "", installments: "3", first_due_date: day() });
  return (
    <section className="panel">
      <h2>Cuotas y planes</h2>
      <p className="muted">
        Distribuyen el balance actual en compromisos mensuales. Abonos y créditos posteriores cubren
        las cuotas en orden. No reemplazan los vencimientos originales de los cargos ni añaden otra
        deuda.
      </p>
      {canManage && (
        <form
          className="finance-form finance-transfer-form"
          onSubmit={e => {
            e.preventDefault();
            action.mutate({
              path: base + "/payment-plans",
              payload: { ...plan, installments: Number(plan.installments) },
              done: () => setPlan({ name: "", installments: "3", first_due_date: day() }),
            });
          }}
        >
          <label className="form-field">
            <span>Nombre del plan</span>
            <input
              required
              minLength={2}
              maxLength={100}
              value={plan.name}
              onChange={e => setPlan({ ...plan, name: e.target.value })}
            />
          </label>
          <label className="form-field">
            <span>Cantidad de cuotas</span>
            <input
              required
              type="number"
              min={2}
              max={24}
              value={plan.installments}
              onChange={e => setPlan({ ...plan, installments: e.target.value })}
            />
          </label>
          <label className="form-field">
            <span>Primer vencimiento</span>
            <DateInput
              required
              min={day()}
              value={plan.first_due_date}
              onValueChange={e => setPlan({ ...plan, first_due_date: e })}
            />
          </label>
          <Button disabled={action.isPending || balance <= 0 || plans.data?.some(p => p.active)}>
            Crear plan
          </Button>
        </form>
      )}
      {plans.error && <p className="form-error">{apiMessage(plans.error)}</p>}
      <div className="finance-mini-list">
        {plans.data?.map(p => (
          <article key={p.payment_plan_id}>
            <div className="panel-heading">
              <h3>{p.name}</h3>
              <Badge tone={p.active ? "info" : "neutral"}>
                {p.active ? "Activo" : "Cancelado"}
              </Badge>
            </div>
            {p.installments.map(i => (
              <div className="finance-installment" key={i.installment_id}>
                <span>{dateLabel(i.due_date)}</span>
                <span>
                  {money(i.amount)} · cubierto {money(i.paid_amount)} · pendiente{" "}
                  {money(i.remaining)}
                </span>
                <Badge
                  tone={
                    i.status === "paid" ? "success" : i.status === "overdue" ? "danger" : "warning"
                  }
                >
                  {labels[i.status]}
                </Badge>
              </div>
            ))}
            {canManage && p.active && (
              <Button
                variant="secondary"
                onClick={() => {
                  onCancel(p);
                }}
              >
                Cancelar plan sin borrar pagos
              </Button>
            )}
          </article>
        ))}
      </div>
      {plans.data?.length === 0 && <p className="muted">No hay planes registrados.</p>}
    </section>
  );
}
