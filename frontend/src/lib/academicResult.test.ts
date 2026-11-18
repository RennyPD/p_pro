import { describe, expect, it } from "vitest";
import { describeAverage, provisionalReason, resultLabel, standingLabel } from "./academicResult";

describe("academic result vocabulary", () => {
  it("prefers final averages and never presents provisional ones as final", () => {
    expect(describeAverage({ finalAverage: 85, finalCount: 2 })).toMatchObject({ value: "85", kind: "final", note: "2 resultados definitivos" });
    expect(describeAverage({ finalAverage: null, provisionalAverage: 77.8, provisionalCount: 3 })).toMatchObject({ value: "77.8", kind: "provisional", note: "3 resultados sin cierre" });
    expect(describeAverage({ finalAverage: null })).toMatchObject({ value: "Sin datos", kind: "empty" });
  });
  it("translates technical states and explains provisional results", () => {
    expect(standingLabel("probation")).toBe("Observación académica");
    expect(standingLabel("no_final_results")).toBe("Sin resultados definitivos");
    expect(resultLabel("in_progress")).toBe("Provisional");
    expect(provisionalReason(100)).toBe("Plan completo · falta cerrar evaluaciones");
    expect(provisionalReason(40)).toBe("40% del plan publicado");
  });
});
