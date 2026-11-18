const relative = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
const HOUR = 60;
const DAY = 24 * HOUR;

/** "Vence mañana", "Venció hace 3 días", "Venció hace 6 semanas". */
export function dueLabel(due: Date, now = new Date()): string {
  const minutes = Math.round((due.getTime() - now.getTime()) / 60_000);
  const size = Math.abs(minutes);
  const [value, unit]: [number, Intl.RelativeTimeFormatUnit] =
    size < HOUR
      ? [minutes, "minute"]
      : size < DAY
        ? [Math.round(minutes / HOUR), "hour"]
        : size < 14 * DAY
          ? [Math.round(minutes / DAY), "day"]
          : size < 60 * DAY
            ? [Math.round(minutes / (7 * DAY)), "week"]
            : [Math.round(minutes / (30 * DAY)), "month"];
  return `${minutes < 0 ? "Venció" : "Vence"} ${relative.format(value, unit)}`;
}
