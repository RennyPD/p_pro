import type { ApiSchema } from "../../lib/apiTypes";

type Tone = "success" | "info" | "warning" | "danger" | "neutral";

export const ticketStatus: Record<string, { label: string; tone: Tone }> = {
  open: { label: "Abierto", tone: "info" },
  in_progress: { label: "En revisión", tone: "info" },
  waiting: { label: "Esperando tu respuesta", tone: "warning" },
  resolved: { label: "Resuelto", tone: "success" },
  closed: { label: "Cerrado", tone: "neutral" },
};

export const ticketCategories: Record<string, string> = {
  uso: "Cómo usar Nexo",
  error: "Algo no funciona",
  facturacion: "Plan y facturación",
  datos: "Datos y privacidad",
  otro: "Otro",
};

export type TicketMessage = ApiSchema<"TicketMessageOut">;
/** Tickets of the platform inbox carry the institution and the requester's email. */
export type Ticket = ApiSchema<"TicketOut"> & Partial<ApiSchema<"PlatformTicketOut">>;
