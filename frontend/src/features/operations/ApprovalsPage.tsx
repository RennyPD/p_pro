import { useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDate } from "../../lib/format";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Badge, Button, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useDraftGuard } from "../../lib/useDraftGuard";
import { useAuthStore } from "../../store/auth";

type Approval = {
  approval_request_id: number;
  resource_type: string;
  resource_id: number;
  reason: string;
  status: string;
  resolution_notes: string;
  requested_by: number;
  created_at?: string;
  resource_label?: string;
  requested_by_name?: string;
};
const statuses: Record<string, string> = { pending: "Pendiente", approved: "Aprobada", rejected: "Rechazada" };
const statusTone: Record<string, "warning" | "success" | "danger"> = {
  pending: "warning",
  approved: "success",
  rejected: "danger",
};
const requestDate = (value?: string) => formatDate(value, "");

export function RequestApproval({
  resource,
  id,
  label,
}: {
  resource: "student" | "section" | "submission";
  id: number;
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const client = useQueryClient();
  useDraftGuard(open && Boolean(reason), busy);

  function close() {
    if (busy || (reason && !window.confirm("¿Descartar la solicitud?"))) return;
    setOpen(false);
    setReason("");
    setError("");
  }
  async function request(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/operations/approvals", {
        request_type: "academic_exception",
        resource_type: resource,
        resource_id: id,
        reason: reason.trim(),
      });
      await client.invalidateQueries({ queryKey: ["approvals"] });
      toast.success("Solicitud registrada. Consulta su estado en Mis solicitudes.");
      setOpen(false);
      setReason("");
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Button type="button" variant="secondary" onClick={() => setOpen(true)}>
        Solicitar revisión
      </Button>
      {open && (
        <Modal title="Solicitar revisión" description={label} onClose={close}>
          <form className="resource-form" onSubmit={request}>
            <label className="form-field">
              <span>Motivo de la solicitud</span>
              <textarea
                rows={4}
                required
                maxLength={5000}
                value={reason}
                onChange={event => setReason(event.target.value)}
              />
            </label>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            <div className="form-actions">
              <Button type="button" variant="secondary" disabled={busy} onClick={close}>
                Cancelar
              </Button>
              <Button disabled={busy || reason.trim().length < 2}>{busy ? "Enviando…" : "Enviar solicitud"}</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

export function ApprovalsPage() {
  const user = useAuthStore(state => state.user);
  const client = useQueryClient();
  const [all, setAll] = useState(false);
  const [selected, setSelected] = useState<Approval | null>(null);
  const [status, setStatus] = useState("approved");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const listing = useQuery({
    queryKey: ["approvals", user?.user_id, all],
    queryFn: () =>
      api.get<Approval[]>(all ? "/operations/approvals" : "/operations/approvals/mine").then(response => response.data),
  });
  useDraftGuard(Boolean(selected && reason), busy);
  function close() {
    if (!busy && (!reason || window.confirm("¿Descartar la decisión?"))) setSelected(null);
  }
  async function resolve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await api.patch(`/operations/approvals/${selected.approval_request_id}`, {
        status,
        resolution_notes: reason.trim(),
      });
      void client.invalidateQueries({ queryKey: ["approvals"] });
      toast.success("Decisión registrada");
      setSelected(null);
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="kicker">Seguimiento</span>
          <h1>Solicitudes de revisión</h1>
          <p>Revisiones de expedientes, notas, secciones o entregas y su decisión.</p>
        </div>
      </header>
      {user?.role_name === "admin" && (
        <div className="form-actions">
          <Button variant={all ? "secondary" : "primary"} onClick={() => setAll(false)}>
            Mis solicitudes
          </Button>
          <Button variant={all ? "primary" : "secondary"} onClick={() => setAll(true)}>
            Bandeja institucional
          </Button>
        </div>
      )}
      {listing.isLoading ? (
        <Spinner label="Cargando solicitudes" />
      ) : listing.error ? (
        <p role="alert" className="form-error">
          {apiMessage(listing.error)}
        </p>
      ) : listing.data?.length ? (
        listing.data.map(item => (
          <article className="panel" key={item.approval_request_id}>
            <div className="approval-head">
              <h2>{item.resource_label || "Solicitud de revisión"}</h2>
              <Badge tone={statusTone[item.status] ?? "neutral"}>{statuses[item.status] ?? item.status}</Badge>
            </div>
            <p className="muted">
              Solicitud n.º {item.approval_request_id}
              {item.created_at && ` · ${requestDate(item.created_at)}`}
              {all && item.requested_by_name && ` · solicitada por ${item.requested_by_name}`}
            </p>
            <p>{item.reason}</p>
            {item.resolution_notes && <p>Decisión registrada · {item.resolution_notes}</p>}
            {all && item.status === "pending" && (
              <Button
                variant="secondary"
                onClick={() => {
                  setSelected(item);
                  setReason("");
                  setStatus("approved");
                  setError("");
                }}
              >
                Revisar solicitud
              </Button>
            )}
          </article>
        ))
      ) : (
        <section className="panel">
          <p>Aún no hay solicitudes en esta bandeja.</p>
          {!all && <Link to="/">Volver al inicio</Link>}
        </section>
      )}
      {selected && (
        <Modal title="Revisar solicitud" description={selected.resource_label} onClose={close}>
          <p>
            La decisión se registra aquí. Los cambios en el expediente, la sección o la entrega se tramitan desde su
            pantalla.
          </p>
          <form className="resource-form" onSubmit={resolve}>
            <label className="form-field">
              <span>Decisión</span>
              <select value={status} onChange={event => setStatus(event.target.value)}>
                <option value="approved">Aprobar</option>
                <option value="rejected">Rechazar</option>
              </select>
            </label>
            <label className="form-field">
              <span>Motivo de la decisión</span>
              <textarea
                rows={4}
                required
                value={reason}
                maxLength={5000}
                onChange={event => setReason(event.target.value)}
              />
            </label>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            <div className="form-actions">
              <Button type="button" variant="secondary" disabled={busy} onClick={close}>
                Cancelar
              </Button>
              <Button disabled={busy || reason.trim().length < 2}>{busy ? "Guardando…" : "Registrar decisión"}</Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
