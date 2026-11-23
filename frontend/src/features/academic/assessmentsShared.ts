import type { ApiSchema } from "../../lib/apiTypes";
import "./assessments.css";

export type Section = {
  section_id: number;
  code: string;
  subject_id: number;
  subject_name: string;
  teacher_name: string;
  period_name: string;
};
export type Assessment = ApiSchema<"AssessmentOut">;
export type Grade = {
  grade_id: number;
  assessment_id: number | null;
  grade_value: number;
  status: string;
};
export type Student = {
  enrollment_id: number;
  first_name: string;
  last_name: string;
  enrollment_number: string;
  grades: Grade[];
  grading_scale_id?: number | null;
};
export type Scale = ApiSchema<"ScaleBrief">;
export type Workspace = {
  roster: Student[];
  subject_id: number;
  period_name: string;
  grading_scales?: Scale[];
};
export type Final = {
  enrollment_id: number;
  weighted_grade: number;
  completed_weight: number;
  final: boolean;
  status: string;
  calculation_mode: string;
};
export type Template = ApiSchema<"AssessmentTemplateOut">;
export type Plan = ApiSchema<"PlanTemplateOut">;
export type Change = ApiSchema<"GradeChangeOut">;
export const labels: Record<string, string> = {
  draft: "Borrador",
  published: "Publicada",
  voided: "Anulada",
  created: "Registro",
  updated: "Corrección",
  in_progress: "Provisional",
  passed: "Aprobada",
  failed: "Reprobada",
};
export const cellKey = (enrollmentId: number, assessmentId: number) =>
  enrollmentId + ":" + assessmentId;
