import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Button, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useDraftGuard } from "../../lib/useDraftGuard";
import { useAuthStore } from "../../store/auth";

type Plan = {
  lesson_plan_id: number;
  scheduled_date: string;
  title: string;
  content: string;
  competencies: string;
  status: "planned" | "delivered" | "cancelled";
};
const stateLabels = { planned: "Programado", delivered: "Impartido", cancelled: "Cancelado" };
const endpoint = "/operations/lesson-plans";

export function LessonPlansDialog({ sectionId, onClose }: { sectionId: string; onClose: () => void }) {
  const user = useAuthStore(state => state.user);
  const client = useQueryClient();
  const [editing, setEditing] = useState<Plan | "new" | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const key = ["lesson-plans", sectionId, user?.user_id];
  const plans = useQuery({
    queryKey: key, queryFn: () => api.get<Plan[]>(endpoint, { params: { section_id: sectionId } }).then(response => response.data),
  });
  const plan = editing === "new" ? null : editing;
  useDraftGuard(dirty, busy);

  function close() {
    if (busy || (dirty && !window.confirm("¿Descartar cambios del plan de clase?"))) return;
    if (editing) {
      setEditing(null);
      setError("");
      setDirty(false);
    } else onClose();
  }
  async function change(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      setEditing(null);
      setDirty(false);
      await client.invalidateQueries({ queryKey: key });
    } catch (failure) { setError(apiMessage(failure)); }
    finally { setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    const data = { ...fields, section_id: Number(sectionId), status: "planned" };
    void change(() => plan ? api.put(`${endpoint}/${plan.lesson_plan_id}`, data) : api.post(endpoint, data));
  }
  return <Modal title="Planes de clase de la sección" onClose={close}>
    {plans.isLoading ? <Spinner label="Cargando planes" /> : plans.error ? <p role="alert">{apiMessage(plans.error)}</p> : !editing && <>
      {!plans.data?.length && <p>Aún no hay planes de clase.</p>}
      {plans.data?.map(item => <article className="panel" key={item.lesson_plan_id}>
        <h3>{item.title}</h3><p>{item.scheduled_date} · {stateLabels[item.status]}</p>
        <p className="preserve-lines">{item.content}</p>
        {item.competencies && <p>Competencias · {item.competencies}</p>}
        {item.status === "planned" && <div className="form-actions">
          <Button variant="secondary" disabled={busy} onClick={() => { setEditing(item); setError(""); }}>Editar plan</Button>
          <Button variant="secondary" disabled={busy} onClick={() => {
            if (window.confirm(`¿Marcar «${item.title}» como impartido?`)) void change(() => api.patch(`${endpoint}/${item.lesson_plan_id}/status`, { status: "delivered" }));
          }}>Marcar impartido</Button>
          <Button variant="danger" disabled={busy} onClick={() => {
            if (window.confirm(`¿Cancelar «${item.title}»?`)) void change(() => api.patch(`${endpoint}/${item.lesson_plan_id}/status`, { status: "cancelled" }));
          }}>Cancelar plan</Button>
        </div>}
      </article>)}
      <Button disabled={busy} onClick={() => { setEditing("new"); setError(""); }}>Nuevo plan</Button>
    </>}
    {editing && <form className="resource-form" onSubmit={submit} onChange={() => setDirty(true)}>
      <label className="form-field"><span>Título</span><input name="title" defaultValue={plan?.title} required minLength={2} maxLength={150} /></label>
      <label className="form-field"><span>Fecha de clase</span><input name="scheduled_date" type="date" defaultValue={plan?.scheduled_date} required /></label>
      <label className="form-field"><span>Contenido de la clase</span><textarea name="content" rows={4} defaultValue={plan?.content} required minLength={2} /></label>
      <label className="form-field"><span>Competencias</span><textarea name="competencies" rows={2} defaultValue={plan?.competencies} /></label>
      <div className="form-actions">
        <Button type="button" variant="secondary" disabled={busy} onClick={close}>Cancelar edición</Button>
        <Button disabled={busy}>{busy ? "Guardando…" : "Guardar plan"}</Button>
      </div>
    </form>}
    {error && <p role="alert" className="form-error">{error}</p>}
  </Modal>;
}
