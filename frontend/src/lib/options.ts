import { api } from "./api";

/** Load paginated catalogs without silently hiding records after the first page.
 * Some catalog endpoints ignore pagination; deduplication also handles those.
 */
export async function fetchAllOptions<T extends object>(
  endpoint: string,
  valueKey: keyof T,
  params: Record<string, string | number> = {},
  signal?: AbortSignal,
): Promise<T[]> {
  const items = new Map<unknown, T>();
  const limit = 100;
  for (let skip = 0; ; skip += limit) {
    const { data } = await api.get<T[]>(endpoint, { params: { ...params, skip, limit }, signal });
    if (!Array.isArray(data)) throw new Error("El catálogo no devolvió una lista de opciones.");
    const previousSize = items.size;
    for (const item of data) items.set(item[valueKey], item);
    if (data.length !== limit || items.size === previousSize) return [...items.values()];
  }
}
