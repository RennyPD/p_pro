import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import { fetchAllOptions } from "./options";

afterEach(() => vi.restoreAllMocks());

it("loads catalogs beyond 100 records while retaining filters", async () => {
  const records = Array.from({ length: 125 }, (_, i) => ({ id: i + 1 }));
  const get = vi.spyOn(api, "get").mockImplementation(async (_path, config) => { const { skip } = config?.params as { skip: number }; return { data: records.slice(skip, skip + 100) }; });
  expect(await fetchAllOptions("/items", "id", { status: "active" })).toEqual(records);
  expect(get).toHaveBeenLastCalledWith("/items", expect.objectContaining({ params: { skip: 100, limit: 100, status: "active" } }));
});

it("does not loop when an endpoint ignores pagination", async () => {
  const get = vi.spyOn(api, "get").mockResolvedValue({ data: Array.from({ length: 100 }, (_, id) => ({ id })) });
  expect(await fetchAllOptions("/items", "id")).toHaveLength(100);
  expect(get).toHaveBeenCalledTimes(2);
});

it("does not present a partial list when a later page fails", async () => {
  vi.spyOn(api, "get").mockResolvedValueOnce({ data: Array.from({ length: 100 }, (_, id) => ({ id })) }).mockRejectedValueOnce(new Error("offline"));
  await expect(fetchAllOptions("/items", "id")).rejects.toThrow("offline");
});
