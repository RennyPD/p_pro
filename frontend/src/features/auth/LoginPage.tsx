import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Eye, EyeOff, GraduationCap, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate } from "react-router-dom";
import { z } from "zod";
import { Button } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import type { ApiSchema } from "../../lib/apiTypes";
import type { TokenResponse } from "../../types";

type PublicInstitution = ApiSchema<"PublicInstitution">;
export const SUSPENDED_NOTICE =
  "Esta institución está suspendida. Contacta a su administración o al soporte de Nexo.";

const schema = z.object({
  username: z.string().min(1, "Escribe tu usuario o correo"),
  password: z.string().min(8, "La contraseña debe tener al menos 8 caracteres"),
  otp: z
    .string()
    .regex(/^\d{6}$/, "Usa 6 dígitos")
    .or(z.literal(""))
    .optional(),
  // Institution code: asked only when the username exists in several (Fase 4 A).
  institution: z.string().max(60).optional(),
});
type FormValues = z.infer<typeof schema>;
export function LoginPage() {
  const { token, setSession } = useAuthStore();
  const [show, setShow] = useState(false);
  const [serverError, setServerError] = useState("");
  const [askInstitution, setAskInstitution] = useState(false);
  // On an institution's own address (subdomain) the server already knows which one it is.
  const addressed = useQuery({
    queryKey: ["public-institution"],
    queryFn: () => api.get<PublicInstitution>("/public/institution").then(r => r.data),
    retry: false,
    staleTime: Infinity,
  });
  const institution = addressed.data;
  const signup = useQuery({
    queryKey: ["public-signup"],
    queryFn: () => api.get<{ enabled: boolean }>("/public/signup").then(r => r.data),
    retry: false,
    staleTime: Infinity,
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });
  if (token) return <Navigate to="/" replace />;
  async function submit(values: FormValues) {
    setServerError("");
    try {
      const { data } = await api.post<TokenResponse>("/auth/login", {
        ...values,
        otp: values.otp || undefined,
        institution: institution ? undefined : values.institution?.trim() || undefined,
      });
      setSession(data.access_token, data.user);
    } catch (error) {
      const status = (error as { response?: { status?: number } }).response?.status;
      if (status === 409 && !institution) setAskInstitution(true);
      setServerError(apiMessage(error));
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="brand-lockup">
          <span className="brand-symbol">
            <GraduationCap />
          </span>
          <strong>Nexo</strong>
        </div>
        <div className="auth-story__copy">
          <span className="kicker kicker--light">
            <Sparkles size={14} /> Gestión académica sin fricción
          </span>
          <h1>Todo el pulso de tu comunidad educativa.</h1>
          <p>
            Un espacio claro para coordinar estudiantes, docentes, horarios, notas y asistencia sin
            perder tiempo entre pantallas.
          </p>
          <div className="trust-line">
            <ShieldCheck />
            <span>Acceso protegido según tu rol y contexto académico.</span>
          </div>
        </div>
        <div className="orbit orbit--one" />
        <div className="orbit orbit--two" />
      </section>
      <section className="auth-form-wrap">
        <form className="auth-card" onSubmit={handleSubmit(submit)}>
          <div>
            <span className="kicker">{institution?.name ?? "Portal académico"}</span>
            <h2>Qué bueno verte</h2>
            <p>Usa tus credenciales institucionales para continuar.</p>
          </div>
          {institution?.status === "suspended" && (
            <div className="form-error" role="alert">
              {SUSPENDED_NOTICE}
            </div>
          )}
          <label className="form-field">
            <span>Usuario o correo</span>
            <input
              autoFocus
              autoComplete="username"
              placeholder="nombre@institución.edu"
              {...register("username")}
            />
            {errors.username && <small>{errors.username.message}</small>}
          </label>
          <label className="form-field">
            <span>Contraseña</span>
            <div className="password-field">
              <input
                type={show ? "text" : "password"}
                autoComplete="current-password"
                placeholder="••••••••"
                {...register("password")}
              />
              <button
                type="button"
                onClick={() => setShow(!show)}
                aria-label={show ? "Ocultar contraseña" : "Mostrar contraseña"}
              >
                {show ? <EyeOff /> : <Eye />}
              </button>
            </div>
            {errors.password && <small>{errors.password.message}</small>}
          </label>
          <label className="form-field">
            <span>Código de verificación (si está activado)</span>
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="000000"
              {...register("otp")}
            />
            {errors.otp && <small>{errors.otp.message}</small>}
          </label>
          {askInstitution && !institution && (
            <label className="form-field">
              <span>Código de tu institución</span>
              <input
                autoComplete="organization"
                placeholder="Ej. colegio-horizonte"
                {...register("institution")}
              />
            </label>
          )}
          {serverError && (
            <div className="form-error" role="alert">
              {serverError}
            </div>
          )}
          <Button disabled={isSubmitting} className="auth-submit">
            {isSubmitting ? "Verificando…" : "Entrar a Nexo"}
          </Button>
          <p className="auth-help">
            <Link to="/recuperar">¿Olvidaste tu contraseña?</Link>
          </p>
          {signup.data?.enabled && !institution && (
            <p className="auth-help">
              ¿Tu institución aún no usa Nexo? <Link to="/registro">Crea una cuenta gratis</Link>
            </p>
          )}
        </form>
      </section>
    </main>
  );
}
