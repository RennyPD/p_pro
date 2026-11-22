import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDate, formatDateTime, formatMoney } from "../../lib/format";
import {
  MAX_PROOF,
  readBase64,
  toAmount,
  transferStatus,
  type FamilyFinance,
  type FamilyTransfer,
  type FinanceOptions,
} from "./paymentsData";
import "./payments.css";

type Suggestion = ApiSchema<"FamilySuggestion">;

/** Family total with the breakdown per child and concept, and one transfer for several. */
export function FamilyPayments() {
  const [paying, setPaying] = useState(false);
  const family = useQuery({
    queryKey: ["payments", "family"],
    queryFn: () => api.get<FamilyFinance>("/guardian/finance").then(response => response.data),
  });
  const transfers = useQuery({
    queryKey: ["payments", "family-transfers"],
    queryFn: () => api.get<FamilyTransfer[]>("/guardian/transfers").then(response => response.data),
  });
  const options = useQuery({
    queryKey: ["payments", "options"],
    queryFn: () => api.get<FinanceOptions>("/finance/options").then(response => response.data),
  });

  if (family.isPending) return <Spinner />;
  if (family.isError)
    return (
      <EmptyState
        icon={<Users />}
        title="No pudimos cargar los pagos de la familia"
        description={apiMessage(family.error)}
      />
    );
  const data = family.data;
  const names = Object.fromEntries(data.students.map(s => [s.student_id, s.student_name]));
  const instructions = options.data?.transfer_instructions ?? "";

  return (
    <div className="payments-account">
      <section className="panel payments-lead" aria-label="Total de la familia">
        <div>
          <span className="kicker">Total de la familia</span>
          <strong className={data.total_overdue > 0 ? "is-low" : undefined}>
            {formatMoney(data.total_balance)}
          </strong>
          <small>
            {data.total_overdue > 0
              ? `${formatMoney(data.total_overdue)} vencido`
              : data.next_due_date
                ? `Próximo vencimiento: ${formatDate(data.next_due_date)}`
                : "Al día"}
          </small>
        </div>
        {data.total_balance > 0 && instructions && (
          <Button className="payments-action" onClick={() => setPaying(true)}>
            Pagar a varios hijos
          </Button>
        )}
      </section>

      <section className="panel payments-section" aria-label="Por estudiante">
        <h2>Por estudiante</h2>
        <ul className="payments-list">
          {data.students.map(student => (
            <li key={student.student_id}>
              <div>
                <strong>{student.student_name}</strong>
                <small>
                  {student.overdue_balance > 0
                    ? `${formatMoney(student.overdue_balance)} vencido`
                    : student.next_due_date
                      ? `Vence ${formatDate(student.next_due_date)}`
                      : "Al día"}
                  {student.financial_responsible && " · eres responsable de pago"}
                </small>
              </div>
              <b className={student.overdue_balance > 0 ? "is-low" : undefined}>
                {formatMoney(student.balance)}
              </b>
            </li>
          ))}
        </ul>
      </section>

      {data.concepts.length > 0 && (
        <section className="panel payments-section" aria-label="Por concepto">
          <h2>Por concepto</h2>
          <ul className="payments-list">
            {data.concepts.map(concept => (
              <li key={concept.concept}>
                <div>
                  <strong>{concept.concept}</strong>
                  <small>
                    {concept.students
                      .map(s => `${names[s.student_id]?.split(" ")[0]} ${formatMoney(s.remaining)}`)
                      .join(" · ")}
                  </small>
                </div>
                <b>{formatMoney(concept.remaining)}</b>
              </li>
            ))}
          </ul>
        </section>
      )}

      {transfers.data && transfers.data.length > 0 && (
        <section className="panel payments-section" aria-label="Pagos familiares reportados">
          <h2>Pagos familiares reportados</h2>
          <ul className="payments-list">
            {transfers.data.map(batch => {
              const state = transferStatus[batch.status] ?? transferStatus.pending;
              return (
                <li key={batch.transfer_batch_id}>
                  <div>
                    <strong>
                      {formatMoney(batch.total)} · {batch.reference}
                    </strong>
                    <small>
                      {formatDateTime(batch.submitted_at)} ·{" "}
                      {batch.shares
                        .map(s => `${s.student_name.split(" ")[0]} ${formatMoney(s.amount)}`)
                        .join(" · ")}
                    </small>
                    {batch.status === "rejected" && batch.review_reason && (
                      <small className="is-low">{batch.review_reason}</small>
                    )}
                  </div>
                  <Badge tone={state.tone}>{state.label}</Badge>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {paying && (
        <FamilyTransferDialog
          family={data}
          instructions={instructions}
          onClose={() => setPaying(false)}
        />
      )}
    </div>
  );
}

function FamilyTransferDialog({
  family,
  instructions,
  onClose,
}: {
  family: FamilyFinance;
  instructions: string;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const payable = family.students.filter(s => s.balance > 0);
  const [total, setTotal] = useState(
    (family.total_overdue > 0 ? family.total_overdue : family.total_balance).toFixed(2),
  );
  const [shares, setShares] = useState<Record<number, string>>({});
  const [reference, setReference] = useState("");
  const [bank, setBank] = useState("");
  const [file, setFile] = useState<File>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sum = payable.reduce(
    (acc, s) => acc + Number(toAmount(shares[s.student_id] ?? "") ?? 0),
    0,
  );

  async function suggest() {
    const value = toAmount(total);
    if (!value) return setError("Escribe el monto transferido");
    setError("");
    try {
      const response = await api.get<Suggestion[]>("/guardian/finance/allocation", {
        params: { amount: value },
      });
      setShares(
        Object.fromEntries(response.data.map(item => [item.student_id, item.amount.toFixed(2)])),
      );
    } catch (failure) {
      setError(apiMessage(failure));
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const allocations = payable
      .map(s => ({ student_id: s.student_id, amount: toAmount(shares[s.student_id] ?? "") }))
      .filter(item => item.amount !== null);
    if (!allocations.length) return setError("Reparte el monto entre al menos un estudiante");
    const over = payable.find(s => Number(toAmount(shares[s.student_id] ?? "") ?? 0) > s.balance);
    if (over) return setError(`El monto de ${over.student_name} supera su balance`);
    if (!file || file.size > MAX_PROOF)
      return setError("Adjunta un PDF, PNG o JPEG de máximo 2 MB");
    setBusy(true);
    setError("");
    try {
      await api.post("/guardian/transfers", {
        reference: reference.trim(),
        bank: bank.trim(),
        proof_base64: await readBase64(file),
        allocations,
      });
      toast.success("Pago familiar reportado. Caja lo verificará.");
      await client.invalidateQueries({ queryKey: ["payments"] });
      onClose();
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Pagar a varios hijos" description={instructions} onClose={onClose}>
      <form className="resource-form payments-form" onSubmit={submit}>
        <label className="form-field">
          <span>Monto transferido</span>
          <input
            required
            inputMode="decimal"
            disabled={busy}
            value={total}
            onChange={event => setTotal(event.target.value)}
          />
        </label>
        <div className="form-field payments-suggest">
          <Button type="button" variant="secondary" disabled={busy} onClick={() => void suggest()}>
            Sugerir reparto
          </Button>
          <small>Primero lo que vence antes, sea del hijo que sea. Puedes ajustarlo.</small>
        </div>
        <fieldset className="payments-wide payments-shares">
          <legend>Reparto por estudiante</legend>
          {payable.map(student => (
            <label key={student.student_id} className="form-field">
              <span>
                {student.student_name} <small>(debe {formatMoney(student.balance)})</small>
              </span>
              <input
                inputMode="decimal"
                disabled={busy}
                value={shares[student.student_id] ?? ""}
                placeholder="0.00"
                onChange={event =>
                  setShares({ ...shares, [student.student_id]: event.target.value })
                }
              />
            </label>
          ))}
          <p className={Math.abs(sum - Number(total || 0)) > 0.004 ? "is-low" : "muted"}>
            Repartido: {formatMoney(sum)} de {formatMoney(Number(total || 0))}
          </p>
        </fieldset>
        <label className="form-field">
          <span>Número de referencia</span>
          <input
            required
            minLength={2}
            maxLength={100}
            disabled={busy}
            value={reference}
            onChange={event => setReference(event.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Banco de origen</span>
          <input
            required
            minLength={2}
            maxLength={100}
            disabled={busy}
            value={bank}
            onChange={event => setBank(event.target.value)}
          />
        </label>
        <label className="form-field payments-wide">
          <span>Comprobante (PDF, PNG o JPEG, máximo 2 MB)</span>
          <input
            type="file"
            accept="application/pdf,image/png,image/jpeg"
            disabled={busy}
            onChange={event => setFile(event.target.files?.[0])}
          />
        </label>
        {error && (
          <p className="form-error payments-wide" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions payments-wide">
          <Button type="button" variant="secondary" disabled={busy} onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={busy}>{busy ? "Enviando…" : "Enviar pago familiar"}</Button>
        </div>
      </form>
    </Modal>
  );
}
