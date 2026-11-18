import { KeyRound } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { LookupSelect } from "../../components/LookupSelect";
import { Button, Modal } from "../../components/ui";
import { resources } from "../../config/resources";
import { api, apiMessage } from "../../lib/api";
import { isCustomRole, type ModuleView } from "../../lib/moduleViews";
import { useDraftGuard } from "../../lib/useDraftGuard";
import type { EntityRecord, LookupConfig, ResourceConfig } from "../../types";
import { ResourcePage } from "../resources/ResourcePage";

const roleNames: Record<string, string> = {
  admin: "Administración",
  teacher: "Docencia",
  student: "Estudiante",
  guardian: "Tutoría",
};
const roleLookup: LookupConfig = {
  endpoint: "/roles/",
  valueKey: "role_id",
  labelKeys: ["role_title"],
  placeholder: "Buscar rol",
};
const profiles = {
  student: {
    label: "Estudiante",
    field: "student_id",
    lookup: resources.users.fields.find(field => field.name === "student_id")!.lookup!,
  },
  teacher: {
    label: "Docente",
    field: "teacher_id",
    lookup: resources.users.fields.find(field => field.name === "teacher_id")!.lookup!,
  },
  guardian: {
    label: "Tutor",
    field: "guardian_id",
    lookup: {
      endpoint: "/community/guardians",
      valueKey: "guardian_id",
      labelKeys: ["first_name", "last_name"],
      secondaryKey: "email",
      placeholder: "Buscar tutor",
    },
  },
};
const config: ResourceConfig = {
  ...resources.users,
  description: "Administra cuentas, roles y vínculos de estudiantes, docentes y tutores.",
  columns: [
    { key: "username", label: "Usuario" },
    { key: "email", label: "Correo" },
    {
      key: "role_label",
      label: "Rol",
      render: (label, row) => label || roleNames[String(row.role_name)] || row.role_name,
    },
    { key: "linked_person", label: "Persona vinculada", render: value => value || "Sin vínculo" },
  ],
};

export function UsersPage() {
  const [reset, setReset] = useState<EntityRecord | null>(null);
  const [account, setAccount] = useState<EntityRecord | null>(null);
  return (
    <>
      <ResourcePage
        config={config}
        renderEditor={(record, onClose) => <UserEditor record={record} onClose={onClose} />}
        rowActions={row => (
          <>
            <button
              type="button"
              onClick={() => setReset(row)}
              aria-label={`Restablecer contraseña de ${row.username}`}
              title="Restablecer contraseña"
            >
              <KeyRound />
            </button>
            {isCustomRole(String(row.role_name ?? "")) && (
              <button type="button" onClick={() => setAccount(row)}>
                Módulos
              </button>
            )}
          </>
        )}
      />
      {reset && <UserEditor record={reset} passwordReset onClose={() => setReset(null)} />}
      {account && <ModuleEditor account={account} onClose={() => setAccount(null)} />}
    </>
  );
}

