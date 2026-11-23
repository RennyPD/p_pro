import type { ApiSchema } from "../../lib/apiTypes";
import type { VisualTone } from "../../components/visual";

export type ClassGroup = ApiSchema<"ClassGroupOut">;
export type ClassGroupDetail = ApiSchema<"ClassGroupDetail">;
export type GroupMember = ApiSchema<"ClassGroupMemberOut">;
export type GroupSubject = ApiSchema<"ClassGroupSubjectOut">;
export type Promotion = ApiSchema<"PromotionProposal">;
export type PromotionRow = ApiSchema<"PromotionRow">;
export type Reinscription = ApiSchema<"ReinscriptionOut">;
export type SchoolYear = ApiSchema<"SchoolYearOut">;
export type StudentRow = ApiSchema<"StudentOut">;
export type CareerRow = ApiSchema<"CareerOut">;
export type TeacherRow = ApiSchema<"TeacherOut">;

export const resultLabels: Record<string, { label: string; tone: VisualTone }> = {
  pending: { label: "Pendiente", tone: "default" },
  promoted: { label: "Promovido", tone: "success" },
  completivo: { label: "Completivo", tone: "warning" },
  extraordinario: { label: "Extraordinario", tone: "warning" },
  repeated: { label: "Repite", tone: "danger" },
};

export const memberStatus: Record<string, string> = {
  enrolled: "Inscrito",
  withdrawn: "Retirado",
  transferred: "Trasladado",
};

export const groupKey = (id: number | string) => ["class-group", String(id)];
