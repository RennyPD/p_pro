import { confirmAction } from "../../lib/confirm";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useDraftGuard } from "../../lib/useDraftGuard";

type Unverified = {
  enrollment_id: number;
  period: string;
  section_code: string;
  subject_name: string;
};
type Assignment = {
  assigned_version: string | null;
  operative_version: string;
  versions: string[];
  unverified: Unverified[];
};

export function CurriculumAssignmentPanel({ studentId }: { studentId: string }) {
  const endpoint = `/curriculum/students/${studentId}`;
  const assignment = useQuery({
    queryKey: ["curriculum-assignment", studentId],
    queryFn: () => api.get<Assignment>(`${endpoint}/assignment`).then(response => response.data),
  });
  const [entry, setEntry] = useState<Unverified | null>(null);

  return (
    <section className="panel dossier-panel">
      <h2>Pensum del estudiante</h2>
      {assignment.isPending ? (
        <Spinner />
      ) : assignment.isError ? (
        <p role="alert">
          {apiMessage(assignment.error)}{" "}
          <Button onClick={() => void assignment.refetch()}>Reintentar</Button>
        </p>
      ) : (
        <>
          <p>
            {assignment.data.assigned_version
              ? `Versión asignada · ${assignment.data.assigned_version}`
              : `Asignación institucional pendiente. Versión provisional · ${assignment.data.operative_version}`}
          </p>
          {assignment.data.versions.length ? (
            <CurriculumForm
              key={assignment.data.assigned_version ?? ""}
              studentId={studentId}
              endpoint={`${endpoint}/assignment`}
              versions={assignment.data.versions}
              initial={assignment.data.assigned_version ?? ""}
            />
          ) : (
            <p>Registra una versión en el pensum de la carrera para asignarla a este expediente.</p>
          )}
          {assignment.data.unverified.length > 0 && (
            <>
              <h3>Inscripciones con créditos por verificar</h3>
              <p>Registra los créditos originales cuando tengas respaldo institucional.</p>
              <ul>
                {assignment.data.unverified.map(item => (
                  <li key={item.enrollment_id}>
                    {item.subject_name} · {item.section_code} · {item.period}{" "}
                    <Button type="button" variant="secondary" onClick={() => setEntry(item)}>
                      Verificar créditos
                    </Button>
                  </li>
                ))}
              </ul>
              {entry && (
                <div className="panel dossier-panel">
                  <h4>
                    {entry.subject_name} · {entry.section_code} · {entry.period}
                  </h4>
                  <CurriculumForm
                    key={entry.enrollment_id}
                    studentId={studentId}
                    endpoint={`${endpoint}/enrollments/${entry.enrollment_id}/verified-credits`}
                    onClose={() => setEntry(null)}
                  />
                </div>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}

function CurriculumForm({
  studentId,
  endpoint,
  versions,
  initial = "",
  onClose,
}: {
  studentId: string;
  endpoint: string;
  versions?: string[];
  initial?: string;
  onClose?: () => void;
}) {
  const queryClient = useQueryClient();
  const [version, setVersion] = useState(initial);
  const [reason, setReason] = useState("");
  const [credits, setCredits] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useDraftGuard(Boolean(reason || credits || version !== initial), busy);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.put(endpoint, {
        version,
        reason,
        ...(versions ? {} : { credits: Number(credits) }),
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["curriculum-assignment", studentId] }),
        queryClient.invalidateQueries({ queryKey: ["student-transcript", studentId] }),
        queryClient.invalidateQueries({ queryKey: ["transcript"] }),
      ]);
      setReason("");
      toast.success(versions ? "Versión asignada" : "Créditos verificados");
      onClose?.();
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="resource-form" onSubmit={save}>
      <label className="form-field">
        <span>{versions ? "Versión del pensum" : "Versión original"}</span>
        {versions ? (
          <select
            required
            value={version}
            disabled={busy}
            onChange={event => setVersion(event.target.value)}
          >
            <option value="">Selecciona una versión</option>
            {versions.map(value => (
              <option key={value}>{value}</option>
            ))}
          </select>
        ) : (
          <input
            required
            maxLength={30}
            disabled={busy}
            value={version}
            onChange={event => setVersion(event.target.value)}
          />
        )}
      </label>
      {!versions && (
        <label className="form-field">
          <span>Créditos originales</span>
          <input
            required
            type="number"
            min={0}
            step="any"
            value={credits}
            disabled={busy}
            onChange={event => setCredits(event.target.value)}
          />
        </label>
      )}
      <label className="form-field">
        <span>
          {versions ? "Motivo de la asignación" : "Referencia del respaldo institucional"}
        </span>
        <input
          required
          minLength={3}
          maxLength={250}
          value={reason}
          disabled={busy}
          onChange={event => setReason(event.target.value)}
        />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        {onClose && (
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={async () => {
              if (
                !(reason || credits || version) ||
                (await confirmAction("¿Descartar la verificación?"))
              )
                onClose();
            }}
          >
            Cancelar
          </Button>
        )}
        <Button disabled={busy || (Boolean(versions) && version === initial)}>
          {busy ? "Guardando…" : versions ? "Asignar versión" : "Guardar verificación"}
        </Button>
      </div>
    </form>
  );
}
