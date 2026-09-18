import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BookOpenCheck, GraduationCap } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./career-program.css";

const termLabels:Record<string,string>={bimester:"Bimestre",trimester:"Trimestre",quadrimester:"Cuatrimestre",semester:"Semestre",annual:"Año"};
const levelLabels:Record<string,string>={technical:"Técnico superior",undergraduate:"Grado",graduate:"Maestría",postgraduate:"Postgrado"};

export function CareerProgramPage(){
  const{careerId}=useParams();
  const career=useQuery({queryKey:["career",careerId],queryFn:()=>api.get(`/careers/${careerId}`).then(r=>r.data)});
  const courses=useQuery({queryKey:["career-curriculum",careerId],queryFn:()=>api.get("/curriculum/courses",{params:{career_id:careerId}}).then(r=>r.data)});
  if(career.isLoading||courses.isLoading)return <div className="page"><Spinner/></div>;
  if(career.error||courses.error||!career.data)return <div className="page"><EmptyState icon={<GraduationCap/>} title="No pudimos abrir el programa" description={apiMessage(career.error??courses.error)}/></div>;
  const items:any[]=courses.data??[];
  const totalCredits=items.reduce((sum,item)=>sum+Number(item.credits),0);
  const termNumbers=[...new Set(items.map(item=>Number(item.term_number)))].sort((a,b)=>a-b);
  const term=termLabels[career.data.term_type]??"Período";
  return <div className="page"><Link className="back-link" to="/careers"><ArrowLeft/> Carreras</Link><header className="program-hero"><div><span className="kicker">{career.data.code} · {levelLabels[career.data.academic_level]??career.data.academic_level}</span><h1>{career.data.name}</h1><p>{career.data.degree_title}</p><small>{career.data.description}</small></div><div className="program-metrics"><span><b>{totalCredits}</b> créditos</span><span><b>{career.data.duration_terms}</b> períodos</span><span><b>{items.length}</b> asignaturas</span></div></header><section className="curriculum-terms">{termNumbers.length?termNumbers.map(number=>{const periodItems=items.filter(item=>Number(item.term_number)===number);return <article className="panel" key={number}><div className="panel-heading"><div><span className="kicker">Plan de estudios</span><h2>{term} {number}</h2></div><strong>{periodItems.reduce((sum,item)=>sum+Number(item.credits),0)} créditos</strong></div><div className="program-courses">{periodItems.map(item=><div key={item.curriculum_course_id}><BookOpenCheck/><span><strong>{item.subject_code} · {item.subject_name}</strong><small>{item.prerequisite_code?`Prerrequisito: ${item.prerequisite_code}`:"Sin prerrequisito"}</small></span><b>{item.credits} cr.</b></div>)}</div></article>}):<EmptyState icon={<BookOpenCheck/>} title="El pensum aún está vacío" description="Agrega asignaturas, créditos y prerrequisitos desde Pensum académico."/>}</section></div>;
}
