import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button, Modal } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./operations.css";
import { type Section, type Event, labels, inputDate } from "./operationsShared";

export function EventEditor({
  event,
  sections,
  manager,
  admin,
  onClose,
  onSaved,
}: {
  event: Event | "new";
  sections: Section[];
  manager: boolean;
  admin: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const item = event === "new" ? null : event;
  const [form, setForm] = useState({
    title: item?.title ?? "",
    description: item?.description ?? "",
    event_type: item?.kind ?? "activity",
    audience: item?.audience ?? (admin ? "all" : "section"),
    section_id: String(item?.section_id ?? ""),
    starts_at: item ? inputDate(item.starts_at) : "",
    ends_at: item ? inputDate(item.ends_at) : "",
    no_school: item?.no_school ?? false,
  });
  const editable = manager && (admin || item?.audience === "section" || !item);
  const save = useMutation({
    mutationFn: () => {
      const body = {
        ...form,
        section_id: form.audience === "section" ? Number(form.section_id) : null,
        starts_at: new Date(form.starts_at).toISOString(),
        ends_at: new Date(form.ends_at).toISOString(),
      };
      return item
        ? api.put(`/operations/calendar/${item.event_id}`, body)
        : api.post("/operations/calendar", body);
    },
    onSuccess: () => {
      toast.success("Evento guardado");
      onSaved();
      onClose();
    },
    onError: e => toast.error(apiMessage(e)),
  });
  return (
    <Modal title={item ? "Evento académico" : "Nuevo evento"} onClose={onClose}>
      <form
        className="operations-form"
        onSubmit={e => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <fieldset disabled={!editable}>
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
            Descripción
            <textarea
              value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
            />
          </label>
          <label>
            Tipo
            <select
              value={form.event_type}
              onChange={e => setForm({ ...form, event_type: e.target.value })}
            >
              {Object.entries(labels)
                .slice(0, 5)
                .map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Destinatarios
            <select
              value={form.audience}
              onChange={e => setForm({ ...form, audience: e.target.value })}
            >
              {(admin || !editable
                ? [
                    ["all", "Toda la institución"],
                    ["student", "Estudiantes"],
                    ["teacher", "Docentes"],
                    ["admin", "Administradores"],
                    ["guardian", "Tutores"],
                    ["section", "Una sección"],
                  ]
                : [["section", "Una sección"]]
              ).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          {form.audience === "section" && (
            <label>
              Sección
              <select
                required
                value={form.section_id}
                onChange={e => setForm({ ...form, section_id: e.target.value })}
              >
                <option value="">Selecciona una sección</option>
                {sections.map(s => (
                  <option key={s.section_id} value={s.section_id}>
                    {s.subject_name} · {s.code}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Inicio
            <input
              required
              type="datetime-local"
              value={form.starts_at}
              onChange={e => setForm({ ...form, starts_at: e.target.value })}
            />
          </label>
          <label>
            Fin
            <input
              required
              type="datetime-local"
              value={form.ends_at}
              onChange={e => setForm({ ...form, ends_at: e.target.value })}
            />
          </label>
          <label className="operations-check">
            <input
              type="checkbox"
              checked={form.no_school}
              onChange={e => setForm({ ...form, no_school: e.target.checked })}
            />
            Día no lectivo (marca informativa)
          </label>
        </fieldset>
        {editable && <Button disabled={save.isPending}>Guardar evento</Button>}
      </form>
    </Modal>
  );
}
