import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, LogOut, Plus, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDateTime } from "../../lib/format";
import { platformApi, usePlatformSession } from "../../lib/platformApi";
import "./platform.css";

type Institution = ApiSchema<"InstitutionOut">;
type AuditEntry = ApiSchema<"PlatformAuditOut">;
type Me = ApiSchema<"PlatformMe">;
type Token = ApiSchema<"PlatformToken">;

const size = 20;
const types: Record<string, string> = {
  university: "Universidad",
  school: "Escuela o colegio",
  both: "Escuela y universidad",
};
const actions: Record<string, string> = {
  "platform.login": "Inicio de sesión",
  "platform.login_failed": "Intento fallido",
  "platform_admin.created": "Cuenta de plataforma creada",
  "institution.created": "Institución creada",
  "institution.suspended": "Institución suspendida",
  "institution.reactivated": "Institución reactivada",
};

/** Platform super administration (Fase 4 B): only Nexo's team, with its own accounts. */
export function PlatformPage() {
  const token = usePlatformSession(state => state.token);
  return token ? <PlatformConsole /> : <PlatformLogin />;
}

const loginSchema = z.object({
  email: z.string().email("Escribe un correo válido"),
  password: z.string().min(10, "La contraseña tiene al menos 10 caracteres"),
  otp: z.string().regex(/^\d{6}$/, "Usa los 6 dígitos de tu aplicación de verificación"),
});
type LoginValues = z.infer<typeof loginSchema>;

function PlatformLogin() {
  const signIn = usePlatformSession(state => state.signIn);
  const [serverError, setServerError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });
  async function submit(values: LoginValues) {
    setServerError("");
    try {
      const { data } = await platformApi.post<Token>("/platform/auth/login", values);
      signIn(data.access_token);
    } catch (error) {
      setServerError(apiMessage(error));
    }
  }
  return (
    <main className="platform-login">
      <form className="auth-card" onSubmit={handleSubmit(submit)}>
        <div>
          <span className="kicker">Nexo · Plataforma</span>
          <h2>Administración de la plataforma</h2>
          <p>Acceso exclusivo del equipo de Nexo. El código de verificación es obligatorio.</p>
        </div>
        <label className="form-field">
          <span>Correo</span>
          <input autoFocus autoComplete="username" {...register("email")} />
          {errors.email && <small>{errors.email.message}</small>}
        </label>
        <label className="form-field">
          <span>Contraseña</span>
          <input type="password" autoComplete="current-password" {...register("password")} />
          {errors.password && <small>{errors.password.message}</small>}
        </label>
        <label className="form-field">
          <span>Código de verificación</span>
          <input
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="000000"
            {...register("otp")}
          />
          {errors.otp && <small>{errors.otp.message}</small>}
        </label>
        {serverError && (
          <div className="form-error" role="alert">
            {serverError}
          </div>
        )}
        <Button disabled={isSubmitting} className="auth-submit">
          {isSubmitting ? "Verificando…" : "Entrar"}
        </Button>
      </form>
    </main>
  );
}

