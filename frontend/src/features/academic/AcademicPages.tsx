import { useQuery } from "@tanstack/react-query";
import { CalendarDays, CheckCircle2, GraduationCap } from "lucide-react";
import { EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./academic-pages.css";
import "./curriculum-progress.css";

type QueryShape={data?:Record<string,any>[];isLoading:boolean;error:unknown};

export { StudentGradesPage as MyGradesPage } from "./StudentGradesPage";
export function MySchedulePage(){const user=useAuthStore(s=>s.user);const path=user?.role_name==="student"?`/academic/students/${user.student_id}/schedule`:`/academic/teachers/${user?.teacher_id}/schedule`;const query=useQuery({queryKey:["my-schedule",path],queryFn:()=>api.get(path).then(r=>r.data),enabled:Boolean(user)});return <AcademicList title="Mi horario" description="Una vista limpia de tus compromisos semanales." icon={<CalendarDays/>} query={query} render={(item)=><article className="schedule-card" key={item.section_id}><div className="schedule-time">{item.start_time.slice(0,5)}<span>{item.end_time.slice(0,5)}</span></div><div><strong>{item.subject_code}</strong><p>{item.section_code}</p><small>{item.days_of_week.join(" · ")}</small></div></article>}/>}


export function MyProgressPage(){const id=useAuthStore(s=>s.user?.student_id);const query=useQuery({queryKey:["my-progress",id],queryFn:()=>api.get(`/curriculum/students/${id}/progress`).then(r=>r.data),enabled:Boolean(id)});if(query.isLoading)return <div className="page"><Spinner/></div>;if(query.error||!query.data)return <div className="page"><EmptyState icon={<GraduationCap/>} title="No pudimos cargar tu progreso" description={apiMessage(query.error)}/></div>;const progress=query.data;return <div className="page"><header className="page-header"><div><span className="kicker">Trayectoria académica</span><h1>Mi progreso</h1><p>{progress.career_name}</p></div><ProgressRing value={progress.progress_percentage}/></header><section className="profile-metrics"><Metric label="Créditos completados" value={progress.completed_credits}/><Metric label="Créditos del pensum" value={progress.total_credits}/><Metric label="Avance" value={`${progress.progress_percentage}%`}/></section><section className="panel"><div className="curriculum-list">{progress.courses.map((course:any)=><article className={`curriculum-row status-${course.status}`} key={course.curriculum_course_id}><span>{course.term_number}</span><div><strong>{course.subject_code} · {course.subject_name}</strong><small>{course.credits} créditos{course.prerequisite_code?` · Requiere ${course.prerequisite_code}`:""}</small></div><b>{course.recognition_type==="equivalence"?"Reconocida por equivalencia · sin nota":course.status==="completed"?`Aprobada · ${course.final_average}`:course.status==="in_progress"?"Cursando":"Pendiente"}</b></article>)}</div></section></div>}


function Metric({label,value}:{label:string;value:string|number}){return <article><small>{label}</small><strong>{value}</strong></article>}
function ProgressRing({value}:{value:number|null}){return <div className="progress-ring" style={{"--progress":`${value??0}%`} as React.CSSProperties}><span>{value===null?"—":`${value}%`}</span></div>}
function AcademicList({title,description,icon,query,render}:{title:string;description:string;icon:React.ReactNode;query:QueryShape;render:(item:Record<string,any>)=>React.ReactNode}){return <div className="page"><header className="page-header"><div><span className="kicker">Mi espacio</span><h1>{title}</h1><p>{description}</p></div></header><section className="academic-list">{query.isLoading?<Spinner/>:query.error?<EmptyState icon={icon} title="No pudimos cargar esta información" description={apiMessage(query.error)}/>:query.data?.length?query.data.map(render):<EmptyState icon={<CheckCircle2/>} title="Todo está tranquilo por aquí" description="Cuando exista información disponible aparecerá en este espacio."/>}</section></div>}
export { AttendanceWorkspacePage as SectionWorkspacePage, StudentAttendancePage as MyAttendancePage } from "./AttendancePages";
