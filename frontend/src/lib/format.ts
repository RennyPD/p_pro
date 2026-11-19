/**
 * Single source for dates, times and money shown to people.
 * Always Spanish (Dominican Republic) and the institution's time zone, whatever
 * the browser language is, so every screen reads "18 nov 2026, 4:40 p. m.".
 */
const LOCALE = "es-DO";
const TIME_ZONE = "America/Santo_Domingo";

const dateFormat = new Intl.DateTimeFormat(LOCALE, {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: TIME_ZONE,
});
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: TIME_ZONE,
});
const moneyFormat = new Intl.NumberFormat(LOCALE, { style: "currency", currency: "DOP" });

/**
 * Parses API values: "2026-11-18" is a calendar date (kept at local noon so it
 * never shifts a day); timestamps without zone come from the API in UTC.
 */
export function parseApiDate(value: string | Date): Date {
  if (value instanceof Date) return value;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date(`${value}T12:00:00`);
  return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
}

const valid = (date: Date) => !Number.isNaN(date.getTime());

/** "18 nov 2026" */
export function formatDate(value: string | Date | null | undefined, fallback = "—") {
  if (!value) return fallback;
  const date = parseApiDate(value);
  return valid(date) ? dateFormat.format(date) : String(value);
}

/** "18 nov 2026, 4:40 p. m." — date-only values are shown without time. */
export function formatDateTime(value: string | Date | null | undefined, fallback = "—") {
  if (!value) return fallback;
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value);
  const date = parseApiDate(value);
  return valid(date) ? dateTimeFormat.format(date) : String(value);
}

/** "08:00:00" → "8:00 a. m." (or "08:00" with a 24-hour clock). */
export function formatTime(value: string | null | undefined, clock12 = true) {
  if (!value) return "—";
  const [hour, minute] = value.split(":").map(Number);
  if (Number.isNaN(hour)) return value;
  return new Intl.DateTimeFormat(LOCALE, {
    hour: clock12 ? "numeric" : "2-digit",
    minute: "2-digit",
    hour12: clock12,
  })
    .format(new Date(2000, 0, 1, hour, minute || 0))
    .replace(/\s/g, "\u00a0");
}

/** "RD$2,550.00" */
export const formatMoney = (amount: number | null | undefined) => moneyFormat.format(amount || 0);

/** Today's calendar date in the institution, as "YYYY-MM-DD". */
export const todayIso = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE }).format(new Date());
