import type { Tone } from "../../lib/academicResult";
import type { ApiSchema } from "../../lib/apiTypes";

export type Statement = ApiSchema<"AccountStatement">;
export type Obligation = ApiSchema<"StatementObligation">;
export type Transfer = ApiSchema<"TransferOut">;
export type InboxItem = ApiSchema<"TransferInboxItem">;
export type FamilyFinance = ApiSchema<"FamilyFinance">;
export type FamilyTransfer = ApiSchema<"FamilyTransferOut">;
export type FinanceOptions = { transfer_instructions: string; simulator_enabled: boolean };

export const obligationStatus: Record<string, { label: string; tone: Tone }> = {
  paid: { label: "Pagada", tone: "success" },
  partial: { label: "Abono parcial", tone: "info" },
  pending: { label: "Pendiente", tone: "neutral" },
  overdue: { label: "Vencida", tone: "danger" },
};

export const transferStatus: Record<string, { label: string; tone: Tone }> = {
  pending: { label: "En revisión", tone: "warning" },
  approved: { label: "Aprobada", tone: "success" },
  rejected: { label: "Rechazada", tone: "danger" },
};

export const paymentMethods: Record<string, string> = {
  cash: "Efectivo",
  card: "Tarjeta",
  transfer: "Transferencia",
  check: "Cheque",
  legacy: "Registro anterior",
};

export const MAX_PROOF = 2 * 1024 * 1024;

/** File contents as base64 without the data URL prefix. */
export function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("No se pudo leer el comprobante"));
    reader.readAsDataURL(file);
  });
}

/** Amount typed by the user ("1,250.5") as a two-decimal string for the API. */
export function toAmount(value: string): string | null {
  const number = Number(value.replace(/,/g, ""));
  if (!Number.isFinite(number) || number <= 0) return null;
  return number.toFixed(2);
}

export type TransferGroup = { key: string; items: InboxItem[]; batch: boolean };

/** Reports of the same family transfer are reviewed together. */
export function groupTransfers(items: InboxItem[]): TransferGroup[] {
  const groups: TransferGroup[] = [];
  const byBatch = new Map<number, TransferGroup>();
  for (const item of items) {
    if (item.batch_id) {
      const existing = byBatch.get(item.batch_id);
      if (existing) {
        existing.items.push(item);
        continue;
      }
      const group = { key: `batch-${item.batch_id}`, items: [item], batch: true };
      byBatch.set(item.batch_id, group);
      groups.push(group);
    } else {
      groups.push({ key: `single-${item.transfer_request_id}`, items: [item], batch: false });
    }
  }
  for (const group of groups)
    group.items.sort((a, b) => a.transfer_request_id - b.transfer_request_id);
  return groups;
}
