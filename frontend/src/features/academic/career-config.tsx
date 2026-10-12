import { Link } from "react-router-dom";
import { Badge } from "../../components/ui";
import { resources } from "../../config/resources";
import type { FieldConfig, ResourceConfig } from "../../types";

export const levelLabels: Record<string,string> = {technical:"Técnico superior", undergraduate:"Grado", graduate:"Maestría", postgraduate:"Postgrado"};
export const statusLabels: Record<string,string> = {draft:"En diseño", active:"Activo", suspended:"Admisión suspendida", archived:"Archivado"};
export const modalityLabels: Record<string,string> = {in_person:"Presencial", virtual:"Virtual", hybrid:"Semipresencial"};
export const termLabels: Record<string,string> = {bimester:"Bimestre",trimester:"Trimestre",quadrimester:"Cuatrimestre",semester:"Semestre",annual:"Año"};
const options = (labels:Record<string,string>) => Object.entries(labels).map(([value,label])=>({value,label}));
const institutional: FieldConfig[] = [
  {name:"status",label:"Estado del programa",section:"Organización institucional",type:"select",required:true,options:options(statusLabels)},
  {name:"modality",label:"Modalidad",section:"Organización institucional",type:"select",required:true,options:options(modalityLabels)},
  ...[{name:"faculty",label:"Facultad / escuela"},{name:"department",label:"Departamento académico"},{name:"coordinator_name",label:"Coordinación del programa"},{name:"contact_email",label:"Correo de coordinación",type:"email" as const},{name:"campus",label:"Sede / campus"},{name:"authorization_reference",label:"Referencia de aprobación institucional"}].map(field=>({...field,section:"Organización institucional"})),
  ...[{name:"admission_profile",label:"Perfil de ingreso"},{name:"graduate_profile",label:"Perfil de egreso y competencias"},{name:"professional_fields",label:"Campo de ejercicio profesional"},{name:"admission_requirements",label:"Requisitos de admisión"},{name:"graduation_requirements",label:"Requisitos de titulación"}].map(field=>({...field,section:"Formación y requisitos",type:"textarea" as const})),
];
export const careerConfig:ResourceConfig = {
  ...resources.careers, title:"Catálogo de carreras", singular:"programa", allowDelete:false,
  defaultValues:{status:"draft",modality:"in_person",academic_level:"undergraduate",term_type:"semester",duration_terms:8,required_credits:120,curriculum_version:String(new Date().getFullYear())},
  description:"Administra la identidad institucional, el perfil formativo y el plan de estudios de cada programa.",
  searchPlaceholder:"Buscar por código, programa, título o facultad",
  columns:[
    {key:"name",label:"Programa académico",render:(_,row)=><div className="student-table-identity"><span className="student-initials">{String(row.code).slice(0,2)}</span><div><Link to={`/careers/${row.career_id}`}><strong>{row.name}</strong></Link><small>{row.code} · {row.degree_title || "Título por definir"}</small></div></div>},
    {key:"faculty",label:"Adscripción",render:(value,row)=><div className="student-cell"><strong>{value || "Sin facultad asignada"}</strong><small>{row.coordinator_name || "Coordinación pendiente"}</small></div>},
    {key:"academic_level",label:"Nivel y modalidad",render:(value,row)=><div className="student-cell"><strong>{levelLabels[String(value)]}</strong><small>{modalityLabels[String(row.modality)]}</small></div>},
    {key:"status",label:"Estado",render:value=><Badge tone={value==="active"?"success":value==="archived"?"neutral":"warning"}>{statusLabels[String(value)]}</Badge>},
    {key:"curriculum_version",label:"Plan vigente",render:(value,row)=><div className="student-cell"><strong>Versión {value}</strong><small>{row.required_credits} créditos · {row.duration_terms} períodos</small></div>},
  ],
  fields:[...resources.careers.fields.map(field=>({...field,section:"Identidad y estructura académica",...(field.name==="description"?{label:"Descripción del programa",type:"textarea" as const}:{})})),...institutional],
};
