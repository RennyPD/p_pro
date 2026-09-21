import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, CalendarDays, CreditCard, MapPin, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Badge, Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./schedule.css";
import "./catalog.css";

export function CourseCatalogPage(){
  const client=useQueryClient();
  const query=useQuery({queryKey:["course-catalog"],queryFn:()=>api.get("/academic/catalog").then(r=>r.data)});
  const summary=useQuery({queryKey:["course-catalog-summary"],queryFn:()=>api.get("/academic/catalog/summary").then(r=>r.data)});
  const refresh=()=>{client.invalidateQueries({queryKey:["course-catalog"]});client.invalidateQueries({queryKey:["course-catalog-summary"]});client.invalidateQueries({queryKey:["my-schedule"]})};
  const select=useMutation({mutationFn:(id:number)=>api.post(`/academic/catalog/sections/${id}/select`),onSuccess:()=>{toast.success("Asignatura seleccionada");refresh()},onError:e=>toast.error(apiMessage(e))});
  const withdraw=useMutation({mutationFn:(id:number)=>api.post(`/academic/catalog/sections/${id}/withdraw`),onSuccess:()=>{toast.success("Asignatura retirada");refresh()},onError:e=>toast.error(apiMessage(e))});
  if(query.isLoading||summary.isLoading)return <div className="page"><Spinner/></div>;
  if(query.error||summary.error)return <div className="page"><EmptyState icon={<BookOpen/>} title="No pudimos abrir el catálogo" description={apiMessage(query.error??summary.error)}/></div>;
  const info=summary.data;
  return <div className="page"><header className="page-header"><div><span className="kicker">Oferta del período {info?.period??"sin período activo"}</span><h1>Elegir asignaturas</h1><p>Selecciona secciones de tu pensum. Nexo verifica cupos, créditos, prerrequisitos y choques de horario.</p></div></header><section className="profile-metrics"><article><small>Créditos seleccionados</small><strong>{info?.selected_credits??0} / {info?.maximum_credits??0}</strong></article><article><small>Secciones confirmadas</small><strong>{info?.enrolled_sections??0}</strong></article><article><small>En lista de espera</small><strong>{info?.waitlisted_sections??0}</strong></article></section><section className="catalog-grid">{query.data?.map((item:any)=><article className="panel" key={item.section_id}><div className="panel-heading"><div><span className="kicker">{item.subject_code} · {item.credits} créditos</span><h2>{item.subject_name}</h2><small>Sección {item.section_code}</small></div><Badge tone={item.available_seats?"success":"warning"}>{item.available_seats} cupos</Badge></div><p><UserRound size={16}/>{item.teacher_name}</p><p><CalendarDays size={16}/>{item.days_of_week.join(" · ")} · {item.start_time.slice(0,5)}–{item.end_time.slice(0,5)}</p><p><MapPin size={16}/>{item.room} · {labelModality(item.modality)}</p><p><CreditCard size={16}/>{item.prerequisite_code?`Requiere ${item.prerequisite_code}`:"Sin prerrequisito"}{item.corequisite_code?` · Correquisito ${item.corequisite_code}`:""}</p>{item.selection_status?<div className="catalog-actions"><Badge tone="info">{labelState(item.selection_status)}</Badge>{["enrolled","waitlisted"].includes(item.selection_status)&&<Button variant="secondary" disabled={withdraw.isPending} onClick={()=>confirm("¿Retirar esta asignatura?")&&withdraw.mutate(item.section_id)}>Retirar</Button>}</div>:<Button disabled={!item.available_seats||!item.selectable||select.isPending} title={item.restriction_reason??""} onClick={()=>confirm(`¿Seleccionar ${item.subject_name}, sección ${item.section_code}?`)&&select.mutate(item.section_id)}>Seleccionar sección</Button>}</article>)}</section></div>;
}
function labelModality(v:string){return v==="virtual"?"Virtual":v==="hybrid"?"Híbrida":"Presencial"}
function labelState(v:string){return v==="waitlisted"?"En lista de espera":v==="enrolled"?"Seleccionada":v==="withdrawn"?"Retirada":v}
