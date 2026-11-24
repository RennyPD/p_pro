type Tone = "success" | "info" | "warning" | "danger" | "neutral";

export const billingStatus: Record<string, { label: string; tone: Tone }> = {
  trialing: { label: "En prueba", tone: "info" },
  active: { label: "Al día", tone: "success" },
  past_due: { label: "Pago pendiente", tone: "warning" },
  read_only: { label: "Solo lectura", tone: "danger" },
  suspended: { label: "Suspendida", tone: "danger" },
  canceled: { label: "Cancelada", tone: "neutral" },
};
