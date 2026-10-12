import { Link } from "react-router-dom";
import { Badge } from "../../components/ui";
import { resources } from "../../config/resources";
import type { FieldConfig, ResourceConfig } from "../../types";

export const employmentLabels: Record<string, string> = { full_time: "Tiempo completo", part_time: "Tiempo parcial", adjunct: "Por asignatura", substitute: "Suplente" };
const extraFields: FieldConfig[] = [
  { name: "document_number", label: "Documento de identidad", section: "Identificación personal" },
  { name: "birth_date", label: "Fecha de nacimiento", type: "date", section: "Identificación personal" },
  { name: "nationality", label: "Nacionalidad", section: "Identificación personal" },
  { name: "academic_degree", label: "Título o grado académico", placeholder: "Ej. Maestría en Educación", section: "Formación y experiencia" },
  { name: "alma_mater", label: "Institución de formación", section: "Formación y experiencia" },
  { name: "professional_license", label: "Registro o habilitación profesional", section: "Formación y experiencia" },
  { name: "experience_years", label: "Años de experiencia docente", type: "number", section: "Formación y experiencia" },
  { name: "employee_code", label: "Código institucional", placeholder: "Ej. DOC-0001", section: "Vinculación institucional" },
  { name: "department", label: "Departamento o área académica", section: "Vinculación institucional" },
  { name: "teaching_category", label: "Categoría docente", placeholder: "Ej. Titular, adjunto, instructor", section: "Vinculación institucional" },
  { name: "employment_type", label: "Tipo de vinculación", type: "select", options: Object.entries(employmentLabels).map(([value,label]) => ({value,label})), section: "Vinculación institucional" },
  { name: "appointment_date", label: "Fecha de ingreso a la institución", type: "date", section: "Vinculación institucional" },
  { name: "emergency_contact_name", label: "Nombre del contacto", section: "Contacto de emergencia" },
  { name: "emergency_contact_phone", label: "Teléfono de emergencia", section: "Contacto de emergencia" },
  { name: "emergency_contact_relationship", label: "Parentesco o relación", section: "Contacto de emergencia" },
];
const baseFields = (names: string[], section: string): FieldConfig[] => resources.teachers.fields.filter(field => names.includes(field.name)).map(field => ({...field,section}));
export const teacherConfig: ResourceConfig = {
  ...resources.teachers,
  title: "Gestión de docentes",
  description: "Directorio del equipo académico: formación, vinculación institucional y expedientes docentes.",
  searchPlaceholder: "Nombre, código, especialidad o departamento",
  allowDelete: false,
  columns: [
    { key: "first_name", label: "Docente", render: (_,row) => <Link className="student-table-identity" to={`/teachers/${row.teacher_id}`}><span className="student-initials">{String(row.first_name).slice(0,1)}{String(row.last_name).slice(0,1)}</span><span><strong>{row.first_name} {row.last_name}</strong><small>{row.employee_code || "Código sin registrar"}</small></span></Link> },
    { key: "specialty", label: "Perfil académico", render: (value,row) => <div className="student-cell"><strong>{value}</strong><small>{row.academic_degree || "Formación sin registrar"}</small></div> },
    { key: "department", label: "Vinculación", render: (value,row) => <div className="student-cell"><strong>{value || "Área sin registrar"}</strong><small>{employmentLabels[String(row.employment_type)] || "Vinculación sin registrar"}</small></div> },
    { key: "active", label: "Situación", render: value => <Badge tone={value ? "success" : "neutral"}>{value ? "Activo" : "Inactivo"}</Badge> },
    { key: "email", label: "Contacto", render: (value,row) => <div className="student-cell"><span className="student-email" title={String(value)}>{value}</span><small>{row.telephone}</small></div> },
  ],
  fields: [
    ...baseFields(["first_name","last_name"], "Identificación personal"),
    ...extraFields.filter(field => field.section === "Identificación personal"),
    ...baseFields(["email","telephone","address"], "Contacto y domicilio"),
    ...baseFields(["specialty"], "Formación y experiencia"),
    ...extraFields.filter(field => field.section === "Formación y experiencia"),
    ...extraFields.filter(field => field.section === "Vinculación institucional"),
    ...baseFields(["active"], "Vinculación institucional"),
    ...extraFields.filter(field => field.section === "Contacto de emergencia"),
  ],
};
