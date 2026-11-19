import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";

const schema = z
  .object({
    current_password: z.string().min(8, "Escribe tu contraseña actual"),
    new_password: z.string().min(10, "Usa al menos 10 caracteres"),
    confirm: z.string(),
  })
  .refine(values => values.new_password === values.confirm, {
    path: ["confirm"],
    message: "Las contraseñas no coinciden",
  });
type Values = z.infer<typeof schema>;
type Session = { session_id: number; created_at: string; active: boolean };
const sixDigits = /^\d{6}$/;
const localDate = new Intl.DateTimeFormat("es-DO", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Santo_Domingo",
});

export function AccountPage() {
  const { user, clearSession } = useAuthStore();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"enroll" | "disable" | null>(null);
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [currentCode, setCurrentCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [securityError, setSecurityError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
  });
  const sessions = useQuery({
    queryKey: ["account-sessions", user?.user_id],
    queryFn: () => api.get<Session[]>("/auth/sessions").then(response => response.data),
  });
  const enabled = Boolean(user?.mfa_enabled);
  const activeSessions = sessions.data?.filter(session => session.active) ?? [];

  function endSession(message: string) {
    toast.success(`${message} Inicia sesión de nuevo.`);
    queryClient.clear();
    clearSession();
  }

  function resetMfaForm() {
    setMode(null);
    setSecret("");
    setPassword("");
    setCurrentCode("");
    setCode("");
  }

  async function runSecurity(action: () => Promise<void>) {
    setSecurityError("");
    setBusy(true);
    try {
      await action();
    } catch (error) {
      setSecurityError(apiMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function changePassword({ confirm: _, ...values }: Values) {
    setPasswordError("");
    try {
      await api.post("/auth/change-password", values);
      endSession("Contraseña actualizada.");
    } catch (error) {
      setPasswordError(apiMessage(error));
    }
  }

  function submitMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runSecurity(async () => {
      if (mode === "disable") {
        await api.post("/auth/mfa/disable", { code, current_password: password });
        endSession("Verificación en dos pasos desactivada.");
        return;
      }
      await api.post("/auth/mfa/enable", {
        code,
        current_password: password,
        current_code: enabled ? currentCode : undefined,
      });
      endSession("Verificación en dos pasos configurada.");
    });
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Mi seguridad</h1>
      </header>
      <div className="settings-grid">
        <section className="account-card">
          <span className="account-icon">
            <KeyRound />
          </span>
          <form onSubmit={handleSubmit(changePassword)}>
            <h2>Cambiar contraseña</h2>
            <p>Al actualizarla, se cerrarán todas tus sesiones.</p>
            <label className="form-field">
              <span>Contraseña actual</span>
              <input
                type="password"
                autoComplete="current-password"
                {...register("current_password")}
              />
              {errors.current_password && <small>{errors.current_password.message}</small>}
            </label>
            <label className="form-field">
              <span>Nueva contraseña</span>
              <input type="password" autoComplete="new-password" {...register("new_password")} />
              {errors.new_password && <small>{errors.new_password.message}</small>}
            </label>
            <label className="form-field">
              <span>Confirmar contraseña</span>
              <input type="password" autoComplete="new-password" {...register("confirm")} />
              {errors.confirm && <small>{errors.confirm.message}</small>}
            </label>
            {passwordError && (
              <p role="alert" className="form-error">
                {passwordError}
              </p>
            )}
            <Button disabled={isSubmitting}>
              {isSubmitting ? "Actualizando…" : "Actualizar contraseña"}
            </Button>
          </form>
        </section>
        <section className="account-card">
          <span className="account-icon">
            <ShieldCheck />
          </span>
          <div>
            <h2>Verificación en dos pasos</h2>
            <p>Estado: {enabled ? "activada" : "desactivada"}</p>
            {!mode ? (
              <>
                <Button
                  disabled={busy}
                  onClick={() =>
                    void runSecurity(async () => {
                      const { data } = await api.post<{ secret: string }>("/auth/mfa/setup");
                      setSecret(data.secret);
                      setMode("enroll");
                    })
                  }
                >
                  {enabled ? "Cambiar autenticador" : "Configurar autenticador"}
                </Button>
                {enabled && (
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => {
                      setSecurityError("");
                      setMode("disable");
                    }}
                  >
                    Desactivar
                  </Button>
                )}
              </>
            ) : (
              <form onSubmit={submitMfa}>
                {mode === "enroll" && (
                  <p>
                    Agrega esta clave en tu aplicación autenticadora. Vence en 10 minutos.{" "}
                    <code>{secret}</code>
                  </p>
                )}
                <label className="form-field">
                  <span>Contraseña actual</span>
                  <input
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={event => setPassword(event.target.value)}
                  />
                </label>
                {mode === "enroll" && enabled && (
                  <label className="form-field">
                    <span>Código del autenticador actual</span>
                    <input
                      inputMode="numeric"
                      maxLength={6}
                      autoComplete="one-time-code"
                      value={currentCode}
                      onChange={event => setCurrentCode(event.target.value)}
                    />
                  </label>
                )}
                <label className="form-field">
                  <span>
                    {mode === "disable"
                      ? "Código del autenticador actual"
                      : "Código del nuevo autenticador"}
                  </span>
                  <input
                    inputMode="numeric"
                    maxLength={6}
                    value={code}
                    onChange={event => setCode(event.target.value)}
                  />
                </label>
                <Button
                  disabled={
                    busy ||
                    password.length < 8 ||
                    !sixDigits.test(code) ||
                    (mode === "enroll" && enabled && !sixDigits.test(currentCode))
                  }
                >
                  {mode === "disable" ? "Confirmar desactivación" : "Guardar autenticador"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void runSecurity(async () => {
                      if (mode === "enroll") await api.delete("/auth/mfa/setup");
                      resetMfaForm();
                    })
                  }
                >
                  Cancelar
                </Button>
              </form>
            )}
            {securityError && (
              <p role="alert" className="form-error">
                {securityError}
              </p>
            )}
            <h2 className="account-subheading">Sesiones activas</h2>
            {sessions.isPending ? (
              <p>Cargando sesiones…</p>
            ) : sessions.isError ? (
              <p role="alert">
                No se pudieron consultar tus sesiones.{" "}
                <button type="button" onClick={() => void sessions.refetch()}>
                  Reintentar
                </button>
              </p>
            ) : activeSessions.length ? (
              <ul className="session-list">
                {activeSessions.map((session, index) => (
                  <li key={session.session_id}>
                    <span>{index === 0 ? "Sesión más reciente" : `Sesión ${index + 1}`}</span>
                    <small>Iniciada el {localDate.format(new Date(session.created_at))}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No hay sesiones renovables.</p>
            )}
            <p className="muted">Cerrar todas también cierra la sesión que estás usando.</p>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() =>
                void runSecurity(async () => {
                  await api.post("/auth/sessions/revoke-all");
                  endSession("Sesiones cerradas.");
                })
              }
            >
              Cerrar todas las sesiones
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
}
