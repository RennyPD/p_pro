import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LifeBuoy } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Modal, Spinner } from "../../components/ui";
import { apiMessage } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { platformApi } from "../../lib/platformApi";
import { TicketThread } from "../support/TicketThread";
import { ticketCategories, ticketStatus, type Ticket } from "../support/supportLabels";

/** Support inbox of Nexo's team (Fase 5 G6). */
export function SupportInbox() {
  const [status, setStatus] = useState("open");
  const [open, setOpen] = useState<number | null>(null);
  const tickets = useQuery({
    queryKey: ["platform", "support", status],
    queryFn: () =>
      platformApi
        .get<Ticket[]>("/platform/support", { params: { status: status || undefined } })
        .then(r => r.data),
  });
  return (
    <section className="panel platform-audit" aria-labelledby="support-title">
      <div className="platform-section-header">
        <h2 id="support-title">
          <LifeBuoy size={18} /> Soporte
        </h2>
        <label className="form-field">
          <span>Estado</span>
          <select value={status} onChange={event => setStatus(event.target.value)}>
            <option value="">Todos</option>
            {Object.entries(ticketStatus).map(([value, item]) => (
              <option key={value} value={value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {tickets.isPending ? (
        <Spinner label="Cargando tickets" />
      ) : !tickets.data?.length ? (
        <p className="muted">Sin tickets en este estado.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Institución</th>
                <th>Prioridad</th>
                <th>Estado</th>
                <th>Actualizado</th>
              </tr>
            </thead>
            <tbody>
              {tickets.data.map(ticket => {
                const state = ticketStatus[ticket.status] ?? ticketStatus.open;
                return (
                  <tr key={ticket.support_ticket_id}>
                    <td>
                      <Button variant="ghost" onClick={() => setOpen(ticket.support_ticket_id)}>
                        #{ticket.support_ticket_id} · {ticket.subject}
                      </Button>
                      <div className="muted">
                        {ticketCategories[ticket.category]} · {ticket.requester_name}
                      </div>
                    </td>
                    <td>{ticket.institution}</td>
                    <td>{ticket.priority}</td>
                    <td>
                      <Badge tone={state.tone}>{state.label}</Badge>
                    </td>
                    <td>{formatDateTime(ticket.updated_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {open !== null && <TicketDialog id={open} onClose={() => setOpen(null)} />}
    </section>
  );
}

function TicketDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const client = useQueryClient();
  const [body, setBody] = useState("");
  const [status, setStatus] = useState("waiting");
  const ticket = useQuery({
    queryKey: ["platform", "support", "ticket", id],
    queryFn: () => platformApi.get<Ticket>(`/platform/support/${id}`).then(r => r.data),
  });
  const reply = useMutation({
    mutationFn: () => platformApi.post(`/platform/support/${id}/reply`, { body, status }),
    onSuccess: () => {
      setBody("");
      client.invalidateQueries({ queryKey: ["platform", "support"] });
    },
  });
  return (
    <Modal
      title={ticket.data ? `#${id} · ${ticket.data.subject}` : `Ticket #${id}`}
      description={
        ticket.data
          ? `${ticket.data.institution} · ${ticket.data.requester_email ?? ""}`
          : undefined
      }
      onClose={onClose}
    >
      {ticket.isPending ? (
        <Spinner label="Cargando ticket" />
      ) : (
        <div className="platform-form">
          <TicketThread messages={ticket.data?.messages ?? []} />
          <label className="form-field">
            <span>Respuesta (vacía: solo cambia el estado)</span>
            <textarea value={body} onChange={event => setBody(event.target.value)} rows={4} />
          </label>
          <label className="form-field">
            <span>Nuevo estado</span>
            <select value={status} onChange={event => setStatus(event.target.value)}>
              {Object.entries(ticketStatus).map(([value, item]) => (
                <option key={value} value={value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          {reply.error && (
            <div className="form-error" role="alert">
              {apiMessage(reply.error)}
            </div>
          )}
          <div className="form-actions">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cerrar
            </Button>
            <Button disabled={reply.isPending} onClick={() => reply.mutate()}>
              {body.trim() ? "Responder" : "Guardar estado"}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
