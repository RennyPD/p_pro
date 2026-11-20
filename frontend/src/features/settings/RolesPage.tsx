import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, Pencil, Plus, ShieldCheck, Trash2, Users } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { confirmAction } from "../../lib/confirm";
import { formatDateTime } from "../../lib/format";
import { useAuthStore } from "../../store/auth";
import {
  fitsScope,
  roleCode,
  scopeShort,
  scopeTone,
  SYSTEM_ROLES,
  togglePermission,
  type Change,
  type PermissionDef,
  type RoleRow,
  type ScopeOption,
} from "./roleRules";
import "./roles.css";

export function RolesPage() {
  const uid = useAuthStore(state => state.user?.user_id);
  const client = useQueryClient();
  const [editing, setEditing] = useState<RoleRow | "new">();
  const [historyOf, setHistoryOf] = useState<RoleRow>();
  const roles = useQuery({
    queryKey: ["access-roles", uid],
    queryFn: () => api.get<RoleRow[]>("/roles/", { params: { limit: 100 } }).then(r => r.data),
  });
  const catalog = useQuery({
    queryKey: ["access-catalog", uid],
    queryFn: () => api.get<PermissionDef[]>("/access/permissions").then(r => r.data),
  });
  const scopes = useQuery({
    queryKey: ["access-scopes", uid],
    queryFn: () => api.get<ScopeOption[]>("/access/scopes").then(r => r.data),
  });
  const remove = useMutation({
    mutationFn: (role: RoleRow) => api.delete(`/roles/${role.role_id}`),
    onSuccess: () => {
      toast.success("Rol eliminado");
      void client.invalidateQueries({ queryKey: ["access-roles"] });
    },
    onError: error => toast.error(apiMessage(error)),
  });

  if (roles.isPending || catalog.isPending || scopes.isPending)
    return (
      <div className="page">
        <Spinner label="Cargando roles" />
      </div>
    );
  const error = roles.error || catalog.error || scopes.error;
  if (error)
    return (
      <div className="page">
        <EmptyState
          icon={<ShieldCheck />}
          title="No pudimos cargar los roles"
          description={apiMessage(error)}
        />
      </div>
    );

  return (
    <div className="page roles-page">
      <header className="page-header">
        <div>
          <span className="kicker">Configuración · Seguridad</span>
          <h1>Roles y permisos</h1>
          <p>
            Cada función del sistema se habilita con un permiso. Crea roles a la medida de cada
            puesto y define sobre qué registros actúan.
          </p>
        </div>
        <Button onClick={() => setEditing("new")}>
          <Plus size={18} />
          Nuevo rol
        </Button>
      </header>
      <section className="role-grid" aria-label="Roles">
        {roles.data?.map(role => {
          const system = SYSTEM_ROLES.includes(role.name);
          return (
            <article className="role-card" key={role.role_id}>
              <header>
                <div>
                  <h2>{role.role_title}</h2>
                  <small>{system ? "Rol del sistema" : "Rol personalizado"}</small>
                </div>
                <Badge tone={scopeTone[role.scope] ?? "neutral"}>
                  {scopeShort[role.scope] ?? role.scope}
                </Badge>
              </header>
              <p>{role.description}</p>
              <dl>
                <div>
                  <dt>Permisos</dt>
                  <dd>{role.permission_count}</dd>
                </div>
                <div>
                  <dt>
                    <Users size={14} aria-hidden="true" /> Cuentas
                  </dt>
                  <dd>{role.user_count}</dd>
                </div>
              </dl>
              <footer>
                <Button variant="secondary" onClick={() => setEditing(role)}>
                  <Pencil size={16} />
                  Editar
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setHistoryOf(role)}
                  aria-label={`Historial de ${role.role_title}`}
                  title="Historial de cambios"
                >
                  <History size={16} />
                </Button>
                {!system && role.user_count === 0 && (
                  <Button
                    variant="ghost"
                    disabled={remove.isPending}
                    aria-label={`Eliminar ${role.role_title}`}
                    title="Eliminar rol"
                    onClick={async () => {
                      if (
                        await confirmAction(`¿Eliminar el rol «${role.role_title}»?`, {
                          tone: "danger",
                        })
                      )
                        remove.mutate(role);
                    }}
                  >
                    <Trash2 size={16} />
                  </Button>
                )}
              </footer>
            </article>
          );
        })}
      </section>
      {editing && (
        <RoleEditor
          role={editing === "new" ? undefined : editing}
          roles={roles.data ?? []}
          catalog={catalog.data ?? []}
          scopes={scopes.data ?? []}
          onClose={() => setEditing(undefined)}
        />
      )}
      {historyOf && <RoleHistory role={historyOf} onClose={() => setHistoryOf(undefined)} />}
    </div>
  );
}

