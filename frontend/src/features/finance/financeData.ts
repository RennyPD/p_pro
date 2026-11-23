import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDateTime, formatMoney, todayIso } from "../../lib/format";

export type Account = ApiSchema<"FinanceAccountListItem">;
export type Summary = ApiSchema<"StudentFinanceSummary">;
export type Transaction = ApiSchema<"FinanceTransaction">;
export type Transfer = ApiSchema<"TransferOut">;
export type Plan = ApiSchema<"PaymentPlanStatus">;
export type Concept = ApiSchema<"BillingConceptOut">;
export type Closing = ApiSchema<"CashClosingOut">;
export type FinanceEvent = ApiSchema<"FinanceEventOut">;
export type FinanceOptions = ApiSchema<"FinanceOptions">;
export type Action = { path: string; payload: unknown; method?: "put"; done?: () => void };

export const money = (value = 0) => formatMoney(value);
export const auditNames: Record<string, string> = {
  "account.updated": "Configuración de cuenta",
  "charge.created": "Cargo registrado",
  "payment.posted": "Pago confirmado",
  "adjustment.created": "Ajuste registrado",
  "transaction.reversed": "Movimiento reversado",
  "plan.created": "Plan creado",
  "plan.cancelled": "Plan cancelado",
  "transfer.submitted": "Transferencia reportada",
  "transfer.reviewed": "Transferencia revisada",
};
export function auditDetail(value: string) {
  const names: Record<string, string> = {
    reason: "Motivo",
    description: "Concepto",
    reference: "Referencia",
    method: "Método",
    receipt: "Recibo",
    amount_cents: "Monto",
    due_date: "Vencimiento",
    status: "Estado",
    installments: "Cuotas",
    first_due_date: "Primera cuota",
    balance_before: "Balance anterior",
    balance_after: "Balance posterior",
    name: "Nombre",
    before: "Configuración anterior",
    after: "Configuración nueva",
  };
  try {
    return Object.entries(JSON.parse(value) as Record<string, unknown>)
      .filter(([key]) => key in names)
      .map(
        ([key, v]) =>
          `${names[key]}: ${
            key === "amount_cents"
              ? money(Number(v) / 100)
              : key.startsWith("balance_")
                ? money(Number(v))
                : typeof v === "object" && v
                  ? Object.entries(v)
                      .map(
                        ([field, n]) =>
                          `${field === "cutoff_day" ? "Corte" : field === "due_day" ? "Vencimiento" : field} día ${n}`,
                      )
                      .join(", ")
                  : labels[String(v)] || String(v ?? "—")
          }`,
      )
      .join(" · ");
  } catch {
    return "Detalle histórico no disponible";
  }
}
export const day = todayIso;
export const ACCOUNTS_PAGE = 20;
export const dateLabel = (value: string) => formatDateTime(value);
export const labels: Record<string, string> = {
  charge: "Cargo",
  payment: "Abono",
  adjustment: "Ajuste",
  cash: "Efectivo",
  transfer: "Transferencia verificada",
  legacy: "Registro anterior",
  posted: "Registrado",
  reversed: "Reversado",
  pending: "Pendiente",
  approved: "Aprobada",
  rejected: "Rechazada",
  paid: "Pagada",
  partial: "Parcial",
  overdue: "Vencida",
  discount: "Descuento",
  scholarship: "Beca",
  credit: "Crédito",
  late_fee: "Mora",
  debit: "Débito",
  once: "Única",
  monthly: "Mensual",
  term: "Por período",
  annual: "Anual",
};
export function useActions() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (a: Action) =>
      a.method === "put" ? api.put(a.path, a.payload) : api.post(a.path, a.payload),
    onSuccess: (_r, a) => {
      for (const key of [
        "finance",
        "finance-accounts",
        "finance-plans",
        "finance-transfers",
        "finance-history",
        "finance-closings",
        "finance-concepts",
        "dashboard",
        "guardian-overview",
      ])
        void client.invalidateQueries({ queryKey: [key] });
      a.done?.();
      toast.success("Operación registrada");
    },
    onError: e => toast.error(apiMessage(e)),
  });
}
export async function download(path: string, name: string) {
  try {
    const r = await api.get(path, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = r.headers?.["content-disposition"]?.match(/filename="([^"]+)"/)?.[1] || name;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    toast.error(apiMessage(e));
  }
}
