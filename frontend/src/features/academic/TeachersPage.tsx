import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { ArrowUpRight, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ResourcePage } from "../resources/ResourcePage";
import { employmentLabels, teacherConfig } from "./teacher-config";
import "./students.css";
import "./teachers.css";

export function TeachersPage() {
  const [department, setDepartment] = useState("");
  const departments = useQuery<string[]>({queryKey:["teacher-departments"],queryFn:()=>api.get("/teachers/departments").then(response=>response.data)});
  const [status, setStatus] = useState("");
  const [employment, setEmployment] = useState("");
  const params: Record<string, string | number> = {};
  if (department) params.department = department;
  if (status) params.active = status;
  if (employment) params.employment_type = employment;
  return <div className="students-workspace teachers-workspace"><div className="student-directory-banner"><Users/><div><strong>El equipo académico, en contexto</strong><span>Consulta la formación, la vinculación y las secciones de cada docente desde su expediente institucional.</span></div></div><ResourcePage key={`${department}-${status}-${employment}`} config={teacherConfig} queryParams={params} toolbarContent={<div className="student-filters"><select aria-label="Filtrar por departamento docente" value={department} onChange={event=>setDepartment(event.target.value)}><option value="">Todos los departamentos</option>{departments.data?.map(value=><option key={value}>{value}</option>)}</select><select aria-label="Filtrar docentes por situación" value={status} onChange={event => setStatus(event.target.value)}><option value="">Todos los estados</option><option value="true">Activos</option><option value="false">Inactivos</option></select><select aria-label="Filtrar por vinculación docente" value={employment} onChange={event => setEmployment(event.target.value)}><option value="">Todas las vinculaciones</option>{Object.entries(employmentLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select>{(department || status || employment) && <button className="student-reset" onClick={() => { setDepartment(""); setStatus(""); setEmployment(""); }}>Limpiar filtros</button>}</div>} rowActions={row => <Link className="student-open" to={`/teachers/${row.teacher_id}`} title="Abrir expediente docente" aria-label={`Abrir expediente de ${row.first_name} ${row.last_name}`}><ArrowUpRight size={18}/></Link>}/></div>;
}
