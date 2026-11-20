/** Month labels for billing cycles ("YYYY-MM"). */

const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const MONTHS_LONG = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
];

/** "2026-08" → "ago 2026" (or "agosto 2026" when long). */
export function cycleLabel(cycle: string, long = false) {
  const [year, month] = cycle.split("-").map(Number);
  return `${(long ? MONTHS_LONG : MONTHS)[month - 1]} ${year}`;
}
