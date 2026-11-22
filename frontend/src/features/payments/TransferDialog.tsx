import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button, Modal } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { formatMoney } from "../../lib/format";
import { MAX_PROOF, readBase64, toAmount } from "./paymentsData";

/** Report a bank transfer for one student; the cashier verifies it. */
export function TransferDialog({
  studentId,
  instructions,
  suggested,
  balance,
  onClose,
}: {
  studentId: number;
  instructions: string;
  suggested: number;
  balance: number;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [amount, setAmount] = useState(suggested > 0 ? suggested.toFixed(2) : "");
  const [reference, setReference] = useState("");
  const [bank, setBank] = useState("");
  const [note, setNote] = useState("");
  const [file, setFile] = useState<File>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = toAmount(amount);
    if (!value) return setError("Escribe un monto mayor que cero");
    if (Number(value) > balance) return setError("El monto supera el balance pendiente");
    if (!file || file.size > MAX_PROOF)
      return setError("Adjunta un PDF, PNG o JPEG de máximo 2 MB");
    setBusy(true);
    setError("");
    try {
      await api.post(`/finance/students/${studentId}/transfers`, {
        amount: value,
        reference: reference.trim(),
        bank: bank.trim(),
        note: note.trim(),
        proof_base64: await readBase64(file),
      });
      toast.success("Pago reportado. Caja lo verificará y verás el recibo aquí.");
      await client.invalidateQueries({ queryKey: ["payments"] });
      onClose();
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Reportar pago" description={instructions} onClose={onClose}>
      <form className="resource-form payments-form" onSubmit={submit}>
        <label className="form-field">
          <span>Monto transferido</span>
          <input
            required
            inputMode="decimal"
            disabled={busy}
            value={amount}
            onChange={event => setAmount(event.target.value)}
          />
          <small>Balance pendiente: {formatMoney(balance)}</small>
        </label>
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
        <label className="form-field">
          <span>Nota (opcional)</span>
          <input
            maxLength={250}
            disabled={busy}
            value={note}
            onChange={event => setNote(event.target.value)}
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
          <Button disabled={busy}>{busy ? "Enviando…" : "Enviar reporte"}</Button>
        </div>
      </form>
    </Modal>
  );
}
