/** Up to two initials of a person's name ("Sofía García" → "SG"). */
export function initials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase())
    .join("");
}
