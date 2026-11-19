/** "Nueva asignatura", "Nuevo período": Spanish gender inferred from the noun's ending. */
export function newLabel(singular: string) {
  const noun = singular.split(" ")[0];
  return `${/(a|ción|sión)$/.test(noun) ? "Nueva" : "Nuevo"} ${singular}`;
}
