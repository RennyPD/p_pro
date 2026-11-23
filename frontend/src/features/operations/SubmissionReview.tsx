import { formatDateTime } from "../../lib/format";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, Button } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./operations.css";
import { type Task, type Row, labels, date } from "./operationsShared";

export function SubmissionReview({
  row,
  task,
  onSaved,
  onAttempts,
}: {
  row: Row;
  task: Task;
  onSaved: () => void;
  onAttempts: (id: number) => void;
}) {
  const item = row.submission;
  const [open, setOpen] = useState(false),
    [score, setScore] = useState(String(item?.score ?? "")),
    [feedback, setFeedback] = useState(item?.feedback ?? "");
  const grade = useMutation({
    mutationFn: () =>
      api.patch(`/operations/submissions/${item!.submission_id}/grade`, {
        score: Number(score),
        feedback,
      }),
    onSuccess: () => {
      toast.success("Devolución guardada");
      onSaved();
    },
    onError: e => toast.error(apiMessage(e)),
  });
  return (
    <article className="submission-review">
      <div className="operations-actions">
        <div>
          <strong>{row.student_name}</strong>
          <small>{row.enrollment_number}</small>
        </div>
        <Badge>{item ? labels[item.status] : "Sin entrega"}</Badge>
        {item && (
          <Button variant="secondary" onClick={() => setOpen(!open)}>
            {open ? "Ocultar" : "Revisar"}
          </Button>
        )}
      </div>
      {open && item && (
        <>
          <p>
            {formatDateTime(item.submitted_at)}
            {date(item.submitted_at) > date(task.due_at) ? " · Entrega tardía" : ""}
          </p>
          <p className="preserve-lines">{item.content}</p>
          <Button variant="ghost" onClick={() => onAttempts(item.submission_id)}>
            Ver {item.attempts} intento(s)
          </Button>
          <form
            className="operations-form"
            onSubmit={e => {
              e.preventDefault();
              grade.mutate();
            }}
          >
            <label>
              Puntuación / {task.max_score}
              <input
                required
                type="number"
                min="0"
                max={task.max_score}
                step="any"
                value={score}
                onChange={e => setScore(e.target.value)}
              />
            </label>
            <label>
              Devolución al estudiante
              <textarea value={feedback} onChange={e => setFeedback(e.target.value)} />
            </label>
            <Button disabled={grade.isPending || task.lifecycle === "archived"}>
              Guardar devolución
            </Button>
          </form>
        </>
      )}
    </article>
  );
}
