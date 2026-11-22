import { KeyRound, MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./password-pages.css";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="password-page">
      <section className="auth-card password-card">{children}</section>
    </main>
  );
}

/** «¿Olvidaste tu contraseña?»: the answer never reveals whether the account exists. */
export function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await api.post<{ message: string }>("/auth/password-reset/request", {
        identifier: identifier.trim(),
      });
      setSent(response.data.message);
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  if (sent)
    return (
      <Shell>
        <MailCheck className="password-icon" aria-hidden="true" />
        <h1>Revisa tu correo</h1>
        <p>{sent}. El enlace vence en 30 minutos.</p>
        <Link className="button button--secondary" to="/login">
          Volver a iniciar sesión
        </Link>
      </Shell>
    );
  return (
    <Shell>
      <KeyRound className="password-icon" aria-hidden="true" />
      <h1>¿Olvidaste tu contraseña?</h1>
      <p>Escribe tu usuario o correo y te enviaremos un enlace para elegir una nueva.</p>
      <form className="password-form" onSubmit={submit}>
        <label className="form-field">
          <span>Usuario o correo</span>
          <input
            required
            autoFocus
            autoComplete="username"
            disabled={busy}
            value={identifier}
            onChange={event => setIdentifier(event.target.value)}
          />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <Button disabled={busy}>{busy ? "Enviando…" : "Enviar enlace"}</Button>
      </form>
      <Link to="/login">Volver a iniciar sesión</Link>
    </Shell>
  );
}

/** Choose a password from a reset link (/restablecer) or an invitation (/activar). */
export function ChoosePasswordPage({ mode }: { mode: "reset" | "activate" }) {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const activate = mode === "activate";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password.length < 10) return setError("Usa al menos 10 caracteres");
    if (password !== repeat) return setError("Las contraseñas no coinciden");
    setBusy(true);
    setError("");
    try {
      await api.post("/auth/password-reset/confirm", { token, new_password: password });
      setDone(true);
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  if (!token)
    return (
      <Shell>
        <h1>Enlace incompleto</h1>
        <p>Abre el enlace completo que recibiste por correo o solicita uno nuevo.</p>
        <Link to="/recuperar">Solicitar un enlace nuevo</Link>
      </Shell>
    );
  if (done)
    return (
      <Shell>
        <MailCheck className="password-icon" aria-hidden="true" />
        <h1>{activate ? "Cuenta activada" : "Contraseña actualizada"}</h1>
        <p>Ya puedes entrar con tu nueva contraseña.</p>
        <Link className="button button--primary" to="/login">
          Iniciar sesión
        </Link>
      </Shell>
    );
  return (
    <Shell>
      <KeyRound className="password-icon" aria-hidden="true" />
      <h1>{activate ? "Activa tu cuenta" : "Elige una contraseña nueva"}</h1>
      <p>Usa al menos 10 caracteres. Al guardarla se cerrarán las sesiones abiertas.</p>
      <form className="password-form" onSubmit={submit}>
        <label className="form-field">
          <span>Contraseña nueva</span>
          <input
            required
            type="password"
            autoComplete="new-password"
            minLength={10}
            disabled={busy}
            value={password}
            onChange={event => setPassword(event.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Repite la contraseña</span>
          <input
            required
            type="password"
            autoComplete="new-password"
            disabled={busy}
            value={repeat}
            onChange={event => setRepeat(event.target.value)}
          />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}{" "}
            {error.includes("venció") && <Link to="/recuperar">Solicitar un enlace nuevo</Link>}
          </p>
        )}
        <Button disabled={busy}>{busy ? "Guardando…" : "Guardar contraseña"}</Button>
      </form>
    </Shell>
  );
}
