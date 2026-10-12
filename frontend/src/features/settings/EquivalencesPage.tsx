import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./equivalences.css";

type Career = { career_id: number; code: string; name: string };
type Subject = { subject_id: number; code: string; description: string };
type Rule = { course_equivalence_id: number; career_id: number; career_name: string; career_code: string; source_subject_id: number; source_code: string; source_name: string; target_subject_id: number; target_code: string; target_name: string; curriculum_version: string; active: boolean; notes: string };
type Context = { active_version: string; versions: string[]; courses: { subject_id: number; code: string; name: string; version: string; credits: number }[] };
type Impact = { affected_students: number; gained_subjects: number; lost_subjects: number; truncated: boolean; applies_to_current_version: boolean; students: { student_id: number; student_name: string; enrollment_number: string; gained: string[]; lost: string[]; credit_delta: number }[] };
type History = { audit_log_id: number; actor: string; action: string; detail: string; created_at: string };
async function all<T>(path: string): Promise<T[]> {
  const rows: T[] = [];
  for (let skip = 0; ; skip += 100) {
    const { data } = await api.get<T[]>(path, { params: { skip, limit: 100 } });
    rows.push(...data);
    if (data.length < 100) return rows;
  }
}
function ImpactView({ value }: { value: Impact }) {
  return <section className="equivalence-impact" aria-label="Impacto previsto">
    <h3>Impacto previsto (sin guardar)</h3>
    <p>{value.affected_students} estudiantes afectados · {value.gained_subjects} reconocimientos añadidos · {value.lost_subjects} retirados.</p>
    {!value.applies_to_current_version && <p>Esta versión no es la activa: no modifica el progreso actual.</p>}
    <p>Sin calificaciones nuevas. Desactivar una regla puede retirar créditos y requisitos reconocidos, incluidas sus cadenas.</p>
    {value.students.map(s => <article key={s.student_id}><strong>{s.enrollment_number} · {s.student_name}</strong><span>{s.gained.length ? "Añade: " + s.gained.join(", ") : ""} {s.lost.length ? "Retira: " + s.lost.join(", ") : ""} · Créditos: {s.credit_delta > 0 ? "+" : ""}{s.credit_delta}</span></article>)}
    {value.truncated && <p>Se muestran los primeros 100 estudiantes; los totales incluyen a todos.</p>}
  </section>;
}
export function EquivalencesPage() {
  const client = useQueryClient();
  const uid = useAuthStore(s => s.user?.user_id);
  const [career, setCareer] = useState("");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [chosenVersion, setVersion] = useState("");
  const [notes, setNotes] = useState("");
  const [reason, setReason] = useState("");
  const [active, setActive] = useState(true);
  const [sourceSearch, setSourceSearch] = useState("");
  const [targetSearch, setTargetSearch] = useState("");
  const [search, setSearch] = useState("");
  const [filterCareer, setFilterCareer] = useState("");
  const [filterState, setFilterState] = useState("");
  const [filterVersion, setFilterVersion] = useState("");
  const [preview, setPreview] = useState<Impact>();
  const [editing, setEditing] = useState<Rule>();
  const [editNotes, setEditNotes] = useState("");
  const [editReason, setEditReason] = useState("");
  const [editActive, setEditActive] = useState(false);
  const [editImpact, setEditImpact] = useState<Impact>();
  const [historyId, setHistoryId] = useState<number>();
  const careers = useQuery({ queryKey: ["equivalence-careers", uid], queryFn: () => all<Career>("/careers/") });
  const subjects = useQuery({ queryKey: ["equivalence-subjects", uid], queryFn: () => all<Subject>("/subjects/") });
  const rules = useQuery({ queryKey: ["equivalences", uid], queryFn: () => all<Rule>("/governance/equivalences") });
  const context = useQuery({ queryKey: ["equivalence-context", uid, career], queryFn: () => api.get<Context>(`/governance/equivalences/context/${career}`).then(r => r.data), enabled: Boolean(career) });
  const history = useQuery({ queryKey: ["equivalence-history", uid, historyId], queryFn: () => api.get<History[]>(`/governance/equivalences/${historyId}/history`).then(r => r.data), enabled: Boolean(historyId) });
  const version = chosenVersion || (context.data?.versions.includes(context.data.active_version) ? context.data.active_version : context.data?.versions[0]) || "";
  const payload = { career_id: Number(career), source_subject_id: Number(source), target_subject_id: Number(target), curriculum_version: version, notes, reason, active };
  function invalidate() {
    for (const key of ["equivalences", "equivalence-history", "my-progress", "graduation-audit", "transcript", "course-catalog", "student-profile"]) void client.invalidateQueries({ queryKey: [key] });
  }
  const create = useMutation({ mutationFn: () => api.post("/governance/equivalences", payload), onSuccess: () => { toast.success("Regla registrada"); setSource(""); setTarget(""); setReason(""); setNotes(""); setPreview(undefined); invalidate(); }, onError: e => toast.error(apiMessage(e)) });
  const inspect = useMutation({ mutationFn: () => api.post<Impact>("/governance/equivalences/preview", payload).then(r => r.data), onSuccess: setPreview, onError: e => toast.error(apiMessage(e)) });
  const inspectEdit = useMutation({ mutationFn: () => api.get<Impact>(`/governance/equivalences/${editing?.course_equivalence_id}/impact`, { params: { active: editActive } }).then(r => r.data), onSuccess: setEditImpact, onError: e => toast.error(apiMessage(e)) });
  const update = useMutation({ mutationFn: () => api.patch(`/governance/equivalences/${editing?.course_equivalence_id}`, { notes: editNotes, reason: editReason, active: editActive }), onSuccess: () => { toast.success("Regla actualizada"); setEditing(undefined); invalidate(); }, onError: e => toast.error(apiMessage(e)) });
  const busy = create.isPending || inspect.isPending;
  const visible = (rules.data || []).filter(r => (!filterCareer || r.career_id === Number(filterCareer)) && (!filterState || String(r.active) === filterState) && (!filterVersion || r.curriculum_version === filterVersion) && `${r.career_name} ${r.source_code} ${r.source_name} ${r.target_code} ${r.target_name} ${r.notes}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  if (careers.isLoading || subjects.isLoading || rules.isLoading) return <div className="page"><Spinner /></div>;
  const loadError = careers.error || subjects.error || rules.error;
  return <div className="page equivalences-page">
    <header className="page-header"><div><span className="kicker">Gobierno curricular</span><h1>Reglas de equivalencia</h1><p>Una asignatura aprobada reconoce otra dentro del pensum destino, sin inventar notas.</p></div></header>
    <aside className="panel equivalence-notice">Son reglas generales para todos los estudiantes de la carrera y versión activa. No son solicitudes individuales ni convalidaciones de estudios externos.</aside>
    {loadError && <p className="form-error" role="alert">{apiMessage(loadError)}</p>}
    <details className="panel equivalence-create" open>
      <summary>Registrar una regla</summary>
      <form className="resource-form" onChange={() => setPreview(undefined)} onSubmit={e => { e.preventDefault(); if (!preview) inspect.mutate(); else create.mutate(); }}>
        <div className="equivalence-fields">
          <label className="form-field"><span>Carrera destino</span><select required disabled={busy} value={career} onChange={e => { setCareer(e.target.value); setVersion(""); setTarget(""); }}><option value="">Selecciona una carrera</option>{careers.data?.map(c => <option key={c.career_id} value={c.career_id}>{c.code} · {c.name}</option>)}</select></label>
          <label className="form-field"><span>Versión del pensum destino</span><select required disabled={busy || !context.data?.versions.length || context.isFetching} value={version} onChange={e => { setVersion(e.target.value); setTarget(""); }}><option value="">Selecciona una versión</option>{context.data?.versions.map(v => <option key={v} value={v}>{v}{v === context.data?.active_version ? " · Activa" : ""}</option>)}</select></label>
          <div><label className="form-field"><span>Buscar asignatura de origen</span><input disabled={busy} value={sourceSearch} onChange={e => setSourceSearch(e.target.value)} placeholder="Código o nombre" /></label><label className="form-field"><span>Asignatura aprobada de origen</span><select required disabled={busy} value={source} onChange={e => setSource(e.target.value)}><option value="">Selecciona</option>{subjects.data?.filter(s => s.subject_id !== Number(target) && (s.subject_id === Number(source) || `${s.code} ${s.description}`.toLowerCase().includes(sourceSearch.toLowerCase()))).map(s => <option key={s.subject_id} value={s.subject_id}>{s.code} · {s.description}</option>)}</select></label></div>
          <div><label className="form-field"><span>Buscar asignatura destino</span><input disabled={busy} value={targetSearch} onChange={e => setTargetSearch(e.target.value)} placeholder="Solo asignaturas del pensum seleccionado" /></label><label className="form-field"><span>Asignatura que se reconocerá</span><select required disabled={busy || !version || context.isFetching} value={target} onChange={e => setTarget(e.target.value)}><option value="">Selecciona</option>{context.data?.courses.filter(c => c.version === version && c.subject_id !== Number(source) && (c.subject_id === Number(target) || `${c.code} ${c.name}`.toLowerCase().includes(targetSearch.toLowerCase()))).map(c => <option key={c.subject_id} value={c.subject_id}>{c.code} · {c.name} · {c.credits} créditos</option>)}</select></label></div>
          <label className="form-field"><span>Observaciones</span><textarea disabled={busy} maxLength={2000} value={notes} onChange={e => setNotes(e.target.value)} /></label>
          <label className="form-field"><span>Motivo del registro</span><input required minLength={2} maxLength={250} disabled={busy} value={reason} onChange={e => setReason(e.target.value)} /></label>
        </div>
        <label className="equivalence-check"><input disabled={busy} type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} />Activar al registrar</label>
        {context.error && <p className="form-error">{apiMessage(context.error)}</p>}
        {career && context.data && !context.data.versions.length && <p>Esta carrera no tiene asignaturas en su pensum. Complétalo antes de registrar una regla.</p>}
        {preview && <ImpactView value={preview} />}
        <Button disabled={busy || !version || !source || !target}>{busy ? "Procesando…" : preview ? "Confirmar registro" : "Revisar impacto"}</Button>
      </form>
    </details>
    <section className="panel">
      <h2>Reglas registradas</h2>
      <div className="equivalence-filters">
        <label className="form-field"><span>Buscar reglas</span><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Materias, carrera u observaciones" /></label>
        <label className="form-field"><span>Filtrar carrera</span><select value={filterCareer} onChange={e => setFilterCareer(e.target.value)}><option value="">Todas</option>{careers.data?.map(c => <option key={c.career_id} value={c.career_id}>{c.name}</option>)}</select></label>
        <label className="form-field"><span>Estado</span><select value={filterState} onChange={e => setFilterState(e.target.value)}><option value="">Todos</option><option value="true">Activas</option><option value="false">Inactivas</option></select></label>
        <label className="form-field"><span>Versión</span><select value={filterVersion} onChange={e => setFilterVersion(e.target.value)}><option value="">Todas</option>{[...new Set(rules.data?.map(r => r.curriculum_version))].sort().map(v => <option key={v}>{v}</option>)}</select></label>
      </div>
      <p>{visible.length} reglas · El sentido es origen → destino, no recíproco.</p>
      <div className="equivalence-rules">{visible.map(r => <article key={r.course_equivalence_id}>
        <header><span>{r.career_code} · {r.career_name} · Plan {r.curriculum_version}</span><Badge tone={r.active ? "success" : "neutral"}>{r.active ? "Activa" : "Inactiva"}</Badge></header>
        <div className="equivalence-route"><div><small>Al aprobar</small><strong>{r.source_code}</strong><span>{r.source_name}</span></div><ArrowRightLeft aria-hidden="true" /><div><small>Se reconoce</small><strong>{r.target_code}</strong><span>{r.target_name}</span></div></div>
        <p>{r.notes || "Sin observaciones registradas."}</p>
        <footer><Button variant="secondary" onClick={() => { setEditing(r); setEditNotes(r.notes); setEditReason(""); setEditActive(r.active); setEditImpact(undefined); }}>Gestionar regla</Button><Button variant="ghost" onClick={() => setHistoryId(r.course_equivalence_id)}>Historial</Button></footer>
      </article>)}</div>
      {!visible.length && <EmptyState icon={<ArrowRightLeft />} title="Sin reglas para estos filtros" description="Ajusta los filtros o registra una nueva regla." />}
    </section>
    {editing && <Modal title={`${editing.source_code} → ${editing.target_code}`} description={`${editing.career_name} · Plan ${editing.curriculum_version}. Las asignaturas y la versión no se cambian: registra otra regla si necesitas una relación diferente.`} onClose={() => { if (!update.isPending && !inspectEdit.isPending) setEditing(undefined); }}>
      <form className="resource-form" onSubmit={e => { e.preventDefault(); update.mutate(); }}>
        <label className="form-field"><span>Observaciones</span><textarea disabled={update.isPending} maxLength={2000} value={editNotes} onChange={e => setEditNotes(e.target.value)} /></label>
        <label className="form-field"><span>Motivo del cambio</span><input disabled={update.isPending} required minLength={2} maxLength={250} value={editReason} onChange={e => setEditReason(e.target.value)} /></label>
        <label className="equivalence-check"><input type="checkbox" disabled={update.isPending || inspectEdit.isPending} checked={editActive} onChange={e => { setEditActive(e.target.checked); setEditImpact(undefined); }} />Regla activa</label>
        {editing.active !== editActive && <><Button type="button" variant="secondary" disabled={inspectEdit.isPending} onClick={() => inspectEdit.mutate()}>Revisar impacto del cambio</Button>{editImpact && <ImpactView value={editImpact} />}</>}
        <Button disabled={update.isPending || inspectEdit.isPending || (editing.active !== editActive && !editImpact)}>Confirmar cambios</Button>
      </form>
    </Modal>}
    {historyId && <Modal title="Historial de la regla" description="Solo muestra cambios registrados desde la incorporación de la auditoría." onClose={() => setHistoryId(undefined)}>
      {history.isLoading ? <Spinner /> : history.error ? <p className="form-error">{apiMessage(history.error)}</p> : history.data?.length ? <div className="equivalence-history">{history.data.map(h => <article key={h.audit_log_id}><strong>{{ "equivalence.created": "Registro", "equivalence.updated": "Actualización", "equivalence.activated": "Activación", "equivalence.deactivated": "Desactivación" }[h.action] || h.action} · {h.actor}</strong><time>{new Date(h.created_at + (h.created_at.endsWith("Z") ? "" : "Z")).toLocaleString()}</time><p>{h.detail}</p></article>)}</div> : <p>No hay cambios auditados para esta regla histórica.</p>}
    </Modal>}
  </div>;
}
