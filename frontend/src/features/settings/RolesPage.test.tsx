import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { RolesPage } from "./RolesPage";
import { fitsScope, roleCode, togglePermission, type PermissionDef } from "./roleRules";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const catalog: PermissionDef[] = [
  {
    slug: "finance.view",
    module: "Finanzas",
    label: "Consultar finanzas",
    description: "Cuentas",
    institutional: true,
  },
  {
    slug: "finance.manage",
    module: "Finanzas",
    label: "Gestionar finanzas",
    description: "Pagos",
    institutional: true,
  },
  {
    slug: "grades.manage",
    module: "Calificaciones",
    label: "Gestionar calificaciones",
    description: "Notas",
    institutional: false,
  },
  {
    slug: "records.own",
    module: "Portal personal",
    label: "Consultar su información",
    description: "Propio",
    institutional: false,
  },
];
const roles = [
  {
    role_id: 1,
    name: "admin",
    role_title: "Administración",
    description: "Todo",
    scope: "institution",
    user_count: 1,
    permission_count: 28,
  },
];

function renderPage() {
  useAuthStore.setState({
    user: {
      user_id: 1,
      username: "demo",
      email: "demo@example.com",
      role_id: 1,
      role_name: "admin",
      student_id: null,
      teacher_id: null,
    },
  });
  vi.spyOn(api, "get").mockImplementation(
    async path =>
      ({
        data:
          path === "/roles/"
            ? roles
            : path === "/access/permissions"
              ? catalog
              : path === "/access/scopes"
                ? [
                    { value: "institution", label: "Toda la institución" },
                    { value: "sections", label: "Sus secciones" },
                    { value: "own", label: "Su propio expediente" },
                  ]
                : { permissions: [] },
      }) as never,
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RolesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it("derives role codes and pairs manage with view permissions", () => {
  expect(roleCode("Coordinación académica")).toBe("coordinacion_academica");
  expect(togglePermission([], "finance.manage", true).sort()).toEqual([
    "finance.manage",
    "finance.view",
  ]);
  expect(togglePermission(["finance.manage", "finance.view"], "finance.view", false)).toEqual([]);
});

it("only offers permissions that fit the chosen scope", () => {
  const [view, , grades, own] = catalog;
  expect(fitsScope(view, "institution")).toBe(true);
  expect(fitsScope(view, "sections")).toBe(false);
  expect(fitsScope(grades, "sections")).toBe(true);
  expect(fitsScope(own, "institution")).toBe(false);
  expect(fitsScope(own, "own")).toBe(true);
});

it("creates a role and then saves its permissions", async () => {
  const post = vi
    .spyOn(api, "post")
    .mockResolvedValue({ data: { ...roles[0], role_id: 7, name: "caja" } } as never);
  const put = vi.spyOn(api, "put").mockResolvedValue({ data: {} } as never);
  renderPage();
  expect(await screen.findByText("Administración")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Nuevo rol" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Nombre del rol"), { target: { value: "Caja" } });
  fireEvent.change(within(dialog).getByLabelText("Descripción"), {
    target: { value: "Cobros y pagos" },
  });
  fireEvent.click(within(dialog).getByRole("switch", { name: /Gestionar finanzas/ }));
  expect(within(dialog).getByRole("switch", { name: /Consultar finanzas/ })).toBeChecked();
  expect(within(dialog).getByRole("switch", { name: /Consultar su información/ })).toBeDisabled();
  fireEvent.click(within(dialog).getByRole("button", { name: "Crear rol" }));
  await waitFor(() =>
    expect(put).toHaveBeenCalledWith(
      "/access/roles/7/permissions",
      expect.objectContaining({ permissions: ["finance.manage", "finance.view"] }),
    ),
  );
  expect(post).toHaveBeenCalledWith(
    "/roles/",
    expect.objectContaining({ name: "caja", label: "Caja", scope: "institution" }),
  );
});
