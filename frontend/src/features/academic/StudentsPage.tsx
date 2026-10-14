import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import type { EntityRecord } from "../../types";
import { ResourcePage } from "../resources/ResourcePage";
import { studentConfig } from "./student-config";
import "./students.css";

export function StudentsPage() {
  const [career, setCareer] = useState("");
  const [status, setStatus] = useState("");
  const [hold, setHold] = useState("");
  const careers = useQuery<EntityRecord[]>({ queryKey: ["lookup", "/careers/"], queryFn: () => api.get("/careers/", { params: { limit: 100 } }).then(response => response.data) });
  const params: Record<string, string | number> = {};
  if (career) params.career_id = career;
  if (status) params.active = status;
  if (hold) params.hold = hold;
  return <div className="students-workspace"><ResourcePage key={`${career}-${status}-${hold}`} config={studentConfig} queryParams={params} toolbarContent={<div className="student-filters"><select aria-label="Filtrar por programa" value={career} onChange={event => setCareer(event.target.value)}><option value="">Todos los programas</option>{careers.data?.map(item => <option key={String(item.career_id)} value={String(item.career_id)}>{item.name}</option>)}</select><select aria-label="Filtrar por situación" value={status} onChange={event => setStatus(event.target.value)}><option value="">Todos los estados</option><option value="true">Activos</option><option value="false">Inactivos</option></select><select aria-label="Filtrar por bloqueos" value={hold} onChange={event => setHold(event.target.value)}><option value="">Todos los controles</option><option value="clear">Sin bloqueos</option><option value="academic">Bloqueo académico</option><option value="financial">Bloqueo financiero</option></select>{(career || status || hold) && <button className="student-reset" onClick={() => { setCareer(""); setStatus(""); setHold(""); }}>Limpiar filtros</button>}</div>} rowActions={row => <Link className="student-open" to={`/students/${row.student_id}`} aria-label={`Abrir expediente de ${row.first_name} ${row.last_name}`} title="Abrir expediente"><ArrowUpRight size={18}/></Link>} /></div>;
}