function ModuleEditor({ account, onClose }: { account: EntityRecord; onClose: () => void }) {
  const client = useQueryClient();
  const endpoint = `/module-views/accounts/${account.user_id}`;
  const config = useQuery({
    queryKey: ["module-views", "account", account.user_id],
    queryFn: () => api.get<{ available: ModuleView[]; selected: string[] }>(endpoint).then(response => response.data),
  });
  const [draft, setDraft] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selected = draft ?? config.data?.selected ?? [];
  useDraftGuard(draft !== null, busy);

  function close() {
    if (!busy && (!draft || window.confirm("¿Descartar los cambios de módulos?"))) onClose();
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.put(endpoint, { modules: selected });
      await client.invalidateQueries({ queryKey: ["module-views"] });
      toast.success("Módulos guardados");
      onClose();
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`Módulos de ${account.username}`} onClose={close}>
      {config.isPending ? (
        <p>Cargando módulos…</p>
      ) : config.isError ? (
        <p role="alert">
          {apiMessage(config.error)} <Button onClick={() => void config.refetch()}>Reintentar</Button>
        </p>
      ) : (
        <form className="resource-form" onSubmit={save}>
          <p>Selecciona los módulos de consulta institucional para esta cuenta.</p>
          {config.data.available.map(item => (
            <label key={item.key}>
              <input
                type="checkbox"
                disabled={busy}
                checked={selected.includes(item.key)}
                onChange={event =>
                  setDraft(event.target.checked ? [...selected, item.key] : selected.filter(key => key !== item.key))
                }
              />{" "}
              {item.label}
            </label>
          ))}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <Button type="button" variant="secondary" disabled={busy} onClick={close}>
              Cancelar
            </Button>
            <Button disabled={busy || !draft}>{busy ? "Guardando…" : "Guardar módulos"}</Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function UserEditor({
  record,
  onClose,
  passwordReset = false,
}: {
  record: EntityRecord | null;
  onClose: () => void;
  passwordReset?: boolean;
}) {
  const roleLabel = useId();
  const personLabel = useId();
  const client = useQueryClient();
  const [username, setUsername] = useState(String(record?.username ?? ""));
  const [email, setEmail] = useState(String(record?.email ?? ""));
  const [password, setPassword] = useState("");
  const [role, setRole] = useState(Number(record?.role_id ?? 0));
  const [person, setPerson] = useState(Number(record?.student_id ?? record?.teacher_id ?? record?.guardian_id ?? 0));
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedRole = useQuery({
    queryKey: ["account-role", role],
    queryFn: () => api.get<{ name: string }>(`/roles/${role}`).then(response => response.data),
    enabled: Boolean(role) && !passwordReset,
  });
  const roleCode = selectedRole.data?.name?.toLowerCase() ?? "";
  const profile = profiles[roleCode as keyof typeof profiles];
  const takesPassword = passwordReset || !record;
  useDraftGuard(touched, busy);

  function close() {
    if (!busy && (!touched || window.confirm("¿Descartar los cambios de esta cuenta?"))) onClose();
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!passwordReset && (!role || !selectedRole.data)) {
      setError("Selecciona un rol válido para esta cuenta.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (passwordReset) {
        await api.post(`/users/${record?.user_id}/password`, { password });
      } else {
        const links = {
          student_id: null,
          teacher_id: null,
          guardian_id: null,
          ...(profile && { [profile.field]: person || null }),
        };
        const payload = { username: username.trim(), email: email.trim(), role_id: role, ...links };
        if (record) await api.patch(`/users/${record.user_id}`, payload);
        else await api.post("/users/", { ...payload, password });
      }
      await client.invalidateQueries({ queryKey: ["users"] });
      toast.success(passwordReset ? "Contraseña restablecida y sesiones revocadas" : "Cuenta guardada");
      onClose();
    } catch (failure) {
      setError(`${username.trim() || "Cuenta nueva"}. ${apiMessage(failure)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={passwordReset ? "Restablecer contraseña" : record ? "Editar usuario" : "Nuevo usuario"}
      onClose={close}
    >
      <form className="resource-form" onSubmit={save} onChange={() => setTouched(true)}>
        {passwordReset ? (
          <p>
            Se cerrarán las sesiones de <strong>{username}</strong>.
          </p>
        ) : (
          <>
            <label className="form-field">
              <span>Usuario</span>
              <input
                required
                maxLength={50}
                autoComplete="off"
                value={username}
                onChange={event => setUsername(event.target.value)}
              />
            </label>
            <label className="form-field">
              <span>Correo</span>
              <input
                type="email"
                required
                maxLength={255}
                value={email}
                onChange={event => setEmail(event.target.value)}
              />
            </label>
            <div className="form-field">
              <span id={roleLabel}>Rol</span>
              <LookupSelect
                config={roleLookup}
                labelId={roleLabel}
                required
                value={role || null}
                onChange={value => {
                  if (Number(value) !== role) setPerson(0);
                  setRole(Number(value));
                  setTouched(true);
                }}
              />
            </div>
            {role > 0 && selectedRole.isError && (
              <p role="alert">
                No se pudo verificar el rol.{" "}
                <button type="button" onClick={() => void selectedRole.refetch()}>
                  Reintentar
                </button>
              </p>
            )}
            {profile && (
              <div className="form-field">
                <span id={personLabel}>{profile.label} vinculado</span>
                <LookupSelect
                  config={profile.lookup}
                  labelId={personLabel}
                  value={person || null}
                  onChange={value => {
                    setPerson(Number(value));
                    setTouched(true);
                  }}
                />
              </div>
            )}
          </>
        )}
        {takesPassword && (
          <label className="form-field">
            <span>{passwordReset ? "Nueva contraseña" : "Contraseña inicial"}</span>
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={passwordReset ? 10 : 8}
              value={password}
              onChange={event => setPassword(event.target.value)}
            />
          </label>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <Button type="button" variant="secondary" disabled={busy} onClick={close}>
            Cancelar
          </Button>
          <Button disabled={busy}>
            {busy ? "Guardando…" : passwordReset ? "Restablecer contraseña" : "Guardar cuenta"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
