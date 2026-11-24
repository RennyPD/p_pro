import { useQuery } from "@tanstack/react-query";
import type { ApiSchema } from "../../lib/apiTypes";
import { platformApi } from "../../lib/platformApi";

type Plan = ApiSchema<"PlanOut">;

export const subscriptionLabels: Record<
  string,
  { label: string; tone: "success" | "info" | "warning" | "danger" | "neutral" }
> = {
  trialing: { label: "En prueba", tone: "info" },
  active: { label: "Al día", tone: "success" },
  past_due: { label: "Pago pendiente", tone: "warning" },
  read_only: { label: "Solo lectura", tone: "danger" },
  suspended: { label: "Suspendida", tone: "danger" },
  canceled: { label: "Cancelada", tone: "neutral" },
};

export function usePlans() {
  return useQuery({
    queryKey: ["platform", "plans"],
    queryFn: () => platformApi.get<Plan[]>("/platform/plans").then(r => r.data),
  });
}
