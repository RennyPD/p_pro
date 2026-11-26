import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { GraduationCap, MailCheck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { Button, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import "./signup.css";

type Config = ApiSchema<"SignupConfig">;

const schema = z.object({
  name: z.string().trim().min(3, "Escribe el nombre de la institución"),
  code: z
    .string()
    .trim()
    .toLowerCase()
    .regex(/^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$/, "Minúsculas, números y guiones (3 a 40)"),
  institution_type: z.enum(["school", "university", "both"]),
  admin_email: z.string().email("Escribe un correo válido"),
  plan_code: z.string().min(1, "Elige un plan"),
  website: z.string().optional(),
  accept_terms: z.literal(true, {
    error: "Acepta los términos de uso y la política de privacidad",
  }),
});
type Values = z.infer<typeof schema>;

/** Public self sign-up (Fase 4 D4): the institution starts after its email is verified. */
export function SignupPage() {
  const [sent, setSent] = useState<string | null>(null);
  const [serverError, setServerError] = useState("");
  const [codeNote, setCodeNote] = useState<string | null>(null);
  const config = useQuery({
    queryKey: ["public-signup"],
    queryFn: () => api.get<Config>("/public/signup").then(r => r.data),
    retry: false,
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { institution_type: "school", plan_code: "profesional", website: "" },
  });
  async function checkCode(code: string) {
    if (!code.trim()) return setCodeNote(null);
    try {
      const { data } = await api.get<{ available: boolean; reason: string | null }>(
        "/public/signup/code",
        { params: { code } },
      );
      setCodeNote(data.available ? null : data.reason);
    } catch {
      setCodeNote(null);
    }
  }
  async function submit(values: Values) {
    setServerError("");
    try {
      const { data } = await api.post<{ message: string }>("/public/signup", values);
      setSent(data.message);
    } catch (error) {
      setServerError(apiMessage(error));
    }
  }
  const brand = (
    <div className="brand-lockup signup-brand">
      <span className="brand-symbol">
        <GraduationCap />
      </span>
      <strong>Nexo</strong>
    </div>
  );
  if (config.isPending) return <Spinner label="Preparando el registro" />;
  if (!config.data?.enabled)
    return (
      <main className="signup-page">
        <section className="auth-card">
          {brand}
          <h2>Registro no disponible</h2>
          <p>Para usar Nexo en tu institución, escribe al equipo de Nexo.</p>
          <Link to="/login">Volver a iniciar sesión</Link>
        </section>
      </main>
    );
  if (sent)
    return (
      <main className="signup-page">
        <section className="auth-card" role="status">
          {brand}
          <MailCheck className="signup-sent-icon" aria-hidden />
          <h2>Revisa tu correo</h2>
          <p>{sent}</p>
          <Link to="/login">Volver a iniciar sesión</Link>
        </section>
      </main>
    );
  return (
    <main className="signup-page">
      <form className="auth-card signup-card" onSubmit={handleSubmit(submit)} noValidate>
        {brand}
        <div>
          <span className="kicker">Prueba gratuita de {config.data.trial_days} días</span>
          <h2>Crea la cuenta de tu institución</h2>
          <p>Sin tarjeta. Te enviaremos un correo para activar la cuenta del administrador.</p>
        </div>
        <label className="form-field">
          <span>Nombre de la institución</span>
          <input autoFocus autoComplete="organization" {...register("name")} />
          {errors.name && <small>{errors.name.message}</small>}
        </label>
        <label className="form-field">
          <span>Código (será su dirección y su código de acceso)</span>
          <input
            placeholder="colegio-horizonte"
            autoCapitalize="none"
            {...register("code", { onBlur: event => void checkCode(event.target.value) })}
          />
          {(errors.code || codeNote) && <small>{errors.code?.message ?? codeNote}</small>}
        </label>
        <label className="form-field">
          <span>Tipo</span>
          <select {...register("institution_type")}>
            <option value="school">Escuela o colegio</option>
            <option value="university">Universidad</option>
            <option value="both">Escuela y universidad</option>
          </select>
        </label>
        <label className="form-field">
          <span>Correo del administrador</span>
          <input type="email" autoComplete="email" {...register("admin_email")} />
          {errors.admin_email && <small>{errors.admin_email.message}</small>}
        </label>
        <fieldset className="signup-plans">
          <legend>Plan para después de la prueba</legend>
          {config.data.plans.map(plan => (
            <label key={plan.code} className="signup-plan">
              <input type="radio" value={plan.code} {...register("plan_code")} />
              <span>
                <strong>{plan.name}</strong>
                <small>
                  {plan.monthly_price} {plan.currency} al mes ·{" "}
                  {plan.max_students != null
                    ? `hasta ${plan.max_students.toLocaleString("es-DO")} estudiantes`
                    : "sin límite de estudiantes"}
                </small>
              </span>
            </label>
          ))}
        </fieldset>
        <label className="signup-terms">
          <input type="checkbox" {...register("accept_terms")} />
          <span>
            Acepto los <Link to="/legal/terminos">términos de uso</Link> y la{" "}
            <Link to="/legal/privacidad">política de privacidad</Link>.
          </span>
        </label>
        {errors.accept_terms && <small className="form-error">{errors.accept_terms.message}</small>}
        <div className="signup-trap" aria-hidden="true">
          <label>
            Sitio web
            <input tabIndex={-1} autoComplete="off" {...register("website")} />
          </label>
        </div>
        {serverError && (
          <div className="form-error" role="alert">
            {serverError}
          </div>
        )}
        <Button disabled={isSubmitting} className="auth-submit">
          {isSubmitting ? "Creando…" : "Crear la cuenta"}
        </Button>
        <p className="auth-help">
          ¿Ya usas Nexo? <Link to="/login">Inicia sesión</Link>
        </p>
      </form>
    </main>
  );
}
