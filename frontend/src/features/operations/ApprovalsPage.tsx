import { confirmAction } from "../../lib/confirm";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDate } from "../../lib/format";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Badge, Button, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useDraftGuard } from "../../lib/useDraftGuard";
import { useAuthStore } from "../../store/auth";
import { useAccess } from "../../lib/permissions";

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
  resource_path?: string;
  requested_by_name?: string;
  resolved_by_name?: string;
  resolved_at?: string | null;
};
const resourceKinds: Record<string, string> = {
  student: "Expediente",
  section: "Sección",
  submission: "Entrega",
  grade: "Nota",
  attendance: "Asistencia",
};
const statuses: Record<string, string> = {
  pending: "Pendiente",
  approved: "Aprobada",
  rejected: "Rechazada",
};
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

  async function close() {
    if (busy || (reason && !(await confirmAction("¿Descartar la solicitud?")))) return;
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
              <Button disabled={busy || reason.trim().length < 2}>
                {busy ? "Enviando…" : "Enviar solicitud"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

export function ApprovalsPage() {
  const user = useAuthStore(state => state.user);
  const access = useAccess();
  const client = useQueryClient();
  const [all, setAll] = useState(false);
  const [show, setShow] = useState<"pending" | "resolved" | "all">("all");
  const [selected, setSelected] = useState<Approval | null>(null);
  const [status, setStatus] = useState("approved");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const listing = useQuery({
    queryKey: ["approvals", user?.user_id, all],
    queryFn: () =>
      api
        .get<Approval[]>(all ? "/operations/approvals" : "/operations/approvals/mine")
        .then(response => response.data),
  });
  useDraftGuard(Boolean(selected && reason), busy);
  async function close() {
    if (!busy && (!reason || (await confirmAction("¿Descartar la decisión?")))) setSelected(null);
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
  const pendingCount = (listing.data ?? []).filter(item => item.status === "pending").length;
  const visible = (listing.data ?? []).filter(item =>
    show === "all"
      ? true
      : show === "pending"
        ? item.status === "pending"
        : item.status !== "pending",
  );
  function review(item: Approval, decision: "approved" | "rejected") {
    setSelected(item);
    setReason("");
    setStatus(decision);
    setError("");
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
      {access.institution && access.can("approvals.manage") && (
        <div className="view-tabs" role="group" aria-label="Bandeja de solicitudes">
          <button type="button" aria-pressed={!all} onClick={() => setAll(false)}>
            Mis solicitudes
          </button>
          <button type="button" aria-pressed={all} onClick={() => setAll(true)}>
            Bandeja institucional
          </button>
        </div>
      )}
      {Boolean(listing.data?.length) && (
        <div className="admission-pipeline" role="group" aria-label="Filtrar solicitudes">
          {(
            [
              ["all", "Todas", listing.data?.length ?? 0],
              ["pending", "Pendientes", pendingCount],
              ["resolved", "Resueltas", (listing.data?.length ?? 0) - pendingCount],
            ] as const
          ).map(([key, label, count]) => (
            <button
              key={key}
              type="button"
              aria-pressed={show === key}
              onClick={() => setShow(key)}
            >
              {label} <b>{count}</b>
            </button>
          ))}
        </div>
      )}
      {listing.isLoading ? (
        <Spinner label="Cargando solicitudes" />
      ) : listing.error ? (
        <p role="alert" className="form-error">
          {apiMessage(listing.error)}
        </p>
      ) : visible.length ? (
        <div className="approval-list">
          {visible.map(item => (
            <article className="panel approval-card" key={item.approval_request_id}>
              <div className="approval-head">
                <div>
                  <span className="kicker">
                    {resourceKinds[item.resource_type] ?? "Solicitud"} · n.º{" "}
                    {item.approval_request_id}
                  </span>
                  <h2>{item.resource_label || "Solicitud de revisión"}</h2>
                </div>
                <Badge tone={statusTone[item.status] ?? "neutral"}>
                  {statuses[item.status] ?? item.status}
                </Badge>
              </div>
              <p className="muted">
                {item.created_at && requestDate(item.created_at)}
                {all && item.requested_by_name && ` · solicitada por ${item.requested_by_name}`}
              </p>
              <blockquote className="approval-reason">{item.reason}</blockquote>
              {item.status !== "pending" && (
                <p className={`approval-decision approval-decision--${item.status}`}>
                  <b>{statuses[item.status]}</b>
                  {item.resolved_by_name && ` por ${item.resolved_by_name}`}
                  {item.resolved_at && ` el ${requestDate(item.resolved_at)}`}
                  {item.resolution_notes && `: ${item.resolution_notes}`}
                </p>
              )}
              <div className="approval-actions">
                {item.resource_path && (
                  <Link className="text-link" to={item.resource_path}>
                    Ver registro
                  </Link>
                )}
                {all && item.status === "pending" && (
                  <>
                    <Button variant="danger" onClick={() => review(item, "rejected")}>
                      Rechazar
                    </Button>
                    <Button onClick={() => review(item, "approved")}>Aprobar</Button>
                  </>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <section className="panel">
          <p>
            {listing.data?.length
              ? "No hay solicitudes con este filtro."
              : "Aún no hay solicitudes en esta bandeja."}
          </p>
          {!all && (
            <Link className="text-link" to="/">
              Volver al inicio
            </Link>
          )}
        </section>
      )}
      {selected && (
        <Modal
          title={status === "approved" ? "Aprobar solicitud" : "Rechazar solicitud"}
          description={selected.resource_label}
          onClose={close}
        >
          <p>
            La decisión se registra aquí. Los cambios en el expediente, la sección o la entrega se
            tramitan desde su pantalla.
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
              <Button disabled={busy || reason.trim().length < 2}>
                {busy ? "Guardando…" : "Registrar decisión"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
