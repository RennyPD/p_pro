import { Link } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { Badge } from "../../components/ui";
import { resources } from "../../config/resources";
import type { FieldConfig, ResourceConfig } from "../../types";

const extraFields: FieldConfig[] = [
  { name: "document_number", label: "Documento de identidad", section: "Identificación personal" },
  { name: "birth_date", label: "Fecha de nacimiento", type: "date", section: "Identificación personal" },
  { name: "nationality", label: "Nacionalidad", section: "Identificación personal" },
  { name: "admission_date", label: "Fecha de ingreso", type: "date", section: "Ingreso y procedencia" },
  { name: "previous_school", label: "Centro educativo de procedencia", section: "Ingreso y procedencia" },
  { name: "emergency_contact_name", label: "Nombre del contacto", section: "Contacto de emergencia" },
  { name: "emergency_contact_phone", label: "Teléfono de emergencia", section: "Contacto de emergencia" },
  { name: "emergency_contact_relationship", label: "Parentesco o relación", section: "Contacto de emergencia" },
];
export const studentConfig: ResourceConfig = {
  ...resources.students,
  title: "Gestión de estudiantes",
  description: "Directorio institucional y expedientes: identidad, trayectoria y seguimiento de cada estudiante.",
  searchPlaceholder: "Nombre, matrícula, correo o documento",
  allowDelete: false,
  columns: [
    { key: "first_name", label: "Estudiante", render: (_, row) => <Link className="student-table-identity" to={`/students/${row.student_id}`}><span className="student-initials">{String(row.first_name).slice(0,1)}{String(row.last_name).slice(0,1)}</span><span><strong>{row.first_name} {row.last_name}</strong><small>{row.enrollment_number}</small>{row.document_number&&<small>Doc. {row.document_number}</small>}</span></Link> },
    { key: "career_name", label: "Programa académico", render: (value, row) => <div className="student-cell"><strong>{value}</strong><small>{row.admission_date ? `Ingreso: ${row.admission_date}` : "Ingreso sin registrar"}</small></div> },
    { key: "active", label: "Situación", render: value => <Badge tone={value ? "success" : "neutral"}>{value ? "Activo" : "Inactivo"}</Badge> },
    { key: "academic_hold", label: "Control académico", render: (_, row) => <div className="student-flags">{row.academic_hold && <Badge tone="warning">Bloqueo académico</Badge>}{row.financial_hold && <Badge tone="danger">Bloqueo financiero</Badge>}{!row.academic_hold && !row.financial_hold && <span className="student-clear"><ShieldCheck size={15}/> Sin bloqueos</span>}</div> },
    { key: "email", label: "Contacto", render: (value, row) => <div className="student-cell"><span className="student-email" title={String(value)}>{value}</span><small>{row.telephone || "Sin teléfono"}</small></div> },
  ],
  fields: [
    ...resources.students.fields.filter(field => ["first_name", "last_name"].includes(field.name)).map(field => ({ ...field, section: "Identificación personal" })),
    ...extraFields.filter(field => field.section === "Identificación personal"),
    ...resources.students.fields.filter(field => ["email", "telephone", "address"].includes(field.name)).map(field => ({ ...field, section: "Contacto y domicilio" })),
    ...resources.students.fields.filter(field => ["enrollment_number", "career_id"].includes(field.name)).map(field => ({ ...field, section: "Ingreso y procedencia" })),
    ...extraFields.filter(field => field.section === "Ingreso y procedencia"),
    ...extraFields.filter(field => field.section === "Contacto de emergencia"),
    ...resources.students.fields.filter(field => ["active", "academic_hold", "financial_hold"].includes(field.name)).map(field => ({ ...field, section: "Situación administrativa" })),
  ],
};
