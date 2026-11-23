import { useState } from "react";
import { DateInput } from "../../components/DateInput";
import { formatDateTime } from "../../lib/format";
import { useQuery } from "@tanstack/react-query";
import { Button, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./institutional-control.css";
import "./alert-history.css";
import { alertLabels, severityNames, interventionTypes } from "./institutionalControlShared";

export function AlertCase({
  alert,
  draft,
  studentName,
  busy,
  update,
  assign,
  register,
  resolve,
  reopen,
}: any) {
  const uid = useAuthStore(s => s.user?.user_id);
  const assignees = useQuery({
    queryKey: ["alert-assignees", uid, alert.student_id],
    queryFn: () =>
      api
        .get(`/operations/alert-assignees`, { params: { student_id: alert.student_id } })
        .then(r => r.data),
    enabled: alert.status === "open",
  });
  const [showHistory, setShowHistory] = useState(false);
  const history = useQuery({
    queryKey: ["alert-interventions", uid, alert.early_alert_id],
    queryFn: () =>
      api
        .get(`/operations/alerts/${alert.early_alert_id}/interventions`)
        .then(response => response.data),
    enabled: showHistory,
  });
  return (
    <article>
      <div className="case-title">
        <div>
          <strong>{studentName ?? `Estudiante #${alert.student_id}`}</strong>
          <small>{alertLabels[alert.category] ?? alert.category}</small>
        </div>
        <span className={`case-severity case-severity--${alert.severity}`}>
          {severityNames[alert.severity] || alert.severity}
        </span>
      </div>
      <p>{alert.reason}</p>
      {alert.status === "open" ? (
        <>
          <div className="case-fields">
            <label>
              <span>Responsable</span>
              <select
                disabled={busy || assignees.isFetching}
                value={draft.assigned_to}
                onChange={e => update({ ...draft, assigned_to: e.target.value })}
              >
                <option value="">Sin asignar</option>
                {(assignees.data || []).map((u: any) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Próximo seguimiento</span>
              <DateInput
                disabled={busy}
                value={draft.follow_up_date}
                onValueChange={e => update({ ...draft, follow_up_date: e })}
              />
            </label>
          </div>
          <label className="form-field">
            <span>Tipo de actuación</span>
            <select
              disabled={busy}
              value={draft.action_type ?? "note"}
              onChange={event => update({ ...draft, action_type: event.target.value })}
            >
              {Object.entries(interventionTypes).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Detalle de la actuación</span>
            <textarea
              aria-label="Actuación del caso"
              disabled={busy}
              maxLength={5000}
              rows={3}
              placeholder="Describe la llamada, reunión, acuerdo o resultado"
              value={draft.notes}
              onChange={e => update({ ...draft, notes: e.target.value })}
            />
          </label>
        </>
      ) : (
        <p className="resolution-note">
          <strong>Resolución:</strong> {alert.resolution_notes || "Sin detalle"}
        </p>
      )}
      <div className="case-actions">
        <button
          type="button"
          className="text-link case-history-toggle"
          onClick={() => setShowHistory(value => !value)}
        >
          {showHistory ? "Ocultar historial" : "Ver historial"}
        </button>
        {alert.status === "open" ? (
          <>
            <Button variant="secondary" disabled={busy} onClick={() => assign(draft)}>
              Asignar
            </Button>
            <Button
              variant="secondary"
              disabled={busy || draft.notes.trim().length < 3}
              onClick={() => register(draft)}
            >
              Registrar actuación
            </Button>
            <Button disabled={!draft.notes.trim()} onClick={() => resolve(draft)}>
              Resolver
            </Button>
          </>
        ) : (
          <Button variant="secondary" disabled={busy} onClick={reopen}>
            Reabrir caso
          </Button>
        )}
      </div>
      {assignees.error && <p className="form-error">{apiMessage(assignees.error)}</p>}
      {showHistory && (
        <div className="intervention-history">
          {history.isLoading ? (
            <Spinner />
          ) : history.error ? (
            <p className="form-error">{apiMessage(history.error)}</p>
          ) : history.data?.length ? (
            history.data.map((item: any) => (
              <div key={item.alert_intervention_id}>
                <strong>
                  {{
                    contact: "Contacto",
                    meeting: "Reunión",
                    referral: "Derivación",
                    agreement: "Acuerdo",
                    note: "Actuación",
                  }[item.action_type as string] || item.action_type}{" "}
                  · {item.performer_name || "Registro histórico"}
                </strong>
                <small>{formatDateTime(item.created_at)}</small>
                <p>{item.notes}</p>
              </div>
            ))
          ) : (
            <p className="muted">Todavía no hay actuaciones registradas.</p>
          )}
        </div>
      )}
    </article>
  );
}
