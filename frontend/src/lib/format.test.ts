import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, formatMoney, formatTime, parseApiDate } from "./format";

describe("formatting", () => {
  it("keeps calendar dates on their day and treats zone-less timestamps as UTC", () => {
    expect(formatDate("2026-08-17")).toMatch(/17 ago\.?( de)? 2026/);
    expect(parseApiDate("2026-11-18T20:40:00").toISOString()).toBe("2026-11-18T20:40:00.000Z");
    expect(formatDateTime("2026-11-18T20:40:00")).toMatch(/18 nov\.?( de)? 2026.*4:40/);
    expect(formatDateTime("2026-08-17")).toBe(formatDate("2026-08-17"));
    expect(formatDate(null, "Sin registrar")).toBe("Sin registrar");
  });
  it("formats times and money in Dominican Spanish", () => {
    expect(formatTime("08:00:00")).toMatch(/^8:00\sa.\sm.$/);
    expect(formatTime("17:30:00", false)).toBe("17:30");
    expect(formatMoney(2550)).toMatch(/2,550\.00/);
  });
});
