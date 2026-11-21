import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

const css = readFileSync(join(__dirname, "..", "workspace-design.css"), "utf8");
const zIndex = (selector: string) => {
  const start = css.indexOf(`${selector} {`);
  expect(start, `${selector} must exist`).toBeGreaterThan(-1);
  return Number(/z-index:\s*(\d+)/.exec(css.slice(start, css.indexOf("}", start)))?.[1]);
};

it("keeps an open lookup list above the sticky modal actions", () => {
  expect(zIndex(".lookup-field:has(.lookup-popover)")).toBeGreaterThan(
    zIndex(".modal form > .form-actions"),
  );
});

it("only sticks the footer of a modal's own form, not of cards listed inside it", () => {
  expect(css).not.toMatch(/\.modal \.form-actions \{[^}]*sticky/);
});

it("lets rich first cells (name + subtitle) wrap instead of overflowing the next column", () => {
  const table = readFileSync(
    join(__dirname, "..", "features/resources/resource-table.css"),
    "utf8",
  );
  expect(table).toMatch(/td:first-child:not\(:has\(div\)\)/);
});
