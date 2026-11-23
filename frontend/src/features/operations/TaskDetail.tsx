import { confirmAction } from "../../lib/confirm";
import { DocumentDownload } from "../../components/DocumentDownload";
import { formatDateTime } from "../../lib/format";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarClock, Info, Target } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Badge, Button, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./operations.css";
import { type Task, type Row, labels, date, state } from "./operationsShared";
import { SubmissionReview } from "./SubmissionReview";

export function TaskDetail({
  task,
  manager,
  student,
  userId,
  onClose,
  onSaved,
}: {
  task: Task;
  manager: boolean;
  student: boolean;
  userId?: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [content, setContent] = useState(task.submission?.content ?? ""),
    [reason, setReason] = useState("");
  const attachmentInput = useRef<HTMLInputElement>(null);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [attemptId, setAttemptId] = useState<number | null>(null);
  const roster = useQuery<Row[]>({
    queryKey: ["task-roster", userId, task.assignment_id],
    queryFn: () =>
      api.get(`/operations/assignments/${task.assignment_id}/submissions`).then(r => r.data),
    enabled: manager,
  });
  const revisions = useQuery<
    { revision_id: number; content: string; submitted_at: string; filename?: string | null }[]
  >({
    queryKey: ["task-attempts", userId, attemptId],
    queryFn: () => api.get(`/operations/submissions/${attemptId}/revisions`).then(r => r.data),
    enabled: Boolean(attemptId),
  });
  const send = useMutation({
    mutationFn: async () => {
      let fileData;
      if (attachment) {
        if (attachment.size > 5 * 1024 * 1024)
          throw new Error("Selecciona un archivo de hasta 5 MB.");
        const content_base64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
          reader.onerror = () => reject(new Error("Selecciona de nuevo el archivo."));
          reader.readAsDataURL(attachment);
        });
        fileData = { filename: attachment.name, mime_type: attachment.type, content_base64 };
      }
      return api.post(
        `/operations/assignments/${task.assignment_id}/submit`,
        fileData ? { content, attachment: fileData } : { content },
      );
    },
    onSuccess: () => {
      toast.success("Entrega registrada");
      setAttachment(null);
      if (attachmentInput.current) attachmentInput.current.value = "";
      onSaved();
    },
    onError: e =>
      toast.error(
        e instanceof Error && !("response" in e) && !("isAxiosError" in e)
          ? e.message
          : apiMessage(e),
      ),
  });
  const transfer = useMutation({
    mutationFn: () =>
      api.post(`/operations/assignments/${task.assignment_id}/transfer-grades`, { reason }),
    onSuccess: () => {
      toast.success("Notas enviadas como borradores. Revísalas y publícalas en Evaluaciones.");
      onSaved();
    },
    onError: e => toast.error(apiMessage(e)),
  });
  const canSend =
    task.published &&
    task.lifecycle === "open" &&
    (!task.submission || (task.allow_resubmit && task.submission.score === null)) &&
    (date(task.due_at) >= new Date() || task.allow_late);
  return (
    <Modal
      title={task.title}
      description={`${task.subject_name} · ${task.section_code} · ${task.teacher_name}`}
      onClose={onClose}
    >
      <div className="operations-detail task-detail">
        <div className="task-facts">
          <Badge tone={task.submission?.score != null ? "success" : "info"}>{state(task)}</Badge>
          <span>
            <CalendarClock size={15} /> Vence {formatDateTime(task.due_at)}
          </span>
          <span>
            <Target size={15} /> {task.max_score} puntos
          </span>
          <span title={task.allow_late ? "Acepta entregas tardías" : "No admite entregas tardías"}>
            {task.allow_late ? "Admite tardías" : "Sin entregas tardías"}
          </span>
          {task.allow_resubmit && <span>Reenvío antes de calificar</span>}
        </div>
        <p className="preserve-lines task-instructions">{task.instructions}</p>
        {student && (
          <section className="task-mine">
            <h3>Mi entrega</h3>
            {task.submission && (
              <>
                {task.submission.score !== null && (
                  <div className="task-result">
                    <strong>
                      {task.submission.score}
                      <small>/{task.max_score}</small>
                    </strong>
                    <div>
                      <span>Resultado de la tarea</span>
                      <p>{task.submission.feedback || "Sin comentario del docente"}</p>
                    </div>
                  </div>
                )}
                <p className="task-meta">
                  {labels[task.submission.status]} el {formatDateTime(task.submission.submitted_at)}
                  {date(task.submission.submitted_at) > date(task.due_at) && (
                    <Badge tone="warning">Tardía</Badge>
                  )}
                  <button
                    type="button"
                    className="text-link"
                    onClick={() => setAttemptId(task.submission!.submission_id)}
                  >
                    {task.submission.attempts > 1
                      ? `Ver ${task.submission.attempts} intentos`
                      : "Ver intento"}
                  </button>
                </p>
                <blockquote className="preserve-lines task-content">
                  {task.submission.content}
                </blockquote>
              </>
            )}
            {canSend ? (
              <form
                className="operations-form"
                onSubmit={e => {
                  e.preventDefault();
                  send.mutate();
                }}
              >
                <label>
                  {task.submission ? "Actualizar entrega" : "Contenido de la entrega"}
                  <textarea
                    maxLength={20000}
                    value={content}
                    onChange={e => setContent(e.target.value)}
                  />
                </label>
                <label>
                  Adjunto opcional (PDF, PNG o JPEG, hasta 5 MB)
                  <input
                    ref={attachmentInput}
                    disabled={send.isPending}
                    type="file"
                    accept="application/pdf,image/png,image/jpeg"
                    onChange={event => setAttachment(event.target.files?.[0] ?? null)}
                  />
                </label>
                <Button disabled={send.isPending || (!content.trim() && !attachment)}>
                  {task.submission ? "Reenviar" : "Entregar tarea"}
                </Button>
              </form>
            ) : (
              !task.submission && <p className="muted">El plazo de entrega terminó.</p>
            )}
            {task.assessment_id && (
              <p className="task-note">
                <Info size={15} /> Cuenta para la evaluación del curso cuando el docente publique la
                nota en Mis notas.
              </p>
            )}
          </section>
        )}
        {manager && (
          <section>
            <h3>Estudiantes y entregas</h3>
            {roster.isLoading && <Spinner />}
            {roster.error && <p role="alert">{apiMessage(roster.error)}</p>}
            <div className="submission-roster">
              {roster.data?.map(row => (
                <SubmissionReview
                  key={`${row.student_id}-${row.submission?.score}-${row.submission?.feedback}`}
                  row={row}
                  task={task}
                  onSaved={onSaved}
                  onAttempts={setAttemptId}
                />
              ))}
            </div>
            {task.assessment_id && (
              <form
                className="operations-form"
                onSubmit={async e => {
                  e.preventDefault();
                  if (
                    await confirmAction(
                      "Se crearán notas borrador, sin publicar ni sobrescribir notas existentes. ¿Continuar?",
                    )
                  )
                    transfer.mutate();
                }}
              >
                <h3>Enviar resultados a Evaluaciones</h3>
                <p>
                  Convierte a escala 100. Si existe alguna nota, la transferencia se detiene
                  completa para protegerla.
                </p>
                <label>
                  Motivo
                  <input
                    required
                    minLength={2}
                    maxLength={250}
                    value={reason}
                    onChange={e => setReason(e.target.value)}
                  />
                </label>
                <Button disabled={transfer.isPending || task.lifecycle === "archived"}>
                  Crear notas borrador
                </Button>
                <Link to={`/assessments?section=${task.section_id}`}>Abrir Evaluaciones →</Link>
              </form>
            )}
          </section>
        )}
        {attemptId && (
          <section>
            <h3>Historial de entregas</h3>
            {revisions.isLoading && <Spinner />}
            {revisions.error && <p role="alert">{apiMessage(revisions.error)}</p>}
            {revisions.data?.map((r, i) => (
              <article className="attempt-card" key={r.revision_id}>
                <strong>
                  Intento {i + 1} · {formatDateTime(r.submitted_at)}
                </strong>
                <p className="preserve-lines">{r.content}</p>
                {r.filename && (
                  <DocumentDownload
                    path={`/operations/submissions/${attemptId}/revisions/${r.revision_id}/attachment`}
                    filename={r.filename}
                    label={`Descargar ${r.filename}`}
                  />
                )}
              </article>
            ))}
          </section>
        )}
      </div>
    </Modal>
  );
}
