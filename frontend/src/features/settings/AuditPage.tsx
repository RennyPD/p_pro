import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { LookupSelect } from "../../components/LookupSelect";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { auditActionLabel, auditActions, auditResourceLabel } from "../../lib/auditLabels";
import { ShieldCheck } from "lucide-react";

type Event = {
  audit_log_id: number;
  actor: string | null;
  user_id: number | null;
  action: string;
  resource: string;
  detail: string;
  created_at: string;
};
const size = 25;
const date = new Intl.DateTimeFormat("es-DO", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Santo_Domingo" });
const userLookup = { endpoint: "/users/", valueKey: "user_id", labelKeys: ["username"], secondaryKey: "email", placeholder: "Todas las cuentas" };
const actionOptions = Object.entries(auditActions).sort(([, a], [, b]) => a.localeCompare(b, "es"));

export function AuditPage() {
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [actor, setActor] = useState<number | string | null>(null);
  const events = useQuery({
    queryKey: ["audit", filters, page],
    queryFn: () => api.get<Event[]>("/audit/", { params: { ...filters, skip: page * size, limit: size } }).then(response => ({
      rows: response.data,
      more: response.headers["x-has-more"] === "true",
    })),
  });

  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(
      [...new FormData(event.currentTarget)].map(([key, value]) => [key, String(value).trim()]).filter(([, value]) => value),
    );
    setFilters(actor ? { ...values, user_id: String(actor) } : values);
    setPage(0);
  }

  return <div className="page">
    <header className="page-header"><div><span className="kicker">Configuración · Supervisión</span><h1>Auditoría administrativa</h1><p>Quién hizo cada cambio sensible y cuándo.</p></div></header>
    <form className="panel audit-filters" onSubmit={filter}>
      <label className="form-field"><span>Acción</span><select name="action" defaultValue=""><option value="">Todas las acciones</option>{actionOptions.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
      <div className="form-field"><span id="audit-actor">Cuenta</span><LookupSelect config={userLookup} value={actor} onChange={setActor} labelId="audit-actor" /></div>
      <label className="form-field"><span>Desde</span><input name="start" type="date" /></label>
      <label className="form-field"><span>Hasta</span><input name="end" type="date" /></label>
      <Button>Filtrar</Button>
    </form>
    {events.isLoading ? <Spinner label="Cargando eventos" /> : events.error ? (
      <p role="alert" className="form-error">{apiMessage(events.error)}</p>
    ) : !events.data?.rows.length ? <EmptyState icon={<ShieldCheck />} title="Sin eventos" description="No hay eventos para estos filtros." /> : (
      <div className="panel table-scroll"><table>
        <thead><tr><th>Fecha</th><th>Cuenta</th><th>Acción</th><th>Recurso</th><th>Detalle</th></tr></thead>
        <tbody>{events.data.rows.map(event => <tr key={event.audit_log_id}>
          <td>{date.format(new Date(event.created_at))}</td><td>{event.actor ?? "Sin cuenta registrada"}</td>
          <td title={event.action}>{auditActionLabel(event.action)}</td><td title={event.resource}>{auditResourceLabel(event.resource)}</td><td>{event.detail || "—"}</td>
        </tr>)}</tbody>
      </table></div>
    )}
    <div className="pagination">
      <Button variant="secondary" disabled={page === 0 || events.isFetching} onClick={() => setPage(current => current - 1)}>Anterior</Button>
      <span className="pagination__page">Página {page + 1}</span>
      <Button variant="secondary" disabled={!events.data?.more || events.isFetching} onClick={() => setPage(current => current + 1)}>Siguiente</Button>
    </div>
  </div>;
}