function useRolePermissions(roleId?: number) {
  const uid = useAuthStore(state => state.user?.user_id);
  return useQuery({
    queryKey: ["role-permissions", uid, roleId],
    queryFn: () =>
      api
        .get<{ permissions: string[] }>(`/access/roles/${roleId}/permissions`)
        .then(r => r.data.permissions),
    enabled: Boolean(roleId),
  });
}

export function RoleEditor({
  role,
  roles,
  catalog,
  scopes,
  onClose,
}: {
  role?: RoleRow;
  roles: RoleRow[];
  catalog: PermissionDef[];
  scopes: ScopeOption[];
  onClose: () => void;
}) {
  const client = useQueryClient();
  const uid = useAuthStore(state => state.user?.user_id);
  const creating = !role;
  const system = role ? SYSTEM_ROLES.includes(role.name) : false;
  const [label, setLabel] = useState(role?.role_title ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [scope, setScope] = useState(role?.scope ?? "institution");
  const [copyFrom, setCopyFrom] = useState(0);
  const [draft, setDraft] = useState<string[]>();
  const [reason, setReason] = useState(creating ? "Permisos iniciales del rol" : "");
  const current = useRolePermissions(role?.role_id);
  const before = useMemo(() => current.data ?? [], [current.data]);
  const selected = draft ?? before;
  const usable = selected.filter(slug => {
    const permission = catalog.find(item => item.slug === slug);
    return permission ? fitsScope(permission, scope) : false;
  });
  const modules = useMemo(() => {
    const groups = new Map<string, PermissionDef[]>();
    for (const item of catalog) groups.set(item.module, [...(groups.get(item.module) ?? []), item]);
    return [...groups];
  }, [catalog]);
  const added = usable.filter(slug => !before.includes(slug));
  const removed = before.filter(slug => !usable.includes(slug));
  const titleOf = (slug: string) => catalog.find(item => item.slug === slug)?.label ?? slug;

  const save = useMutation({
    mutationFn: async () => {
      let roleId = role?.role_id;
      if (creating) {
        const created = await api.post<RoleRow>("/roles/", {
          name: roleCode(label),
          label: label.trim(),
          description: description.trim(),
          scope,
        });
        roleId = created.data.role_id;
      } else if (
        label.trim() !== role.role_title ||
        description.trim() !== role.description ||
        scope !== role.scope
      ) {
        await api.patch(`/roles/${roleId}`, {
          label: label.trim(),
          description: description.trim(),
          ...(scope !== role.scope ? { scope } : {}),
        });
      }
      if (creating || added.length || removed.length)
        await api.put(`/access/roles/${roleId}/permissions`, {
          permissions: usable,
          expected_permissions: creating ? undefined : before,
          reason: reason.trim(),
        });
    },
    onSuccess: async () => {
      toast.success(creating ? "Rol creado" : "Rol actualizado");
      await client.invalidateQueries({ queryKey: ["access-roles"] });
      void client.invalidateQueries({ queryKey: ["role-permissions"] });
      void client.invalidateQueries({ queryKey: ["my-permissions"] });
      void client.invalidateQueries({ queryKey: ["access-history"] });
      onClose();
    },
    onError: error => {
      toast.error(apiMessage(error));
      // A role created before the permissions failed must not be created twice.
      void client.invalidateQueries({ queryKey: ["access-roles"] });
    },
  });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (creating && !roleCode(label)) {
      toast.error("Escribe un nombre con letras o números");
      return;
    }
    if (
      !creating &&
      (added.length || removed.length) &&
      role.user_count > 0 &&
      !(await confirmAction(
        `Los cambios se aplicarán a las ${role.user_count} cuentas con este rol. ¿Continuar?`,
      ))
    )
      return;
    save.mutate();
  }

  const permissionsChanged = creating || added.length > 0 || removed.length > 0;
  return (
    <Modal
      title={creating ? "Nuevo rol" : `Editar «${role.role_title}»`}
      description="Elige sobre qué registros trabaja el rol y activa los permisos de su función."
      onClose={onClose}
    >
      <form className="role-editor" onSubmit={submit}>
        <div className="role-editor__identity">
          <label className="form-field">
            <span>Nombre del rol</span>
            <input
              required
              maxLength={100}
              value={label}
              placeholder="Ej. Caja, Coordinación académica"
              onChange={event => setLabel(event.target.value)}
            />
          </label>
          <label className="form-field">
            <span>Descripción</span>
            <input
              required
              maxLength={250}
              value={description}
              placeholder="Qué hace este puesto"
              onChange={event => setDescription(event.target.value)}
            />
          </label>
          <label className="form-field">
            <span>Ámbito de datos</span>
            <select
              value={scope}
              disabled={system}
              onChange={event => setScope(event.target.value)}
            >
              {scopes.map(item => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          {creating && (
            <label className="form-field">
              <span>Partir de un rol existente</span>
              <select
                value={copyFrom}
                onChange={async event => {
                  const id = Number(event.target.value);
                  setCopyFrom(id);
                  const source = roles.find(item => item.role_id === id);
                  if (!source) return setDraft([]);
                  setScope(source.scope);
                  try {
                    setDraft(
                      await client.fetchQuery({
                        queryKey: ["role-permissions", uid, id],
                        queryFn: () =>
                          api
                            .get<{ permissions: string[] }>(`/access/roles/${id}/permissions`)
                            .then(r => r.data.permissions),
                      }),
                    );
                  } catch (error) {
                    toast.error(apiMessage(error));
                  }
                }}
              >
                <option value={0}>Empezar desde cero</option>
                {roles.map(item => (
                  <option key={item.role_id} value={item.role_id}>
                    {item.role_title}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {current.isFetching ? (
          <Spinner label="Cargando permisos del rol" />
        ) : current.error ? (
          <p className="form-error">{apiMessage(current.error)}</p>
        ) : (
          <div className="permission-modules">
            {modules.map(([module, items]) => {
              const available = items.filter(item => fitsScope(item, scope));
              const allOn =
                available.length > 0 && available.every(item => usable.includes(item.slug));
              return (
                <fieldset key={module} className="permission-module">
                  <legend>
                    <span>{module}</span>
                    {available.length > 1 && (
                      <button
                        type="button"
                        className="button button--ghost permission-module__all"
                        onClick={() =>
                          setDraft(
                            allOn
                              ? selected.filter(slug => !items.some(item => item.slug === slug))
                              : [...new Set([...selected, ...available.map(item => item.slug)])],
                          )
                        }
                      >
                        {allOn ? "Quitar todos" : "Todos"}
                      </button>
                    )}
                  </legend>
                  {items.map(item => {
                    const allowed = fitsScope(item, scope);
                    return (
                      <label
                        key={item.slug}
                        className={allowed ? "permission-toggle" : "permission-toggle is-blocked"}
                        title={
                          allowed
                            ? item.slug
                            : "No disponible con el ámbito elegido. Requiere otro ámbito de datos."
                        }
                      >
                        <input
                          type="checkbox"
                          role="switch"
                          disabled={!allowed || save.isPending}
                          checked={allowed && usable.includes(item.slug)}
                          onChange={event =>
                            setDraft(togglePermission(selected, item.slug, event.target.checked))
                          }
                        />
                        <span>
                          <strong>{item.label}</strong>
                          <small>{item.description}</small>
                        </span>
                      </label>
                    );
                  })}
                </fieldset>
              );
            })}
          </div>
        )}
        {!creating && (added.length > 0 || removed.length > 0) && (
          <aside className="role-editor__summary" aria-live="polite">
            {added.length > 0 && <p>Se conceden: {added.map(titleOf).join(", ")}</p>}
            {removed.length > 0 && <p>Se retiran: {removed.map(titleOf).join(", ")}</p>}
          </aside>
        )}
        {permissionsChanged && (
          <label className="form-field">
            <span>Motivo (queda en la auditoría)</span>
            <input
              required
              minLength={3}
              maxLength={250}
              value={reason}
              onChange={event => setReason(event.target.value)}
            />
          </label>
        )}
        <div className="form-actions">
          <span className="muted">{usable.length} permisos activos</span>
          <Button type="button" variant="secondary" onClick={onClose} disabled={save.isPending}>
            Cancelar
          </Button>
          <Button disabled={save.isPending}>{creating ? "Crear rol" : "Guardar cambios"}</Button>
        </div>
      </form>
    </Modal>
  );
}

function RoleHistory({ role, onClose }: { role: RoleRow; onClose: () => void }) {
  const uid = useAuthStore(state => state.user?.user_id);
  const history = useQuery({
    queryKey: ["access-history", uid, role.role_id],
    queryFn: () => api.get<Change[]>(`/access/roles/${role.role_id}/history`).then(r => r.data),
  });
  return (
    <Modal title={`Historial de «${role.role_title}»`} onClose={onClose}>
      {history.isPending ? (
        <Spinner />
      ) : history.error ? (
        <p className="form-error">{apiMessage(history.error)}</p>
      ) : history.data.length ? (
        <ol className="role-history">
          {history.data.map(item => (
            <li key={item.id}>
              <strong>
                {item.actor} · {formatDateTime(item.created_at)}
              </strong>
              <p>{item.detail}</p>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">Este rol todavía no tiene cambios de permisos registrados.</p>
      )}
    </Modal>
  );
}
