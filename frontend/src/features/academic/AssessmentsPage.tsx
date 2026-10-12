import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookCheck, History, Lock, Plus, Save, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./assessments.css";

type Section = { section_id: number; code: string; subject_id: number; subject_name: string; teacher_name: string; period_name: string };
type Assessment = { assessment_id: number; name: string; weight: number; due_date: string | null; closed: boolean };
type Grade = { grade_id: number; assessment_id: number | null; grade_value: number; status: string };
type Student = { enrollment_id: number; first_name: string; last_name: string; enrollment_number: string; grades: Grade[] };
type Workspace = { roster: Student[]; subject_id: number; period_name: string };
type Final = { enrollment_id: number; weighted_grade: number; completed_weight: number; final: boolean; status: string; calculation_mode: string };
type Template = { assessment_template_id: number; name: string; weight: number };
type Plan = Template & { components: { name: string; weight: number }[] };
type Change = { grade_change_id: number; action: string; previous_value: number | null; new_value: number; previous_status: string | null; new_status: string | null; reason: string; changed_by_name: string; changed_at: string };
const labels: Record<string, string> = { draft: "Borrador", published: "Publicada", voided: "Anulada", created: "Registro", updated: "Corrección", in_progress: "Provisional", passed: "Aprobada", failed: "Reprobada" };
const cellKey = (enrollmentId: number, assessmentId: number) => enrollmentId + ":" + assessmentId;

export function AssessmentsPage() {
  const user = useAuthStore(state => state.user);
  const [params] = useSearchParams();
  const [selected, setSelected] = useState(() => Number(params.get("section")) || 0);
  const sections = useQuery<Section[]>({
    queryKey: ["assessment-sections", user?.user_id],
    queryFn: async () => {
      const items: Section[] = [];
      for (let skip = 0; ; skip += 100) {
        const response = await api.get<Section[]>("/sections/", { params: { skip, limit: 100 } });
        items.push(...response.data);
        if (response.data.length < 100) return items;
      }
    },
  });
  const section = sections.data?.find(item => item.section_id === selected) ?? sections.data?.[0];
  if (sections.isLoading) return <div className="page"><Spinner /></div>;
  if (sections.error) return <div className="page"><EmptyState icon={<BookCheck />} title="No pudimos cargar las secciones" description={apiMessage(sections.error)} /></div>;
  if (!section) return <div className="page"><EmptyState icon={<BookCheck />} title="No hay secciones disponibles" description="Asigna un docente a una sección para preparar su plan de evaluación." /></div>;
  return <div className="page assessments-page">
    <header className="page-header"><div><span className="kicker">Evaluación académica</span><h1>Plan y libro de notas</h1><p>Configura la distribución, prepara notas y publica resultados de cada sección.</p></div>
      <label className="form-field"><span>Sección y asignatura</span><select value={section.section_id} onChange={event => {
        if (document.querySelector('[data-unsaved-grades="true"]') && !confirm("Hay cambios sin guardar. ¿Cambiar de sección y descartarlos?")) return;
        setSelected(Number(event.target.value));
      }}>{sections.data?.map(item => <option key={item.section_id} value={item.section_id}>{item.code} · {item.subject_name} · {item.period_name || "Sin período"}</option>)}</select></label>
    </header>
    <SectionBook key={section.section_id + ":" + user?.user_id} section={section} />
  </div>;
}

