import { confirmAction } from "../../lib/confirm";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDateTime } from "../../lib/format";
import { Building2, Hash, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./institution-settings.css";

type SettingsForm = {
  institution_name: string;
  enrollment_prefix: string;
  enrollment_digits: number;
  passing_grade: number;
  max_credits_per_period: number;
  students_view_finance: boolean;
  institution_type: string;
  school_code: string;
  regional: string;
  district: string;
};
type Settings = SettingsForm & {
  settings_id: number;
  next_enrollment_number: number;
  enrollment_preview: string;
  revision: number;
};
type Preview = {
  revision: number;
  existing_selections_preserved: number;
  policy: string;
  changes: { field: string; before: string | number; after: string | number }[];
};
type History = { id: number; actor: string; detail: string; created_at: string };
const names: Record<string, string> = {
  institution_name: "Institución",
  enrollment_prefix: "Prefijo de matrícula",
  enrollment_digits: "Dígitos de matrícula",
  passing_grade: "Nota aprobatoria para nuevas selecciones",
  max_credits_per_period: "Máximo de créditos",
  students_view_finance: "El estudiante ve sus finanzas",
  institution_type: "Tipo de institución",
  school_code: "Código del centro",
  regional: "Regional educativa",
  district: "Distrito educativo",
};
const fields = (s: Settings): SettingsForm => ({
  institution_name: s.institution_name,
  enrollment_prefix: s.enrollment_prefix,
  enrollment_digits: s.enrollment_digits,
  passing_grade: s.passing_grade,
  max_credits_per_period: s.max_credits_per_period,
  students_view_finance: s.students_view_finance ?? true,
  institution_type: s.institution_type ?? "university",
  school_code: s.school_code ?? "",
  regional: s.regional ?? "",
  district: s.district ?? "",
});
export function InstitutionSettingsPage() {
  const uid = useAuthStore(s => s.user?.user_id);
  const client = useQueryClient();
  const [baseline, setBaseline] = useState<Settings>();
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<Preview>();
  const query = useQuery({
    queryKey: ["institution-settings", uid],
    queryFn: () => api.get<Settings>("/configuration/institution").then(r => r.data),
  });
  const history = useQuery({
    queryKey: ["institution-settings-history", uid],
    queryFn: () => api.get<History[]>("/configuration/institution/history").then(r => r.data),
  });
  const {
    register,
    handleSubmit,
    reset,
    getValues,
    setValue,
    formState: { isDirty },
  } = useForm<SettingsForm>();
  useEffect(() => {
    if (query.data && !isDirty) {
      setBaseline(query.data);
      reset(fields(query.data));
    }
  }, [query.data, isDirty, reset]);
  useEffect(() => {
    if (!isDirty) return;
    const guard = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [isDirty]);
  const payload = () => ({
    ...getValues(),
    enrollment_digits: Number(getValues("enrollment_digits")),
    passing_grade: Number(getValues("passing_grade")),
    max_credits_per_period: Number(getValues("max_credits_per_period")),
    expected_revision: baseline?.revision,
    reason,
  });
  const inspect = useMutation({
    mutationFn: () =>
      api.post<Preview>("/configuration/institution/preview", payload()).then(r => r.data),
    onSuccess: setPreview,
    onError: e => toast.error(apiMessage(e)),
  });
  const save = useMutation({
    mutationFn: () => api.put<Settings>("/configuration/institution", payload()),
    onSuccess: r => {
      toast.success(
        "Configuración guardada; se conservan los criterios de las selecciones existentes",
      );
      reset(fields(r.data));
      setBaseline(r.data);
      setReason("");
      setPreview(undefined);
      client.setQueryData(["institution-settings", uid], r.data);
      void client.invalidateQueries({ queryKey: ["institution-settings-history"] });
    },
    onError: e => toast.error(apiMessage(e)),
  });
  if (query.isLoading)
    return (
      <div className="page">
        <Spinner />
      </div>
    );
  if (query.error || !query.data)
    return (
      <div className="page">
        <EmptyState
          icon={<Building2 />}
          title="No pudimos cargar la configuración"
          description={apiMessage(query.error)}
        />
      </div>
    );
  const busy = inspect.isPending || save.isPending;
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="kicker">Administración</span>
          <h1>Configuración institucional</h1>
          <p>Identidad y reglas para nuevas selecciones, con revisión de impacto e historial.</p>
        </div>
      </header>
      <section className="settings-editor">
        <form
          className="panel resource-form"
          onChange={() => setPreview(undefined)}
          onSubmit={handleSubmit(() => {
            if (!preview) inspect.mutate();
            else save.mutate();
          })}
        >
          <label className="form-field settings-wide">
            <span>Nombre de la institución</span>
            <input
              disabled={busy}
              maxLength={150}
              {...register("institution_name", { required: true, minLength: 2 })}
            />
          </label>
          <label className="form-field">
            <span>Prefijo de matrícula</span>
            <input
              disabled={busy}
              maxLength={20}
              pattern="[A-Za-z0-9-]+"
              {...register("enrollment_prefix", { required: true })}
            />
          </label>
          <label className="form-field">
            <span>Cantidad de dígitos</span>
            <input
              disabled={busy}
              type="number"
              min={3}
              max={10}
              {...register("enrollment_digits", { required: true })}
            />
          </label>
          <label className="form-field">
            <span>Nota aprobatoria para nuevas selecciones</span>
            <input
              disabled={busy}
              type="number"
              min={0}
              max={100}
              step=".01"
              {...register("passing_grade", { required: true })}
            />
          </label>
          <label className="form-field">
            <span>Máximo de créditos por período</span>
            <input
              disabled={busy}
              type="number"
              min={1}
              max={60}
              {...register("max_credits_per_period", { required: true })}
            />
          </label>
          <label className="form-field settings-wide">
            <span>Tipo de institución</span>
            <select
              disabled={busy}
              {...register("institution_type", {
                onChange: event => {
                  // Schools hide students' own finances by default (their guardians see them).
                  if (event.target.value === "school")
                    setValue("students_view_finance", false, { shouldDirty: true });
                },
              })}
            >
              <option value="university">Universidad: carreras, créditos y selección libre</option>
              <option value="school">Escuela: niveles, grados y cursos fijos</option>
              <option value="both">Universidad y escuela</option>
            </select>
            <small>
              Al pasar a escuela, el estudiante deja de ver sus finanzas (sus tutores sí) salvo que
              lo actives abajo. Los programas deben tener un nivel acorde.
            </small>
          </label>
          <label className="form-field">
            <span>Código del centro (MINERD)</span>
            <input disabled={busy} maxLength={30} {...register("school_code")} />
          </label>
          <label className="form-field">
            <span>Regional educativa</span>
            <input disabled={busy} maxLength={80} {...register("regional")} />
          </label>
          <label className="form-field">
            <span>Distrito educativo</span>
            <input disabled={busy} maxLength={80} {...register("district")} />
            <small>Aparecen en el encabezado de los boletines.</small>
          </label>
          <label className="settings-toggle settings-wide">
            <input disabled={busy} type="checkbox" {...register("students_view_finance")} />
            <span>
              <b>El estudiante ve sus finanzas en su portal</b>
              <small>
                Recomendado en universidades. En escuelas suele desactivarse: el tutor sigue viendo
                el balance según los accesos de su vínculo.
              </small>
            </span>
          </label>
          <div className="enrollment-preview settings-wide">
            <Hash />
            <div>
              <small>Próxima matrícula con la configuración guardada</small>
              <strong>{query.data.enrollment_preview}</strong>
            </div>
          </div>
          <p className="settings-wide muted">
            Cambiar el prefijo no renumera estudiantes. Cambiar la nota no reclasifica selecciones
            existentes. Reducir créditos no retira materias ya seleccionadas.
          </p>
          <label className="form-field settings-wide">
            <span>Motivo del cambio institucional</span>
            <input
              required
              disabled={busy}
              minLength={3}
              maxLength={250}
              value={reason}
              onChange={e => setReason(e.target.value)}
            />
          </label>
          {preview && (
            <section
              className="settings-wide settings-impact"
              aria-label="Impacto de la configuración"
            >
              <h2>Revisión antes de guardar</h2>
              {preview.changes.map(c => (
                <p key={c.field}>
                  <strong>{names[c.field] || c.field}:</strong> {c.before} → {c.after}
                </p>
              ))}
              <p>
                {preview.existing_selections_preserved} selecciones conservarán su criterio
                aprobatorio.
              </p>
              <p>{preview.policy}</p>
            </section>
          )}
          <div className="form-actions">
            <Button
              type="button"
              variant="secondary"
              disabled={busy || !isDirty}
              onClick={async () => {
                if (await confirmAction("¿Descartar los cambios sin guardar?")) {
                  reset(fields(query.data!));
                  setBaseline(query.data);
                  setReason("");
                  setPreview(undefined);
                }
              }}
            >
              Descartar
            </Button>
            <Button disabled={busy || !isDirty}>
              <Save size={17} />
              {busy ? "Procesando…" : preview ? "Confirmar configuración" : "Revisar impacto"}
            </Button>
          </div>
        </form>
      </section>
      <section className="panel settings-editor settings-history">
        <h2>Historial de configuración</h2>
        {history.isLoading ? (
          <Spinner />
        ) : history.error ? (
          <p className="form-error">{apiMessage(history.error)}</p>
        ) : history.data?.length ? (
          history.data.map(h => (
            <article key={h.id}>
              <strong>
                {h.actor} · {formatDateTime(h.created_at)}
              </strong>
              <p>{h.detail}</p>
            </article>
          ))
        ) : (
          <p className="muted">Sin cambios auditados desde esta mejora.</p>
        )}
      </section>
    </div>
  );
}
