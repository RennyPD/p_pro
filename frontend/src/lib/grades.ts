/**
 * How a 0–100 grade is shown with its program's scale (Fase 3 D).
 * Letter and conceptual scales show their label; staff views can add the value.
 */
export function gradeText(
  value: number | null | undefined,
  label?: string | null,
  withValue = false,
): string {
  if (value === null || value === undefined) return "—";
  if (!label || !Number.isNaN(Number(label))) return label ?? String(value);
  return withValue ? `${label} · ${value}` : label;
}
