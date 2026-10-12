import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { GraduationCap } from "lucide-react";
import { api } from "../../lib/api";
import { ResourcePage } from "../resources/ResourcePage";
import { careerConfig, levelLabels, modalityLabels, statusLabels } from "./career-config";
import "./students.css";
import "./career-program.css";

export function CareersPage(){
  const [filters,setFilters]=useState<Record<string,string>>({});
  const options=useQuery<{faculties:string[]}>({queryKey:["career-catalog-options"],queryFn:()=>api.get("/careers/catalog-options").then(r=>r.data)});
  const params=Object.fromEntries(Object.entries(filters).filter(([,value])=>value));
  const groups:[string,string,Record<string,string>][]=[["faculty","Todas las facultades",Object.fromEntries((options.data?.faculties??[]).map(value=>[value,value]))],["academic_level","Todos los niveles",levelLabels],["modality","Todas las modalidades",modalityLabels],["status","Todos los estados",statusLabels]];
  return <div className="students-workspace careers-workspace"><div className="student-directory-banner"><GraduationCap/><div><strong>Una oferta académica con identidad institucional</strong><span>Abre cada programa para gestionar su coordinación, perfiles, requisitos, pensum y secciones vinculadas.</span></div></div><ResourcePage key={JSON.stringify(params)} config={careerConfig} queryParams={params} toolbarContent={<div className="student-filters">{groups.map(([name,label,values])=><select key={name} aria-label={label} value={filters[name]??""} onChange={event=>setFilters(current=>({...current,[name]:event.target.value}))}><option value="">{label}</option>{Object.entries(values).map(([value,text])=><option key={value} value={value}>{text}</option>)}</select>)}{Object.keys(params).length>0&&<button className="student-reset" onClick={()=>setFilters({})}>Limpiar filtros</button>}</div>}/></div>;
}