function SectionBook({ section }: { section: Section }) {
  const user = useAuthStore(state => state.user);
  const client = useQueryClient();
  const [tab, setTab] = useState("book");
  const [values, setValues] = useState<Record<string, string>>({});
  const [weights, setWeights] = useState<Record<number, string>>({});
  const [reason, setReason] = useState("");
  const [history, setHistory] = useState<{ grade: Grade; student: string; closed: boolean } | null>(null);
  const [name, setName] = useState("");
  const [weight, setWeight] = useState("");
  const [date, setDate] = useState("");
  const [planName, setPlanName] = useState("");
  const assessments = useQuery<Assessment[]>({ queryKey: ["assessments", section.section_id, user?.user_id], queryFn: () => api.get("/assessments/sections/" + section.section_id).then(r => r.data) });
  const workspace = useQuery<Workspace>({ queryKey: ["assessment-roster", section.section_id, user?.user_id], queryFn: () => api.get("/academic/sections/" + section.section_id + "/workspace").then(r => r.data) });
  const finals = useQuery<Final[]>({ queryKey: ["assessment-finals", section.section_id, user?.user_id], queryFn: () => api.get("/assessments/sections/" + section.section_id + "/finals").then(r => r.data) });
  const plans = useQuery<Plan[]>({ queryKey: ["assessment-plans", section.subject_id, user?.user_id], queryFn: () => api.get("/assessments/plans/templates", { params: { subject_id: section.subject_id } }).then(r => r.data) });
  const templates = useQuery<Template[]>({ queryKey: ["assessment-templates", user?.user_id], queryFn: () => api.get("/assessments/templates").then(r => r.data) });
  const audit = useQuery<{ action: string; detail: string; created_at: string; user_id: number; actor: string }[]>({ queryKey: ["assessment-audit", section.section_id, user?.user_id], queryFn: () => api.get("/assessments/sections/" + section.section_id + "/audit").then(r => r.data), enabled: tab === "audit" });
  const refresh = () => {
    for (const key of ["assessments", "assessment-roster", "assessment-finals", "assessment-audit", "section-results", "section-academic-summary", "student-profile", "my-grades", "my-progress", "dashboard", "transcript"])
      client.invalidateQueries({ queryKey: [key] });
  };
  const items = assessments.data ?? [];
  const roster = workspace.data?.roster ?? [];
  const dirty = Object.keys(values).length > 0;
  const getGrade = (student: Student, item: Assessment) => student.grades.find(grade => grade.assessment_id === item.assessment_id);
  const create = useMutation({
    mutationFn: () => api.post("/assessments/", { section_id: section.section_id, name, weight: Number(weight), due_date: date || null }),
    onSuccess: () => { setName(""); setWeight(""); setDate(""); refresh(); toast.success("Evaluación creada"); },
    onError: error => toast.error(apiMessage(error)),
  });
  const distribute = useMutation({
    mutationFn: () => api.patch("/assessments/sections/" + section.section_id + "/distribution", {
      reason, components: items.map(item => ({ assessment_id: item.assessment_id, weight: Number(weights[item.assessment_id] ?? item.weight) })),
    }),
    onSuccess: () => { setWeights({}); refresh(); toast.success("Distribución guardada en una sola operación"); },
    onError: error => toast.error(apiMessage(error)),
  });
  const save = useMutation({
    mutationFn: async (item: Assessment) => {
      const records = roster.filter(student => cellKey(student.enrollment_id, item.assessment_id) in values).map(student => {
        const value = values[cellKey(student.enrollment_id, item.assessment_id)];
        if (!value.trim() || !Number.isFinite(Number(value)) || Number(value) < 0 || Number(value) > 100)
          throw new Error("Las notas deben estar entre 0 y 100. Para retirar una nota guardada, anúlala desde su historial.");
        return { enrollment_id: student.enrollment_id, grade_value: Number(value) };
      });
      return api.post("/grades/bulk", { section_id: section.section_id, assessment_id: item.assessment_id, grade_type: item.name, date_recorded: new Date().toISOString().slice(0, 10), reason, status: "draft", records });
    },
    onSuccess: (_, item) => {
      setValues(current => Object.fromEntries(Object.entries(current).filter(([key]) => !key.endsWith(":" + item.assessment_id))));
      refresh(); toast.success("Cambios guardados como borrador");
    },
    onError: error => toast.error(error instanceof Error && !("response" in error) ? error.message : apiMessage(error)),
  });
  const publish = useMutation({
    mutationFn: (item: Assessment) => api.post("/grades/assessments/" + item.assessment_id + "/publish"),
    onSuccess: response => { refresh(); toast.success(response.data.published + " notas publicadas"); },
    onError: error => toast.error(apiMessage(error)),
  });
  const close = useMutation({
    mutationFn: (item: Assessment) => api.post("/assessments/" + item.assessment_id + "/close"),
    onSuccess: () => { refresh(); toast.success("Evaluación cerrada"); },
    onError: error => toast.error(apiMessage(error)),
  });
  const reopen = useMutation({
    mutationFn: (item: Assessment) => api.post("/assessments/" + item.assessment_id + "/reopen", { reason }),
    onSuccess: () => { refresh(); toast.success("Reapertura registrada"); },
    onError: error => toast.error(apiMessage(error)),
  });
  const savePlan = useMutation({
    mutationFn: () => api.post("/assessments/plans/templates", { name: planName, subject_id: section.subject_id, components: items.map(item => ({ name: item.name, weight: item.weight })) }),
    onSuccess: () => { client.invalidateQueries({ queryKey: ["assessment-plans"] }); toast.success("Esquema completo guardado para esta asignatura"); },
    onError: error => toast.error(apiMessage(error)),
  });
  const applyPlan = useMutation({
    mutationFn: (id: number) => api.post("/assessments/plans/templates/" + id + "/apply", { section_id: section.section_id }),
    onSuccess: () => { refresh(); toast.success("Plan copiado a la sección; sus notas son independientes"); },
    onError: error => toast.error(apiMessage(error)),
  });
  const applyComponent = useMutation({
    mutationFn: (id: number) => api.post("/assessments/templates/" + id + "/apply", { section_id: section.section_id, due_date: date || null }),
    onSuccess: refresh, onError: error => toast.error(apiMessage(error)),
  });
  const saveComponent = useMutation({
    mutationFn: () => api.post("/assessments/templates", { name, weight: Number(weight) }),
    onSuccess: () => { client.invalidateQueries({ queryKey: ["assessment-templates"] }); toast.success("Componente guardado"); },
    onError: error => toast.error(apiMessage(error)),
  });
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => { if (dirty || Object.keys(weights).length) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty, weights]);
  if (assessments.isLoading || workspace.isLoading) return <Spinner />;
  if (assessments.error || workspace.error) return <EmptyState icon={<BookCheck />} title="No pudimos abrir el libro de notas" description={apiMessage(assessments.error || workspace.error)} />;
  const configured = items.reduce((sum, item) => sum + item.weight, 0);
  const proposed = items.reduce((sum, item) => sum + Number(weights[item.assessment_id] ?? item.weight), 0);
  const hasReason = reason.trim().length >= 2;
  return <div data-unsaved-grades={dirty || Object.keys(weights).length > 0}>
    <div className="assessment-context"><strong>{section.subject_name}</strong><span>{section.teacher_name} · {section.period_name || workspace.data?.period_name || "Período por asignar"}</span></div>
    <section className="profile-metrics"><article><small>Distribución</small><strong>{configured.toFixed(2)}%</strong></article><article><small>Por configurar</small><strong>{Math.max(0, 100 - configured).toFixed(2)}%</strong></article><article><small>Estudiantes activos</small><strong>{roster.length}</strong></article></section>
    <nav className="assessment-tabs" aria-label="Gestión de evaluaciones">{[["book", "Libro de notas"], ["plan", "Distribución y plantillas"], ["audit", "Historial del plan"]].map(([key, label]) => <button key={key} aria-pressed={tab === key} onClick={() => setTab(key)}>{label}</button>)}</nav>
    <label className="form-field assessment-reason"><span>Motivo del registro, corrección o reapertura</span><input value={reason} onChange={event => setReason(event.target.value)} placeholder="Ej. Revisión del examen y corrección del puntaje" maxLength={250} /></label>
    {tab === "book" && <>
      <p className="muted">Vacío significa pendiente; 0 es una nota válida. Los borradores no afectan resultados oficiales. Guarda cada componente antes de publicarlo.</p>
      {!items.length ? <EmptyState icon={<BookCheck />} title="Prepara el plan de evaluación" description="Crea componentes o aplica un esquema de la asignatura en Distribución y plantillas." action={<Button onClick={() => setTab("plan")}>Configurar plan</Button>} /> : <>
        <div className="assessment-book-scroll"><table className="assessment-book"><thead><tr><th>Estudiante</th>{items.map(item => <th key={item.assessment_id}>{item.name}<small>{item.weight}% · {item.closed ? "Cerrada" : "Abierta"}</small></th>)}<th>Resultado publicado<small>Ponderado sobre 100</small></th></tr></thead>
          <tbody>{roster.map(student => { const result = finals.data?.find(item => item.enrollment_id === student.enrollment_id); return <tr key={student.enrollment_id}>
            <th scope="row">{student.first_name} {student.last_name}<small>{student.enrollment_number}</small></th>
            {items.map(item => { const grade = getGrade(student, item); const key = cellKey(student.enrollment_id, item.assessment_id); const state = key in values ? "dirty" : grade?.status ?? "pending"; return <td key={item.assessment_id}>
              <div className="assessment-grade-input"><input aria-label={item.name + " de " + student.first_name + " " + student.last_name} disabled={item.closed || save.isPending || publish.isPending} type="number" min="0" max="100" step=".01" placeholder="—" value={values[key] ?? (grade && grade.status !== "voided" ? String(grade.grade_value) : "")} onChange={event => {
                const value = event.target.value; const original = grade && grade.status !== "voided" ? String(grade.grade_value) : "";
                setValues(current => { const next = { ...current }; if (value === original) delete next[key]; else next[key] = value; return next; });
              }} />{grade && <button className="icon-button" title="Historial y anulación" aria-label={"Historial de " + item.name + " de " + student.first_name} onClick={() => setHistory({ grade, student: student.first_name + " " + student.last_name, closed: item.closed })}><History size={16} /></button>}</div>
              <Badge tone={state === "published" ? "success" : state === "dirty" || state === "draft" ? "warning" : "neutral"}>{state === "dirty" ? "Sin guardar" : labels[state] ?? "Pendiente"}</Badge>
              {grade?.status === "published" && <small>Aporta {(grade.grade_value * item.weight / 100).toFixed(2)} puntos</small>}
            </td>; })}
            <td><strong>{result?.completed_weight ? result.weighted_grade.toFixed(2) : "—"}</strong><small>{result?.final ? labels[result.status] : "Provisional"} · {result?.completed_weight ?? 0}% calificado</small></td>
          </tr>; })}</tbody></table></div>
        {!roster.length && <p className="muted">No hay estudiantes inscritos activos en esta sección.</p>}
        <div className="assessment-actions">{items.map(item => {
          const changed = Object.keys(values).some(key => key.endsWith(":" + item.assessment_id));
          const published = roster.filter(student => getGrade(student, item)?.status === "published").length;
          const drafts = roster.filter(student => getGrade(student, item)?.status === "draft").length;
          return <article className="panel" key={item.assessment_id}><h3>{item.name} · {item.weight}%</h3><p>{published}/{roster.length} publicadas · {drafts} borradores · {roster.length - published - drafts} pendientes</p><div className="form-actions">
            <Button disabled={item.closed || !changed || !hasReason || save.isPending} onClick={() => save.mutate(item)}><Save size={16} /> Guardar borrador</Button>
            <Button variant="secondary" disabled={item.closed || dirty || !drafts || publish.isPending || save.isPending} onClick={() => confirm("¿Publicar las notas guardadas de " + item.name + "?") && publish.mutate(item)}><Send size={16} /> Publicar</Button>
            {!item.closed ? <Button variant="secondary" disabled={dirty || save.isPending || publish.isPending || published < roster.length || close.isPending} onClick={() => confirm("¿Cerrar " + item.name + "? Sus notas quedarán bloqueadas.") && close.mutate(item)}><Lock size={16} /> Cerrar</Button> : user?.role_name === "admin" ? <Button variant="secondary" disabled={!hasReason || reopen.isPending} onClick={() => reopen.mutate(item)}>Reabrir con motivo</Button> : <Badge>Cerrada</Badge>}
          </div></article>;
        })}</div>
      </>}
      {finals.error && <p role="alert">{apiMessage(finals.error)}</p>}
    </>}
    {tab === "plan" && <>
      <section className="panel assessment-plan"><h2>Distribución completa</h2><p>Cambia todos los porcentajes y guarda una vez. El total debe ser 100%; las evaluaciones cerradas requieren reapertura.</p>
        {items.map(item => <div className="assessment-weight-row" key={item.assessment_id}><span>{item.name}{item.closed && " · Cerrada"}</span><label><span className="sr-only">Porcentaje de {item.name}</span><input disabled={item.closed} aria-label={"Porcentaje de " + item.name} type="number" min=".01" max="100" step=".01" value={weights[item.assessment_id] ?? item.weight} onChange={event => setWeights(current => ({ ...current, [item.assessment_id]: event.target.value }))} /> %</label></div>)}
        <div className="form-actions"><strong>Total propuesto: {proposed.toFixed(2)}%</strong><Button disabled={!Object.keys(weights).length || Math.abs(proposed - 100) > .001 || !hasReason || distribute.isPending || dirty} onClick={() => distribute.mutate()}>Guardar distribución</Button></div>
      </section>
      <div className="assessment-plan-grid"><form className="panel resource-form" onSubmit={event => { event.preventDefault(); create.mutate(); }}><h2><Plus size={18} /> Nueva evaluación</h2>
        <label className="form-field"><span>Nombre</span><input required minLength={2} maxLength={100} value={name} onChange={event => setName(event.target.value)} /></label>
        <label className="form-field"><span>Peso porcentual</span><input required type="number" min=".01" max="100" step=".01" value={weight} onChange={event => setWeight(event.target.value)} /></label>
        <label className="form-field"><span>Fecha límite</span><input type="date" value={date} onChange={event => setDate(event.target.value)} /></label>
        <div className="form-actions"><Button disabled={create.isPending || configured >= 100}>Crear componente</Button><Button type="button" variant="secondary" disabled={!name || !weight || saveComponent.isPending} onClick={() => saveComponent.mutate()}>Guardar componente como plantilla</Button></div>
      </form>
      <section className="panel assessment-plan"><h2>Esquemas de esta asignatura</h2><p>Una copia por sección: editarla no cambia otras secciones. Los esquemas creados por administración se comparten con docentes.</p>
        <label className="form-field"><span>Nombre del esquema completo</span><input value={planName} onChange={event => setPlanName(event.target.value)} placeholder="Ej. Matemática · evaluación regular" maxLength={100} /></label>
        <Button disabled={planName.trim().length < 2 || !items.length || Math.abs(configured - 100) > .001 || Object.keys(weights).length > 0 || savePlan.isPending} onClick={() => savePlan.mutate()}>Guardar plan de 100%</Button>
        {plans.isLoading ? <Spinner /> : plans.error ? <p role="alert">{apiMessage(plans.error)}</p> : plans.data?.map(plan => <article className="assessment-template" key={plan.assessment_template_id}><strong>{plan.name}</strong><small>{plan.components.map(item => item.name + " " + item.weight + "%").join(" · ")}</small><Button variant="secondary" disabled={items.length > 0 || applyPlan.isPending} onClick={() => applyPlan.mutate(plan.assessment_template_id)}>Copiar a esta sección</Button></article>)}
        {!plans.isLoading && !plans.error && !plans.data?.length && <p className="muted">Todavía no hay esquemas guardados para esta asignatura.</p>}
        <details><summary>Plantillas de componentes individuales</summary>{templates.error ? <p role="alert">{apiMessage(templates.error)}</p> : templates.data?.map(item => <div className="assessment-template" key={item.assessment_template_id}><span>{item.name} · {item.weight}%</span><Button variant="secondary" disabled={configured + item.weight > 100 || applyComponent.isPending} onClick={() => applyComponent.mutate(item.assessment_template_id)}>Agregar</Button></div>)}</details>
      </section></div>
      <section className="assessment-actions">{items.map(item => <AssessmentEditor key={item.assessment_id + ":" + item.name + ":" + item.weight} item={item} refresh={refresh} />)}</section>
    </>}
    {tab === "audit" && <section className="panel assessment-plan"><h2>Historial de distribución y cierres</h2>{audit.isLoading ? <Spinner /> : audit.error ? <p role="alert">{apiMessage(audit.error)}</p> : audit.data?.length ? audit.data.map((item, index) => <article className="assessment-template" key={index}><strong>{{ "assessment.created": "Evaluación creada", "assessment.section.reopened": "Sección habilitada para corrección", "assessment.updated": "Datos de evaluación actualizados", "assessment.closed": "Evaluación cerrada", "assessment.reopened": "Evaluación reabierta", "assessment.distribution": "Distribución actualizada", "assessment.plan.applied": "Esquema aplicado" }[item.action] ?? item.action}</strong><small>{new Date(item.created_at + "Z").toLocaleString()} · {item.actor}</small><p>{item.detail}</p></article>) : <p className="muted">Sin cambios registrados todavía.</p>}</section>}
    {history && <GradeHistory grade={history.grade} student={history.student} closed={history.closed} reason={reason} onClose={() => setHistory(null)} refresh={refresh} />}
  </div>;
}

