import { type UseQueryResult } from "@tanstack/react-query";
import { Badge, Button } from "../../components/ui";
import { apiMessage } from "../../lib/api";
import { dateLabel, download, labels, money, type Transfer } from "./financeData";
import "./finance.css";

/** Transfers reported for this account; family transfers are reviewed as a whole. */
export function TransfersTab({
  transfers,
  canManage,
  onReview,
}: {
  transfers: UseQueryResult<Transfer[]>;
  canManage: boolean;
  onReview: (item: Transfer) => void;
}) {
  return (
    <section className="panel">
      <h2>Transferencias reportadas</h2>
      <p className="muted">
        Una transferencia no reduce la deuda hasta que caja confirma el ingreso en el banco.
      </p>
      {transfers.error && <p className="form-error">{apiMessage(transfers.error)}</p>}
      <div className="finance-mini-list">
        {transfers.data?.map(t => (
          <article key={t.transfer_request_id}>
            <strong>
              {t.reference} · {money(t.amount)}
            </strong>
            {t.batch_id && (
              <Badge tone="info">
                Pago familiar de {money(t.batch_total ?? 0)} · {t.batch_size} estudiantes · se
                revisa completo
              </Badge>
            )}
            <small>
              {t.bank} · {dateLabel(t.submitted_at)} · {t.note}
            </small>
            <Badge
              tone={
                t.status === "approved" ? "success" : t.status === "rejected" ? "danger" : "warning"
              }
            >
              {labels[t.status]}
            </Badge>
            {t.review_reason && <p>{t.review_reason}</p>}
            <div className="finance-row-actions">
              <Button
                variant="ghost"
                onClick={() =>
                  download(
                    `/finance/transfers/${t.transfer_request_id}/proof`,
                    `comprobante-${t.transfer_request_id}`,
                  )
                }
              >
                Descargar comprobante
              </Button>
              {canManage && t.status === "pending" && (
                <Button
                  onClick={() => {
                    onReview(t);
                  }}
                >
                  Revisar ingreso
                </Button>
              )}
              {t.payment_id && (
                <Button
                  variant="secondary"
                  onClick={() =>
                    download(
                      `/finance/payments/${t.payment_id}/receipt.pdf`,
                      `recibo-${t.payment_id}.pdf`,
                    )
                  }
                >
                  Recibo
                </Button>
              )}
            </div>
          </article>
        ))}
      </div>
      {transfers.data?.length === 0 && <p className="muted">No hay transferencias reportadas.</p>}
    </section>
  );
}
