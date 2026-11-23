import { describe, expect, it } from "vitest";
import { gradeText } from "./grades";

describe("gradeText", () => {
  it("shows the scale label, numbers as they are, and the value for staff", () => {
    expect(gradeText(null, "B")).toBe("—");
    expect(gradeText(84.6, "85")).toBe("85");
    expect(gradeText(84.6)).toBe("84.6");
    expect(gradeText(95, "Logrado")).toBe("Logrado");
    expect(gradeText(85, "B", true)).toBe("B · 85");
  });
});
