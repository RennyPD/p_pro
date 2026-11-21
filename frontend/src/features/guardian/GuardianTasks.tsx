import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Pager } from "../../components/Pager";
import { Badge, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import type { Tone } from "../../lib/academicResult";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDateTime } from "../../lib/format";
import { Loaded } from "./guardianShared";

type Task = ApiSchema<"GuardianTask">;
const PAGE = 10;
const FILTERS = [
  { key: "", label: "Todas" },
  { key: "pending", label: "Pendientes" },
  { key: "overdue", label: "Vencidas" },
  { key: "submitted", label: "Entregadas" },
  { key: "graded", label: "Calificadas" },
] as const;
const STATUS: Record<string, { label: string; tone: Tone }> = {
  pending: { label: "Pendiente", tone: "info" },
  overdue: { label: "Vencida", tone: "danger" },
  submitted: { label: "Entregada", tone: "neutral" },
  graded: { label: "Calificada", tone: "success" },
};

export function GuardianTasks({ studentId }: { studentId: number }) {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const query = useQuery({
    queryKey: ["guardian", studentId, "tasks", status, page],
    queryFn: () =>
      api
        .get<Task[]>(`/guardian/students/${studentId}/tasks`, {
          params: { status: status || undefined, skip: page * PAGE, limit: PAGE },
        })
        .then(response => ({
          items: response.data,
          total: Number(response.headers["x-total-count"] ?? response.data.length),
        })),
  });
  return (
    <>
      <div className="guardian-filters" role="group" aria-label="Filtrar tareas">
        {FILTERS.map(item => (
          <button
            key={item.key}
            type="button"
            aria-pressed={status === item.key}
            className={status === item.key ? "is-active" : undefined}
            onClick={() => {
              setStatus(item.key);
              setPage(0);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      {query.isFetching && !query.isPending && <Spinner label="Actualizando" />}
      <Loaded query={query}>
        {data =>
          data.items.length ? (
            <>
              <ul className="guardian-cards">
                {data.items.map(task => {
                  const state = STATUS[task.status] ?? STATUS.pending;
                  return (
                    <li key={task.assignment_id} className="panel guardian-task">
                      <div>
                        <strong>{task.title}</strong>
                        <small>
                          {task.subject_name} · entrega {formatDateTime(task.due_at)}
                        </small>
                        {task.status === "graded" && task.feedback && <p>{task.feedback}</p>}
                      </div>
                      <div className="guardian-result">
                        <Badge tone={state.tone}>{state.label}</Badge>
                        {task.score !== null && task.score !== undefined && (
                          <span className="guardian-figure">
                            {task.score}/{task.max_score}
                          </span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
              <Pager
                page={page}
                pageSize={PAGE}
                total={data.total}
                onPage={setPage}
                label="tareas"
              />
            </>
          ) : (
            <p className="muted">No hay tareas en esta vista.</p>
          )
        }
      </Loaded>
    </>
  );
}
