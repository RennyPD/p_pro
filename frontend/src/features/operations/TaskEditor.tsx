import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button, Modal } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./operations.css";
import { type Section, type Task, inputDate } from "./operationsShared";

export function TaskEditor({
  task,
  sections,
  userId,
  onClose,
  onSaved,
}: {
  task: Task | "new";
  sections: Section[];
  userId?: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const existing = task !== "new" ? task : null;
  const [form, setForm] = useState({
    section_id: String(existing?.section_id ?? ""),
    title: existing?.title ?? "",
    instructions: existing?.instructions ?? "",
    due_at: existing ? inputDate(existing.due_at) : "",
    max_score: String(existing?.max_score ?? 100),
    assessment_id: String(existing?.assessment_id ?? ""),
    published: existing?.published ?? false,
    lifecycle: existing?.lifecycle ?? "open",
    allow_late: existing?.allow_late ?? false,
    allow_resubmit: existing?.allow_resubmit ?? true,
  });
  const assessments = useQuery<{ assessment_id: number; name: string; closed: boolean }[]>({
    queryKey: ["task-assessments", userId, form.section_id],
    queryFn: () => api.get(`/assessments/sections/${form.section_id}`).then(r => r.data),
    enabled: Boolean(form.section_id),
  });
  const save = useMutation({
    mutationFn: () => {
      const body = {
        ...form,
        section_id: Number(form.section_id),
        max_score: Number(form.max_score),
        assessment_id: form.assessment_id ? Number(form.assessment_id) : null,
        due_at: new Date(form.due_at).toISOString(),
      };
      return existing
        ? api.put(`/operations/assignments/${existing.assignment_id}`, body)
        : api.post("/operations/assignments", body);
    },
    onSuccess: () => {
      toast.success("Tarea guardada");
      onSaved();
      onClose();
    },
    onError: e => toast.error(apiMessage(e)),
  });
  return (
    <Modal title={existing ? "Editar tarea" : "Nueva tarea"} onClose={onClose}>
      <form
        className="operations-form"
        onSubmit={e => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <label>
          Asignatura y sección
          <select
            required
            value={form.section_id}
            disabled={Boolean(existing)}
            onChange={e => setForm({ ...form, section_id: e.target.value, assessment_id: "" })}
          >
            <option value="">Selecciona una sección</option>
            {sections.map(s => (
              <option key={s.section_id} value={s.section_id}>
                {s.subject_name} · {s.code} · {s.period_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Título
          <input
            required
            minLength={2}
            maxLength={150}
            value={form.title}
            onChange={e => setForm({ ...form, title: e.target.value })}
          />
        </label>
        <label>
          Instrucciones
          <textarea
            required
            minLength={2}
            value={form.instructions}
            onChange={e => setForm({ ...form, instructions: e.target.value })}
            placeholder="Objetivo, qué entregar y cómo se revisará"
          />
        </label>
        <label>
          Fecha y hora límite
          <input
            required
            type="datetime-local"
            value={form.due_at}
            onChange={e => setForm({ ...form, due_at: e.target.value })}
          />
        </label>
        <label>
          Puntuación máxima
          <input
            required
            type="number"
            min="1"
            max="1000"
            step="any"
            value={form.max_score}
            onChange={e => setForm({ ...form, max_score: e.target.value })}
          />
        </label>
        <label>
          Relación con evaluaciones
          <select
            value={form.assessment_id}
            onChange={e => setForm({ ...form, assessment_id: e.target.value })}
          >
            <option value="">Práctica, sin impacto en la nota</option>
            {assessments.data?.map(a => (
              <option disabled={a.closed} key={a.assessment_id} value={a.assessment_id}>
                {a.name}
                {a.closed ? " · Cerrada" : ""}
              </option>
            ))}
          </select>
        </label>
        {assessments.error && <p role="alert">{apiMessage(assessments.error)}</p>}
        <p>
          Una tarea por evaluación. La puntuación se normaliza a 100 y se transfiere como borrador
          mediante una acción explícita.
        </p>
        <label>
          Estado
          <select
            value={form.lifecycle}
            onChange={e => setForm({ ...form, lifecycle: e.target.value })}
          >
            <option value="open">Abierta</option>
            <option value="closed">Cerrada: no recibe entregas</option>
            <option value="archived">Archivada: solo consulta</option>
          </select>
        </label>
        {(["published", "allow_late", "allow_resubmit"] as const).map(k => (
          <label className="operations-check" key={k}>
            <input
              type="checkbox"
              checked={form[k]}
              onChange={e => setForm({ ...form, [k]: e.target.checked })}
            />
            {
              {
                published: "Publicada para estudiantes",
                allow_late: "Aceptar entregas tardías",
                allow_resubmit: "Permitir reenvíos antes de calificar",
              }[k]
            }
          </label>
        ))}
        <Button disabled={save.isPending}>Guardar tarea</Button>
      </form>
    </Modal>
  );
}