function PlatformConsole() {
  const signOut = usePlatformSession(state => state.signOut);
  const [term, setTerm] = useState("");
  const [page, setPage] = useState(0);
  const [creating, setCreating] = useState(false);
  const [changing, setChanging] = useState<Institution | null>(null);
  const me = useQuery({
    queryKey: ["platform", "me"],
    queryFn: () => platformApi.get<Me>("/platform/me").then(r => r.data),
  });
  const institutions = useQuery({
    queryKey: ["platform", "institutions", term, page],
    queryFn: () =>
      platformApi
        .get<Institution[]>("/platform/institutions", {
          params: { q: term || undefined, skip: page * size, limit: size },
        })
        .then(r => ({ rows: r.data, total: Number(r.headers["x-total-count"] ?? r.data.length) })),
  });
  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTerm(String(new FormData(event.currentTarget).get("q") ?? "").trim());
    setPage(0);
  }
  const total = institutions.data?.total ?? 0;
  return (
    <div className="page platform-page">
      <header className="page-header">
        <div>
          <span className="kicker">Nexo · Plataforma</span>
          <h1>Instituciones</h1>
          <p>Alta, suspensión y uso de cada institución. Aquí no se ven sus registros.</p>
        </div>
        <div className="form-actions">
          <Button onClick={() => setCreating(true)}>
            <Plus size={16} /> Nueva institución
          </Button>
          <Button variant="ghost" onClick={signOut}>
            <LogOut size={16} /> Salir{me.data ? ` (${me.data.name})` : ""}
          </Button>
        </div>
      </header>
      <form className="panel platform-search" onSubmit={search}>
        <label className="form-field">
          <span>Buscar</span>
          <input name="q" placeholder="Nombre o código" defaultValue={term} />
        </label>
        <Button variant="secondary">Buscar</Button>
      </form>
      {institutions.isLoading ? (
        <Spinner label="Cargando instituciones" />
      ) : institutions.error ? (
        <p role="alert" className="form-error">
          {apiMessage(institutions.error)}
        </p>
      ) : !institutions.data?.rows.length ? (
        <EmptyState
          icon={<Building2 />}
          title="Sin instituciones"
          description="No hay instituciones con ese criterio."
        />
      ) : (
        <div className="panel table-scroll">
          <table>
            <thead>
              <tr>
                <th>Institución</th>
                <th>Código</th>
                <th>Estado</th>
                <th>Estudiantes activos</th>
                <th>Cuentas</th>
                <th>Última actividad</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {institutions.data.rows.map(row => (
                <tr key={row.institution_id}>
                  <td>
                    <strong>{row.name}</strong>
                    <div className="muted">{row.contact_email ?? "—"}</div>
                  </td>
                  <td>{row.code}</td>
                  <td>
                    {row.status === "active" ? (
                      <Badge tone="success">Activa</Badge>
                    ) : (
                      <Badge tone="danger">Suspendida</Badge>
                    )}
                    {row.status_reason && <div className="muted">{row.status_reason}</div>}
                  </td>
                  <td>{row.usage.students}</td>
                  <td>{row.usage.users}</td>
                  <td>{row.usage.last_activity ? formatDateTime(row.usage.last_activity) : "—"}</td>
                  <td>
                    <Button
                      variant={row.status === "active" ? "danger" : "secondary"}
                      onClick={() => setChanging(row)}
                    >
                      {row.status === "active" ? "Suspender" : "Reactivar"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <Button
          variant="secondary"
          disabled={page === 0 || institutions.isFetching}
          onClick={() => setPage(current => current - 1)}
        >
          Anterior
        </Button>
        <span className="pagination__page">
          Página {page + 1} de {Math.max(1, Math.ceil(total / size))}
        </span>
        <Button
          variant="secondary"
          disabled={(page + 1) * size >= total || institutions.isFetching}
          onClick={() => setPage(current => current + 1)}
        >
          Siguiente
        </Button>
      </div>
      <PlatformAudit />
      {creating && <CreateInstitution onClose={() => setCreating(false)} />}
      {changing && <ChangeStatus institution={changing} onClose={() => setChanging(null)} />}
    </div>
  );
}

const createSchema = z.object({
  name: z.string().trim().min(3, "Escribe el nombre de la institución"),
  code: z
    .string()
    .trim()
    .regex(/^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$/, "Minúsculas, números y guiones (3 a 40)"),
  institution_type: z.enum(["university", "school", "both"]),
  admin_email: z.string().email("Escribe un correo válido"),
  enrollment_prefix: z.string().trim().min(1, "Escribe un prefijo").max(10),
});
type CreateValues = z.infer<typeof createSchema>;

function CreateInstitution({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { institution_type: "school", enrollment_prefix: "EST" },
  });
  const create = useMutation({
    mutationFn: (values: CreateValues) =>
      platformApi.post<Institution>("/platform/institutions", values).then(r => r.data),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["platform"] });
      onClose();
    },
  });
  return (
    <Modal
      title="Nueva institución"
      description="Se prepara con roles, escala de calificación y políticas, y se invita por correo a su primer administrador."
      onClose={onClose}
    >
      <form className="platform-form" onSubmit={handleSubmit(values => create.mutate(values))}>
        <label className="form-field">
          <span>Nombre</span>
          <input autoFocus {...register("name")} />
          {errors.name && <small>{errors.name.message}</small>}
        </label>
        <label className="form-field">
          <span>Código (también su subdominio)</span>
          <input placeholder="colegio-horizonte" {...register("code")} />
          {errors.code && <small>{errors.code.message}</small>}
        </label>
        <label className="form-field">
          <span>Tipo</span>
          <select {...register("institution_type")}>
            {Object.entries(types).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Correo del primer administrador</span>
          <input type="email" {...register("admin_email")} />
          {errors.admin_email && <small>{errors.admin_email.message}</small>}
        </label>
        <label className="form-field">
          <span>Prefijo de matrícula</span>
          <input {...register("enrollment_prefix")} />
          {errors.enrollment_prefix && <small>{errors.enrollment_prefix.message}</small>}
        </label>
        {create.error && (
          <div className="form-error" role="alert">
            {apiMessage(create.error)}
          </div>
        )}
        <div className="form-actions">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={create.isPending}>
            {create.isPending ? "Creando…" : "Crear e invitar"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ChangeStatus({ institution, onClose }: { institution: Institution; onClose: () => void }) {
  const client = useQueryClient();
  const suspend = institution.status === "active";
  const [reason, setReason] = useState("");
  const change = useMutation({
    mutationFn: () =>
      platformApi.post(
        `/platform/institutions/${institution.institution_id}/${suspend ? "suspend" : "reactivate"}`,
        { reason },
      ),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["platform"] });
      onClose();
    },
  });
  return (
    <Modal
      title={suspend ? `Suspender ${institution.name}` : `Reactivar ${institution.name}`}
      description={
        suspend
          ? "Nadie de la institución podrá entrar; verán un aviso de suspensión. Sus datos se conservan."
          : "La institución recupera el acceso de inmediato."
      }
      onClose={onClose}
    >
      <form
        className="platform-form"
        onSubmit={event => {
          event.preventDefault();
          change.mutate();
        }}
      >
        <label className="form-field">
          <span>Motivo</span>
          <textarea
            autoFocus
            value={reason}
            onChange={event => setReason(event.target.value)}
            minLength={5}
            required
          />
        </label>
        {change.error && (
          <div className="form-error" role="alert">
            {apiMessage(change.error)}
          </div>
        )}
        <div className="form-actions">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant={suspend ? "danger" : "primary"}
            disabled={change.isPending || reason.trim().length < 5}
          >
            {suspend ? "Suspender" : "Reactivar"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function PlatformAudit() {
  const audit = useQuery({
    queryKey: ["platform", "audit"],
    queryFn: () =>
      platformApi.get<AuditEntry[]>("/platform/audit", { params: { limit: 15 } }).then(r => r.data),
  });
  return (
    <section className="panel platform-audit">
      <h2>
        <ShieldCheck size={18} /> Actividad reciente de la plataforma
      </h2>
      {audit.isLoading ? (
        <Spinner label="Cargando actividad" />
      ) : !audit.data?.length ? (
        <p className="muted">Sin actividad registrada.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Cuenta</th>
                <th>Acción</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {audit.data.map(entry => (
                <tr key={entry.platform_audit_log_id}>
                  <td>{formatDateTime(entry.created_at)}</td>
                  <td>{entry.actor ?? "—"}</td>
                  <td title={entry.action}>{actions[entry.action] ?? entry.action}</td>
                  <td>{entry.detail || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
