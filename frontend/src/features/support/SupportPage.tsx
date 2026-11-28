import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LifeBuoy, MessageCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, Button, EmptyState, Spinner } from "../../components/ui";
import { Section } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { TicketThread } from "./TicketThread";
import { ticketCategories, ticketStatus, type Ticket } from "./supportLabels";
import "./support.css";

/** «Soporte» (Fase 5 G6): tickets to Nexo's team, inside the application. */
export function SupportPage() {
  const { ticketId } = useParams();
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="kicker">Ayuda y soporte</span>
          <h1>Soporte</h1>
          <p>
            Escríbele al equipo de Nexo. Te avisaremos por correo cuando respondamos. Antes, quizá
            te sirva el <Link to="/help">centro de ayuda</Link>.
          </p>
        </div>
      </header>
      {ticketId ? <TicketView id={Number(ticketId)} /> : <TicketList />}
    </div>
  );
}

function TicketList() {
  const tickets = useQuery({
    queryKey: ["support", "tickets"],
    queryFn: () => api.get<Ticket[]>("/support/tickets").then(r => r.data),
  });
  return (
    <>
      <NewTicket />
      <Section title="Mis tickets" icon={<MessageCircle size={18} />}>
        {tickets.isPending ? (
          <Spinner label="Cargando tickets" />
        ) : !tickets.data?.length ? (
          <EmptyState
            icon={<LifeBuoy />}
            title="Sin tickets"
            description="Aquí verás tus consultas al equipo de Nexo."
          />
        ) : (
          <ul className="ticket-list">
            {tickets.data.map(ticket => {
              const status = ticketStatus[ticket.status] ?? ticketStatus.open;
              return (
                <li key={ticket.support_ticket_id}>
                  <Link to={`/support/${ticket.support_ticket_id}`}>
                    <strong>
                      #{ticket.support_ticket_id} · {ticket.subject}
                    </strong>
                    <small>
                      {ticketCategories[ticket.category]} · {ticket.requester_name} ·{" "}
                      {formatDateTime(ticket.updated_at)}
                    </small>
                  </Link>
                  <Badge tone={status.tone}>{status.label}</Badge>
                </li>
              );
            })}
          </ul>
        )}
      </Section>
    </>
  );
}

function NewTicket() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<Ticket>("/support/tickets", body).then(r => r.data),
    onSuccess: ticket => {
      client.invalidateQueries({ queryKey: ["support"] });
      navigate(`/support/${ticket.support_ticket_id}`);
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      subject: String(form.get("subject") ?? "").trim(),
      category: form.get("category"),
      priority: form.get("priority"),
      body: String(form.get("body") ?? "").trim(),
    });
  }
  return (
    <Section title="Nuevo ticket" icon={<LifeBuoy size={18} />}>
      <form className="support-form" onSubmit={submit}>
        <label className="form-field support-wide">
          <span>Asunto</span>
          <input name="subject" required minLength={4} maxLength={150} />
        </label>
        <label className="form-field">
          <span>Tema</span>
          <select name="category" defaultValue="uso">
            {Object.entries(ticketCategories).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Prioridad</span>
          <select name="priority" defaultValue="normal">
            <option value="normal">Normal</option>
            <option value="alta">Alta</option>
            <option value="urgente">Urgente (no podemos trabajar)</option>
          </select>
        </label>
        <label className="form-field support-wide">
          <span>Cuéntanos qué pasa</span>
          <textarea
            name="body"
            required
            minLength={10}
            rows={5}
            placeholder="Qué intentabas hacer, qué esperabas y qué ocurrió. No incluyas contraseñas."
          />
        </label>
        {create.error && (
          <div className="form-error support-wide" role="alert">
            {apiMessage(create.error)}
          </div>
        )}
        <div className="form-actions support-wide">
          <Button disabled={create.isPending}>Enviar a soporte</Button>
        </div>
      </form>
    </Section>
  );
}

function TicketView({ id }: { id: number }) {
  const client = useQueryClient();
  const [body, setBody] = useState("");
  const ticket = useQuery({
    queryKey: ["support", "ticket", id],
    queryFn: () => api.get<Ticket>(`/support/tickets/${id}`).then(r => r.data),
  });
  const reply = useMutation({
    mutationFn: () => api.post(`/support/tickets/${id}/messages`, { body }),
    onSuccess: () => {
      setBody("");
      client.invalidateQueries({ queryKey: ["support"] });
    },
  });
  if (ticket.isPending) return <Spinner label="Cargando ticket" />;
  if (ticket.isError)
    return (
      <p className="form-error" role="alert">
        {apiMessage(ticket.error)}
      </p>
    );
  const data = ticket.data;
  const status = ticketStatus[data.status] ?? ticketStatus.open;
  return (
    <Section
      title={`#${data.support_ticket_id} · ${data.subject}`}
      action={<Badge tone={status.tone}>{status.label}</Badge>}
    >
      <p>
        <Link to="/support">← Mis tickets</Link>
      </p>
      <TicketThread messages={data.messages ?? []} />
      {data.status !== "closed" && (
        <form
          className="support-form"
          onSubmit={event => {
            event.preventDefault();
            reply.mutate();
          }}
        >
          <label className="form-field support-wide">
            <span>Responder</span>
            <textarea value={body} onChange={event => setBody(event.target.value)} rows={3} />
          </label>
          {reply.error && (
            <div className="form-error support-wide" role="alert">
              {apiMessage(reply.error)}
            </div>
          )}
          <div className="form-actions support-wide">
            <Button disabled={reply.isPending || body.trim().length < 2}>Enviar respuesta</Button>
          </div>
        </form>
      )}
    </Section>
  );
}
