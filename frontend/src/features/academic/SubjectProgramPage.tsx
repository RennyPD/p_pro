import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Badge, Button, EmptyState, Spinner } from "../../components/ui";
import { resources } from "../../config/resources";
import { api, apiMessage } from "../../lib/api";
import type { EntityRecord, ResourceConfig } from "../../types";
import { ResourceForm } from "../resources/ResourcePage";
import { termLabels } from "./career-config";
import "./students.css";
import "./career-program.css";
import "./subject-program.css";

type Program = EntityRecord & {
  curriculum_course_id: number; career_id: number; career_name: string; career_code: string;
  term_type: string; term_number: number; credits: number; course_type: string;
  curriculum_version: string; is_current_version: boolean;
  prerequisite_code: string | null; corequisite_code: string | null;
};
type Section = {
  section_id: number; code: string; teacher_name: string; period_name: string;
  room: string; capacity: number; status: string;
};
type Overview = { subject: EntityRecord; programs: Program[]; sections: Section[] };
const courseTypes: Record<string, string> = {
  required: "Obligatoria", elective: "Electiva", internship: "Pasantía", capstone: "Trabajo de grado",
};
const sectionStates: Record<string, string> = {
  draft: "Borrador", published: "Publicada", active: "Activa", closed: "Cerrada", cancelled: "Cancelada",
};

export function SubjectProgramPage() {
  const { subjectId } = useParams();
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [courseEditing, setCourseEditing] = useState<Program | null | undefined>();
  const [tab, setTab] = useState("programs");
  const query = useQuery<Overview>({
    queryKey: ["subject-overview", subjectId],
    queryFn: () => api.get(`/subjects/${subjectId}/overview`).then(response => response.data),
  });
  if (query.isLoading) return <div className="page"><Spinner /></div>;
  if (!query.data || query.error) return <div className="page"><EmptyState icon={<BookOpen />} title="No pudimos abrir la asignatura" description={apiMessage(query.error)} /></div>;
  const { subject, programs, sections } = query.data;
  const courseConfig: ResourceConfig = {
    ...resources.curriculum,
    singular: courseEditing ? "asignatura del pensum" : "vínculo con una carrera",
    fields: resources.curriculum.fields
      .filter(field => !courseEditing || !["subject_id", "career_id"].includes(field.name))
      .map(field => field.name === "subject_id" ? { ...field, type: "hidden" } : field),
  };
  const refresh = () => {
    client.invalidateQueries({ queryKey: ["subject-overview", subjectId] });
    client.invalidateQueries({ queryKey: ["career-curriculum"] });
    client.invalidateQueries({ queryKey: ["career-overview"] });
  };
  return <div className="page student-dossier">
    <Link className="back-link" to="/subjects"><ArrowLeft /> Catálogo de asignaturas</Link>
    <header className="dossier-hero career-hero">
      <div className="dossier-identity"><span className="career-emblem"><BookOpen size={34} /></span><div>
        <span className="kicker">Asignatura institucional · {subject.code}</span>
        <h1>{subject.description}</h1><p>Una asignatura compartida, diferentes planes y grupos de docencia.</p>
      </div></div>
      <Button variant="secondary" onClick={() => setEditing(true)}><Pencil size={17} /> Editar asignatura</Button>
    </header>
    <section className="panel dossier-panel subject-guide">
      <div><h2>Asignatura</h2><p>Identidad común: código y nombre. No necesita una sección para existir.</p></div>
      <div><h2>Plan de estudios</h2><p>Define en qué carrera se cursa, sus créditos, período recomendado y requisitos.</p></div>
      <div><h2>Sección</h2><p>Es el grupo que la imparte: docente, período académico, cupos y horario.</p></div>
    </section>
    <nav className="dossier-tabs" aria-label="Gestión de asignatura">
      <button className={tab === "programs" ? "is-active" : ""} aria-pressed={tab === "programs"} onClick={() => setTab("programs")}>Carreras y pensum ({programs.length})</button>
      <button className={tab === "sections" ? "is-active" : ""} aria-pressed={tab === "sections"} onClick={() => setTab("sections")}>Secciones ({sections.length})</button>
    </nav>
    {tab === "programs" ? <>
      <div className="career-section-toolbar"><div><h2>Presencia en los planes de estudio</h2><p>La asignatura puede compartirse entre carreras sin duplicarla. Al vincularla, registra la versión vigente de esa carrera.</p></div>
        <Button onClick={() => setCourseEditing(null)}><Plus size={17} /> Incorporar a una carrera</Button>
      </div>
      {programs.length ? <div className="subject-cards">{programs.map(program => <article className="panel dossier-panel" key={program.curriculum_course_id}>
        <div className="subject-card-heading"><div><span className="kicker">{program.career_code}</span><h2><Link to={`/careers/${program.career_id}`}>{program.career_name}</Link></h2></div>
          <Badge tone={program.is_current_version ? "success" : "warning"}>{program.is_current_version ? "Plan vigente" : "Plan no vigente"}</Badge></div>
        <dl className="dossier-details">
          <div><dt>Ubicación recomendada</dt><dd>{termLabels[program.term_type] ?? "Período"} {program.term_number}</dd></div>
          <div><dt>Créditos / tipo</dt><dd>{program.credits} cr. · {courseTypes[program.course_type]}</dd></div>
          <div><dt>Prerrequisito</dt><dd>{program.prerequisite_code ?? "Sin prerrequisito"}</dd></div>
          <div><dt>Correquisito</dt><dd>{program.corequisite_code ?? "Sin correquisito"}</dd></div>
          <div><dt>Versión del pensum</dt><dd>{program.curriculum_version}</dd></div>
        </dl>
        <Button variant="secondary" onClick={() => setCourseEditing(program)}><Pencil size={16} /> Editar en este pensum</Button>
      </article>)}</div> : <EmptyState icon={<BookOpen />} title="Aún no pertenece a una carrera" description="Incorpórala al pensum para que forme parte del plan académico de sus estudiantes." />}
    </> : <>
      <div className="career-section-toolbar"><div><h2>Grupos de docencia</h2><p>Estas secciones imparten la misma asignatura; no crean nuevas materias.</p></div><Link className="back-link" to="/sections">Administrar secciones</Link></div>
      {sections.length ? <div className="subject-cards">{sections.map(section => <article className="panel dossier-panel" key={section.section_id}>
        <div className="subject-card-heading"><h2>{section.code}</h2><Badge>{sectionStates[section.status] ?? section.status}</Badge></div>
        <p>{section.teacher_name}</p><p>{section.period_name || "Período por asignar"} · {section.room} · {section.capacity} cupos</p>
        <Link className="back-link" to={`/sections/${section.section_id}`}>Abrir sección →</Link>
      </article>)}</div> : <EmptyState icon={<BookOpen />} title="Todavía no tiene secciones" description="La asignatura ya puede formar parte de un pensum. Crea sus secciones cuando planifiques la oferta académica." />}
    </>}
    {editing && <ResourceForm config={resources.subjects} record={subject} onClose={() => { setEditing(false); refresh(); }} />}
    {courseEditing !== undefined && <ResourceForm config={courseConfig} record={courseEditing} initialValues={{ subject_id: Number(subjectId), term_number: 1, credits: 3, course_type: "required", curriculum_version: "" }} onClose={() => { setCourseEditing(undefined); refresh(); }} />}
  </div>;
}
