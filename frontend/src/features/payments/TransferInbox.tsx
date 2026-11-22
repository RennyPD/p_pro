import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { DocumentDownload } from "../../components/DocumentDownload";
import { Badge, Button, Modal } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDateTime, formatMoney } from "../../lib/format";
import "./payments.css";

import { groupTransfers, type TransferGroup as Group } from "./paymentsData";

type Item = ApiSchema<"TransferInboxItem">;
export function TransferInbox() {
  const [review, setReview] = useState<Group | null>(null);
  const query = useQuery({
    queryKey: ["payments", "inbox"],
    queryFn: () =>
      api
        .get<Item[]>("/finance/transfers", { params: { status: "pending", limit: 100 } })
        .then(response => response.data),
  });
  if (!query.data?.length) return null;
  const groups = groupTransfers(query.data);
  return (
    <section className="panel payments-section" aria-label="Transferencias por revisar">
      <h2>
        <Inbox aria-hidden="true" /> Transferencias por revisar
        <Badge tone="warning">{groups.length}</Badge>
      </h2>
      <ul className="payments-list">
        {groups.map(group => {
          const first = group.items[0];
          return (
            <li key={group.key}>
              <div>
                <strong>
                  {formatMoney(group.batch ? first.batch_total : first.amount)} ·{" "}
                  {group.batch ? first.batch_reference : first.reference}
                </strong>
                <small>
                  {group.items
                    .map(item => `${item.student_name} ${formatMoney(item.amount)}`)
                    .join(" · ")}
                </small>
                <small>
                  {first.bank} · {formatDateTime(first.submitted_at)}
                  {group.batch && " · pago familiar"}
                </small>
              </div>
              <Button onClick={() => setReview(group)}>Revisar</Button>
            </li>
          );
        })}
      </ul>
      {review && <ReviewDialog group={review} onClose={() => setReview(null)} />}
    </section>
  );
}

function ReviewDialog({ group, onClose }: { group: Group; onClose: () => void }) {
  const client = useQueryClient();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const first = group.items[0];

  async function decide(approve: boolean, event?: FormEvent) {
    event?.preventDefault();
    if (reason.trim().length < 3) return setError("Escribe el motivo de la revisión");
    setBusy(true);
    setError("");
    try {
      await api.post(`/finance/transfers/${first.transfer_request_id}/review`, {
        approve,
        reason: reason.trim(),
      });
      toast.success(approve ? "Pago aprobado y recibos emitidos" : "Transferencia rechazada");
      await client.invalidateQueries({ queryKey: ["payments"] });
      await client.invalidateQueries({ queryKey: ["finance"] });
      onClose();
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={group.batch ? "Revisar pago familiar" : "Revisar transferencia"}
      description={
        group.batch
          ? "Es una sola transferencia repartida entre varios estudiantes: se aprueba o rechaza completa."
          : undefined
      }
      onClose={onClose}
    >
      <form className="resource-form payments-form" onSubmit={event => void decide(true, event)}>
        <ul className="payments-list payments-wide">
          {group.items.map(item => (
            <li key={item.transfer_request_id}>
              <div>
                <strong>{item.student_name}</strong>
                <small>
                  {item.enrollment_number} · {item.reference}
                </small>
              </div>
              <b>{formatMoney(item.amount)}</b>
            </li>
          ))}
        </ul>
        <div className="payments-wide payments-downloads">
          <DocumentDownload
            path={`/finance/transfers/${first.transfer_request_id}/proof`}
            filename={`comprobante-${first.transfer_request_id}`}
            label="Ver comprobante"
          />
        </div>
        <label className="form-field payments-wide">
          <span>Motivo</span>
          <input
            required
            minLength={3}
            maxLength={250}
            disabled={busy}
            value={reason}
            onChange={event => setReason(event.target.value)}
            placeholder="Depósito verificado en el banco"
          />
        </label>
        {error && (
          <p className="form-error payments-wide" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions payments-wide">
          <Button type="button" variant="danger" disabled={busy} onClick={() => void decide(false)}>
            Rechazar
          </Button>
          <Button disabled={busy}>{busy ? "Guardando…" : "Aprobar"}</Button>
        </div>
      </form>
    </Modal>
  );
}
