import { KeyRound, Mail, UserCheck, UserX } from "lucide-react";
import { confirmAction } from "../../lib/confirm";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { LookupSelect } from "../../components/LookupSelect";
import { Badge, Button, Modal } from "../../components/ui";
import { resources } from "../../config/resources";
import { api, apiMessage } from "../../lib/api";
import { useDraftGuard } from "../../lib/useDraftGuard";
import type { EntityRecord, LookupConfig, ResourceConfig } from "../../types";
import { ResourcePage } from "../resources/ResourcePage";
import "./users.css";

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
    {
      key: "active",
      label: "Estado",
      render: value =>
        value === false ? (
          <Badge tone="danger">Desactivada</Badge>
        ) : (
          <Badge tone="success">Activa</Badge>
        ),
    },
  ],
};

export function UsersPage() {
  const [reset, setReset] = useState<EntityRecord | null>(null);
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
            <InvitationButton account={row} />
            <AccountStatusButton account={row} />
          </>
        )}
      />
      {reset && <UserEditor record={reset} passwordReset onClose={() => setReset(null)} />}
    </>
  );
}

function InvitationButton({ account }: { account: EntityRecord }) {
  const [busy, setBusy] = useState(false);
  const username = String(account.username);

  async function resend() {
    const question = `¿Enviar a ${username} un nuevo enlace para elegir su contraseña? Los enlaces anteriores dejarán de funcionar.`;
    if (busy || !(await confirmAction(question))) return;
    setBusy(true);
    try {
      const response = await api.post<{ message: string }>(`/users/${account.user_id}/invitation`);
      toast.success(response.data.message);
    } catch (error) {
      toast.error(apiMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => void resend()}
      aria-label={`Reenviar invitación a ${username}`}
      title="Reenviar invitación"
    >
      <Mail />
    </button>
  );
}

function AccountStatusButton({ account }: { account: EntityRecord }) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const active = account.active !== false;
  const username = String(account.username);

  async function toggle() {
    const question = active
      ? `¿Desactivar la cuenta de ${username}? Se cerrarán sus sesiones y no podrá entrar.`
      : `¿Reactivar la cuenta de ${username}?`;
    if (busy || !(await confirmAction(question))) return;
    setBusy(true);
    try {
      await api.post(`/users/${account.user_id}/${active ? "deactivate" : "activate"}`);
      toast.success(active ? "Cuenta desactivada y sesiones cerradas" : "Cuenta reactivada");
      await client.invalidateQueries({ queryKey: [config.key] });
    } catch (error) {
      toast.error(apiMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => void toggle()}
      aria-label={`${active ? "Desactivar" : "Reactivar"} la cuenta de ${username}`}
      title={active ? "Desactivar cuenta" : "Reactivar cuenta"}
      className={active ? "danger" : undefined}
    >
      {active ? <UserX /> : <UserCheck />}
    </button>
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
  // New accounts: send an activation link by default instead of typing a password.
  const [invite, setInvite] = useState(!record && !passwordReset);
  const [role, setRole] = useState(Number(record?.role_id ?? 0));
  const [person, setPerson] = useState(
    Number(record?.student_id ?? record?.teacher_id ?? record?.guardian_id ?? 0),
  );
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
  const takesPassword = passwordReset || (!record && !invite);
  useDraftGuard(touched, busy);

  async function close() {
    if (!busy && (!touched || (await confirmAction("¿Descartar los cambios de esta cuenta?"))))
      onClose();
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
        else
          await api.post(
            "/users/",
            invite ? { ...payload, invite: true } : { ...payload, password },
          );
      }
      await client.invalidateQueries({ queryKey: ["users"] });
      toast.success(
        passwordReset
          ? "Contraseña restablecida y sesiones revocadas"
          : !record && invite
            ? `Cuenta creada. Enviamos la invitación a ${email.trim()}`
            : "Cuenta guardada",
      );
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
        {!record && !passwordReset && (
          <label className="form-field users-invite">
            <input
              type="checkbox"
              checked={invite}
              onChange={event => setInvite(event.target.checked)}
            />
            <span>
              <b>Enviar invitación por correo</b>
              <small>La persona recibe un enlace y elige su contraseña (vence en 72 horas)</small>
            </span>
          </label>
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
