import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BookOpenCheck, CalendarCheck, ChevronRight, Users } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Badge, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./section-results.css";

type Mode="attendance"|"grades";
const attendanceLabels:Record<string,string>={present:"Presente",absent:"Ausente",late:"Tardanza",excused:"Justificada",early_departure:"Salida anticipada"};
const attendanceTones:Record<string,"success"|"danger"|"warning"|"info">={present:"success",absent:"danger",late:"warning",excused:"info",early_departure:"warning"};

export function SectionResultsPage({mode}:{mode:Mode}){
  const query=useQuery({queryKey:["section-academic-summary"],queryFn:()=>api.get("/academic/sections/academic-summary").then(r=>r.data)});
  const attendance=mode==="attendance";
  if(query.isLoading)return <div className="page"><Spinner/></div>;
  if(query.error)return <div className="page"><EmptyState icon={attendance?<CalendarCheck/>:<BookOpenCheck/>} title="No pudimos cargar las secciones" description={apiMessage(query.error)}/></div>;
  return <div className="page"><header className="page-header"><div><span className="kicker">Seguimiento por sección</span><h1>{attendance?"Asistencia":"Calificaciones y evaluaciones"}</h1><p>{attendance?"Compara el promedio de asistencia y entra al detalle de cada grupo.":"Revisa el promedio, las evaluaciones registradas y el resultado de cada estudiante."}</p></div></header><section className="section-summary-grid">{query.data?.map((section:any)=><Link className="section-summary-card" to={`/section-results/${section.section_id}/${mode}`} key={section.section_id}><div className="section-card-title"><span>{section.subject_code} · {section.section_code}</span><ChevronRight/></div><h2>{section.subject_name}</h2><p>{section.teacher_name}</p><div className="section-card-metrics"><span><Users/> <b>{section.student_count}</b><small>estudiantes</small></span>{attendance?<span><CalendarCheck/><b>{section.attendance_percentage===null?"—":`${section.attendance_percentage}%`}</b><small>asistencia media</small></span>:<><span><BookOpenCheck/><b>{section.grade_average??"—"}</b><small>promedio general</small></span><span><b>{section.assessment_count}</b><small>evaluaciones</small></span></>}</div></Link>)}</section></div>;
}

export function SectionResultsDetailPage(){
  const{sectionId,mode="attendance"}=useParams();
  const query=useQuery({queryKey:["section-results",sectionId],queryFn:()=>api.get(`/academic/sections/${sectionId}/workspace`).then(r=>r.data)});
  const attendance=mode==="attendance";
  if(query.isLoading)return <div className="page"><Spinner/></div>;
  if(query.error||!query.data)return <div className="page"><EmptyState icon={<Users/>} title="No pudimos abrir la sección" description={apiMessage(query.error)}/></div>;
  const section=query.data;
  return <div className="page"><Link className="back-link" to={attendance?"/attendances":"/grades"}><ArrowLeft/> {attendance?"Asistencia":"Calificaciones"}</Link><header className="workspace-hero"><div><span className="kicker">{section.subject_code} · {section.section_code}</span><h1>{section.subject_name}</h1><p>{section.teacher_name}</p></div><span className="roster-count"><Users/> {section.roster.length} estudiantes</span></header><div className="result-tabs"><Link className={attendance?"active":""} to={`/section-results/${sectionId}/attendance`}>Asistencia</Link><Link className={!attendance?"active":""} to={`/section-results/${sectionId}/grades`}>Calificaciones</Link><Link to={`/sections/${sectionId}`}>Registrar datos</Link></div><section className="student-result-list">{section.roster.map((student:any)=><details className="student-result-card" key={student.enrollment_id}><summary><div><strong>{student.first_name} {student.last_name}</strong><small>{student.enrollment_number}</small></div><div className="student-summary-value"><b>{attendance?(student.attendance_percentage===null?"Sin registros":`${student.attendance_percentage}%`):(student.average_grade??"Sin notas")}</b><small>{attendance?"promedio de asistencia":"promedio académico"}</small></div><ChevronRight/></summary>{attendance?<div className="result-history">{student.attendances.length?student.attendances.map((record:any)=><div key={record.attendance_id}><time>{new Date(`${record.date}T12:00:00`).toLocaleDateString()}</time><Badge tone={attendanceTones[record.status]??"neutral"}>{attendanceLabels[record.status]??record.status}</Badge><span>{record.note||"Sin observación"}</span></div>):<p className="muted">Todavía no hay asistencias registradas para este estudiante.</p>}</div>:<div className="result-history">{student.grades.length?student.grades.map((grade:any)=><div key={grade.grade_id}><time>{new Date(`${grade.date_recorded}T12:00:00`).toLocaleDateString()}</time><strong>{grade.grade_type}</strong><span className="grade-value">{grade.grade_value}</span></div>):<p className="muted">Todavía no hay calificaciones registradas para este estudiante.</p>}</div>}</details>)}</section></div>;
}
