import { CreditCard, Lock } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, Modal } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { formatMoney } from "../../lib/format";
import { goToGateway, type GatewayRedirect, type OnlineStudent } from "./onlinePayments";

/**
 * Card payment (Fase 4 E): the amounts are checked again by the server, and the
 * card is typed on the bank's page, never in Nexo.
 */
export function OnlinePayDialog({
  students,
  suggested,
  minAmount,
  onClose,
}: {
  students: OnlineStudent[];
  suggested?: Record<number, number>;
  minAmount: string;
  onClose: () => void;
}) {
  const [amounts, setAmounts] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      students.map(student => [
        student.student_id,
        String(suggested?.[student.student_id] ?? Number(student.balance)),
      ]),
    ),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const total = students.reduce((sum, s) => sum + (Number(amounts[s.student_id]) || 0), 0);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const allocations = students
      .map(s => ({
        student_id: s.student_id,
        amount: (Number(amounts[s.student_id]) || 0).toFixed(2),
      }))
      .filter(item => Number(item.amount) > 0);
    if (!allocations.length) return setError("Escribe al menos un monto");
    setBusy(true);
    try {
      const { data } = await api.post<{ id: string; redirect: GatewayRedirect }>(
        "/online-payments",
        { allocations },
      );
      goToGateway(data.redirect);
    } catch (problem) {
      setError(apiMessage(problem));
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Pagar con tarjeta"
      description={`Pago mínimo ${formatMoney(Number(minAmount))}. Escribirás los datos de la tarjeta en la página segura del banco.`}
      onClose={onClose}
    >
      <form className="online-pay" onSubmit={submit}>
        {students.map(student => (
          <label key={student.student_id} className="form-field">
            <span>
              {student.name} · pendiente {formatMoney(Number(student.balance))}
            </span>
            <input
              type="number"
              min="0"
              step="0.01"
              max={student.balance}
              inputMode="decimal"
              value={amounts[student.student_id] ?? ""}
              onChange={event =>
                setAmounts(current => ({ ...current, [student.student_id]: event.target.value }))
              }
            />
          </label>
        ))}
        <p className="online-pay__total">
          Total <strong>{formatMoney(total)}</strong>
        </p>
        <p className="muted online-pay__secure">
          <Lock size={14} aria-hidden /> Nexo nunca ve ni guarda los datos de tu tarjeta.
        </p>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        <div className="form-actions">
          <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button disabled={busy || total <= 0}>
            <CreditCard size={16} /> {busy ? "Abriendo el banco…" : "Continuar al pago"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
