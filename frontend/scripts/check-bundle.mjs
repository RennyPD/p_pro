/* global URL, console, process */
// Fails when the entry chunk grows past its budget (audit B2, Fase 4 C).
// Pages load on demand; a new eager import in App.tsx would show up here.
import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const BUDGET_KB = 250;
const dist = new URL("../dist/", import.meta.url).pathname;
const html = readFileSync(join(dist, "index.html"), "utf8");
const entry = html.match(/<script[^>]+src="\/(assets\/index-[^"]+\.js)"/)?.[1];
if (!entry) {
  console.error("No se encontró el paquete principal en dist/index.html. Ejecuta npm run build.");
  process.exit(1);
}
const size = statSync(join(dist, entry)).size / 1024;
const message = `Paquete principal ${entry}: ${size.toFixed(1)} KB (límite ${BUDGET_KB} KB)`;
if (size > BUDGET_KB) {
  console.error(`${message}. Carga la página nueva con React.lazy en App.tsx.`);
  process.exit(1);
}
console.log(message);
