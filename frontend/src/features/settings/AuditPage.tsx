import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Button, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";

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
const date = new Intl.DateTimeFormat("es-DO", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Santo_Domingo",
});

export function AuditPage() {
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const events = useQuery({
    queryKey: ["audit", filters, page],
    queryFn: () =>
      api
        .get<Event[]>("/audit/", { params: { ...filters, skip: page * size, limit: size } })
        .then(response => ({
          rows: response.data,
          more: response.headers["x-has-more"] === "true",
        })),
  });

  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilters(
      Object.fromEntries(
        [...new FormData(event.currentTarget)]
          .map(([key, value]) => [key, String(value).trim()])
          .filter(([, value]) => value),
      ),
    );
    setPage(0);
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Auditoría administrativa</h1>
      </header>
      <form className="panel resource-form" onSubmit={filter}>
        <label className="form-field">
          <span>Acción exacta</span>
          <input name="action" placeholder="section.published" />
        </label>
        <label className="form-field">
          <span>Recurso</span>
          <input name="resource" placeholder="section:12" />
        </label>
        <label className="form-field">
          <span>ID de cuenta del actor</span>
          <input name="user_id" type="number" min="1" />
        </label>
        <label className="form-field">
          <span>Desde</span>
          <input name="start" type="date" />
        </label>
        <label className="form-field">
          <span>Hasta</span>
          <input name="end" type="date" />
        </label>
        <Button>Aplicar filtros</Button>
      </form>
      {events.isLoading ? (
        <Spinner label="Cargando eventos" />
      ) : events.error ? (
        <p role="alert" className="form-error">
          {apiMessage(events.error)}
        </p>
      ) : !events.data?.rows.length ? (
        <p>No hay eventos para estos filtros.</p>
      ) : (
        <div className="panel table-scroll">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Actor</th>
                <th>Acción</th>
                <th>Recurso</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {events.data.rows.map(event => (
                <tr key={event.audit_log_id}>
                  <td>{date.format(new Date(event.created_at))}</td>
                  <td>{event.actor ?? "Sin cuenta registrada"}</td>
                  <td>{event.action}</td>
                  <td>{event.resource}</td>
                  <td>{event.detail || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <Button
          variant="secondary"
          disabled={page === 0 || events.isFetching}
          onClick={() => setPage(current => current - 1)}
        >
          Anterior
        </Button>
        <span>Página {page + 1}</span>
        <Button
          variant="secondary"
          disabled={!events.data?.more || events.isFetching}
          onClick={() => setPage(current => current + 1)}
        >
          Siguiente
        </Button>
      </div>
    </div>
  );
}
