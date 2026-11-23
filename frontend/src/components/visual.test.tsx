import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it } from "vitest";
import { initials } from "../lib/text";
import { Avatar, Chip, Metric, MetricRow, Progress, Section, Tabs } from "./visual";

afterEach(cleanup);

it("renders metrics as links only when there is somewhere to go", () => {
  render(
    <MemoryRouter>
      <MetricRow label="Indicadores">
        <Metric label="Vencido" value="RD$500.00" tone="danger" to="/finance" />
        <Metric label="Estudiantes" value={120} note="activos" />
      </MetricRow>
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: /Vencido/ })).toHaveAttribute("href", "/finance");
  expect(screen.queryByRole("link", { name: /Estudiantes/ })).not.toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Indicadores" })).toBeInTheDocument();
});

it("moves between tabs with the arrow keys and shows pending counts", () => {
  function Example() {
    const [tab, setTab] = useState<"a" | "b">("a");
    return (
      <Tabs
        label="Áreas"
        value={tab}
        onChange={setTab}
        items={[
          { key: "a", label: "Cuotas" },
          { key: "b", label: "Transferencias", count: 2 },
        ]}
      />
    );
  }
  render(<Example />);
  const first = screen.getByRole("tab", { name: "Cuotas" });
  expect(first).toHaveAttribute("aria-selected", "true");
  fireEvent.keyDown(first, { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: /Transferencias/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(screen.getByText("2")).toBeInTheDocument();
});

it("clamps progress, shows initials and labels sections and chips", () => {
  render(
    <Section title="Pagos" kicker="Resumen" action={<button>Ver</button>}>
      <Progress value={140} label="Avance" />
      <Avatar name="Sofía García" />
      <Chip tone="warning">En revisión</Chip>
    </Section>,
  );
  expect(screen.getByRole("meter", { name: "Avance" })).toHaveAttribute("aria-valuenow", "100");
  expect(screen.getByText("SG")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Pagos" })).toBeInTheDocument();
  expect(screen.getByText("En revisión")).toBeInTheDocument();
  expect(initials("ana")).toBe("A");
});