function AssessmentEditor({ item, refresh }: { item: Assessment; refresh: () => void }) {
  const [name, setName] = useState(item.name);
  const [date, setDate] = useState(item.due_date ?? "");
  const update = useMutation({ mutationFn: () => api.patch("/assessments/" + item.assessment_id, { name, due_date: date || null }), onSuccess: () => { refresh(); toast.success("Datos actualizados"); }, onError: error => toast.error(apiMessage(error)) });
  return <form className="panel assessment-plan" onSubmit={event => { event.preventDefault(); update.mutate(); }}><h3>Datos de {item.name}</h3>
    <label className="form-field"><span>Nombre</span><input required minLength={2} maxLength={100} disabled={item.closed} value={name} onChange={event => setName(event.target.value)} /></label>
    <label className="form-field"><span>Fecha límite</span><input type="date" disabled={item.closed} value={date} onChange={event => setDate(event.target.value)} /></label>
    <Button disabled={item.closed || update.isPending}>Guardar datos</Button>
  </form>;
}

function GradeHistory({ grade, student, closed, reason, onClose, refresh }: { grade: Grade; student: string; closed: boolean; reason: string; onClose: () => void; refresh: () => void }) {
  const user = useAuthStore(state => state.user);
  const history = useQuery<Change[]>({ queryKey: ["grade-history", grade.grade_id, user?.user_id], queryFn: () => api.get("/grades/" + grade.grade_id + "/history").then(r => r.data) });
  const annul = useMutation({ mutationFn: () => api.delete("/grades/" + grade.grade_id, { data: { reason } }), onSuccess: () => { refresh(); onClose(); toast.success("Nota anulada, historial conservado"); }, onError: error => toast.error(apiMessage(error)) });
  return <Modal title={"Historial de " + student} onClose={onClose}><p>Nota actual: {grade.grade_value} · {labels[grade.status]}</p>
    {history.isLoading ? <Spinner /> : history.error ? <p role="alert">{apiMessage(history.error)}</p> : history.data?.map(change => <article className="assessment-template" key={change.grade_change_id}><strong>{labels[change.action] ?? change.action} · {change.previous_value ?? "—"} → {change.new_value}</strong><small>{change.changed_by_name} · {new Date(change.changed_at + "Z").toLocaleString()}</small><p>{change.reason}</p><small>{labels[change.previous_status ?? ""] ?? "Sin nota"} → {labels[change.new_status ?? ""] ?? ""}</small></article>)}
    <p className="muted">Para anular, escribe el motivo en el libro de notas. La nota no se borra físicamente.</p>
    <Button variant="danger" disabled={closed || grade.status === "voided" || reason.trim().length < 2 || annul.isPending} onClick={() => confirm("¿Anular esta nota y conservar su historial?") && annul.mutate()}>Anular nota</Button>
  </Modal>;
}
