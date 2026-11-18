import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { expect, it } from "vitest";

const root = join(__dirname, "..");
const hexColor = /#[0-9a-fA-F]{3,8}\b/;

function cssFiles(directory: string): string[] {
  return readdirSync(directory).flatMap(name => {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) return cssFiles(path);
    return name.endsWith(".css") ? [path] : [];
  });
}

it("uses design tokens instead of hand-written colors", () => {
  const offenders = cssFiles(root).flatMap(file =>
    readFileSync(file, "utf8")
      .split("\n")
      .map((line, index) => ({ line: line.trim(), number: index + 1 }))
      // Only token definitions (--name: value) may hold literal colors.
      .filter(({ line }) => hexColor.test(line) && !line.startsWith("--"))
      .map(({ line, number }) => `${relative(root, file)}:${number} ${line}`),
  );
  expect(offenders).toEqual([]);
});

it("keeps the muted text token at AA contrast", () => {
  const styles = readFileSync(join(root, "styles.css"), "utf8");
  expect(styles).toMatch(/--muted: #5b6678;/);
});
