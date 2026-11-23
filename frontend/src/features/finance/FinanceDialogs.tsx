import { useState } from "react";
import { Button, Modal } from "../../components/ui";
import { confirmAction } from "../../lib/confirm";
import { money, useActions, type Plan, type Transaction, type Transfer } from "./financeData";
import "./finance.css";

export function AccountDaysDialog({
  studentId,
  cutoffDay,
  dueDay,
  onClose,
}: {
  studentId: number;
  cutoffDay: number;
  dueDay: number;
  onClose: () => void;
}) {
  const action = useActions();
  const base = `/finance/students/${studentId}`;
  const [accountDays, setAccountDays] = useState({
    cutoff_day: String(cutoffDay),
    due_day: String(dueDay),
  });
  return (
    <Modal
      title="Días de la cuenta"
      description="El corte es informativo. El vencimiento solo se usa para cargos nuevos sin fecha explícita; no cambia deudas existentes."
      onClose={() => {
        if (!action.isPending) onClose();
      }}
    >
      <form
        className="finance-form finance-modal-form"
        onSubmit={e => {
          e.preventDefault();
          action.mutate({
            path: base + "/account",
            method: "put",
            payload: {
              cutoff_day: Number(accountDays.cutoff_day),
              due_day: Number(accountDays.due_day),
            },
            done: onClose,
          });
        }}
      >
        <label className="form-field">
          <span>Día de corte informativo</span>
          <input
            required
            disabled={action.isPending}
            type="number"
            min={1}
            max={31}
            value={accountDays.cutoff_day}
            onChange={e => setAccountDays({ ...accountDays, cutoff_day: e.target.value })}
          />
        </label>
        <label className="form-field">
          <span>Día de vencimiento sugerido</span>
          <input
            required
            disabled={action.isPending}
            type="number"
            min={1}
            max={31}
            value={accountDays.due_day}
            onChange={e => setAccountDays({ ...accountDays, due_day: e.target.value })}
          />
        </label>
        <Button disabled={action.isPending}>Guardar días de la cuenta</Button>
      </form>
    </Modal>
  );
}

/** Review a transfer, reverse a movement or cancel a plan; all need a reason. */
export function ReasonDialog({
  studentId,
  review,
  reverse,
  cancelPlan,
  onClose,
}: {
  studentId: number;
  review?: Transfer;
  reverse?: Transaction;
  cancelPlan?: Plan;
  onClose: () => void;
}) {
  const action = useActions();
  const base = `/finance/students/${studentId}`;
  const [reason, setReason] = useState("");
  return (
    <Modal
      title={review ? "Verificar transferencia" : reverse ? "Reversar movimiento" : "Cancelar plan"}
      description={
        review
          ? "Confirma el ingreso en el banco; el comprobante por sí solo no demuestra recepción."
          : "Se conserva el historial. Esta operación no devuelve dinero al banco ni borra registros."
      }
      onClose={() => {
        if (!action.isPending) {
          onClose();
        }
      }}
    >
      <form
        className="finance-form finance-modal-form"
        onSubmit={async e => {
          e.preventDefault();
          const path = review
            ? `/finance/transfers/${review.transfer_request_id}/review`
            : reverse
              ? `${base}/transactions/${reverse.type}/${reverse.transaction_id}/reverse`
              : `${base}/payment-plans/${cancelPlan?.payment_plan_id}/cancel`;
          if (await confirmAction("¿Confirmar esta operación financiera?"))
            action.mutate({
              path,
              payload: review ? { reason, approve: true } : { reason },
              done: () => {
                onClose();
              },
            });
        }}
      >
        {review && (
          <p>
            {review.reference} · {money(review.amount)} · {review.bank}
          </p>
        )}
        {reverse && (
          <p>
            {reverse.description} · {money(reverse.amount)}
          </p>
        )}
        <label className="form-field">
          <span>Motivo de la operación</span>
          <input
            required
            minLength={3}
            maxLength={250}
            value={reason}
            onChange={e => setReason(e.target.value)}
          />
        </label>
        <div className="finance-row-actions">
          <Button disabled={action.isPending}>
            {review ? "Confirmar dinero recibido" : "Confirmar operación"}
          </Button>
          {review && (
            <Button
              type="button"
              variant="danger"
              disabled={action.isPending || reason.trim().length < 3}
              onClick={() =>
                action.mutate({
                  path: `/finance/transfers/${review.transfer_request_id}/review`,
                  payload: { reason, approve: false },
                  done: onClose,
                })
              }
            >
              Rechazar comprobante
            </Button>
          )}
        </div>
      </form>
    </Modal>
  );
}
