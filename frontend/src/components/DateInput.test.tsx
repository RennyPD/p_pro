import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { displayToIso, isoToDisplay } from "../lib/dateText";
import { DateInput } from "./DateInput";

afterEach(cleanup);

describe("DateInput", () => {
  it("converts between dd/mm/aaaa and ISO, rejecting impossible dates", () => {
    expect(isoToDisplay("2026-11-18")).toBe("18/11/2026");
    expect(displayToIso("18/11/2026")).toBe("2026-11-18");
    expect(displayToIso("31/02/2026")).toBeNull();
  });
  it("masks typing and reports ISO only for complete, valid dates", () => {
    const change = vi.fn();
    render(<DateInput aria-label="Fecha" onValueChange={change} />);
    const input = screen.getByLabelText("Fecha");
    fireEvent.change(input, { target: { value: "1811" } });
    expect(input).toHaveValue("18/11");
    expect(change).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "18112026" } });
    expect(input).toHaveValue("18/11/2026");
    expect(change).toHaveBeenLastCalledWith("2026-11-18");
  });
  it("submits ISO through FormData and restores the value a parent refuses", () => {
    function Guarded() {
      const [value, setValue] = useState("2026-01-05");
      return (
        <form aria-label="f">
          <DateInput
            aria-label="Fecha"
            name="day"
            value={value}
            onValueChange={next => {
              if (next !== "2026-02-01") setValue(next);
            }}
          />
        </form>
      );
    }
    render(<Guarded />);
    const input = screen.getByLabelText("Fecha");
    expect(
      new FormData(screen.getByRole("form", { name: "f" }) as HTMLFormElement).get("day"),
    ).toBe("2026-01-05");
    fireEvent.change(input, { target: { value: "01022026" } });
    expect(input).toHaveValue("05/01/2026");
  });
});
