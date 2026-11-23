import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarRange,
  History,
  Pause,
  Pencil,
  Play,
  Plus,
  ReceiptText,
  X,
} from "lucide-react";
import { useId, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { LookupSelect } from "../../components/LookupSelect";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { confirmAction } from "../../lib/confirm";
import { formatDate, formatDateTime, formatMoney, todayIso } from "../../lib/format";
import { fetchAllOptions } from "../../lib/options";
import { useAccess } from "../../lib/permissions";
import { useAuthStore } from "../../store/auth";
import { cycleLabel } from "./billingCycles";
import { SchoolTargets } from "./SchoolTargets";
import "./billing-plans.css";

type Plan = ApiSchema<"BillingPlanOut">;
type Preview = ApiSchema<"BillingPreview">;
type Run = ApiSchema<"BillingRunOut">;
type Targets = ApiSchema<"BillingPlanTargets">;
type Career = {
  career_id: number;
  code: string;
  name: string;
  academic_level?: string;
  duration_terms?: number;
};
type Concept = { billing_concept_id: number; name: string; amount: number | string };

const money = (value: number | string) => formatMoney(Number(value));
const charges = (count: number) => `${count} ${count === 1 ? "cargo" : "cargos"}`;
const operationKey = () =>
  globalThis.crypto?.randomUUID?.() ?? `run-${Date.now()}-${Math.random().toString(36).slice(2)}`;

function targetSummary(value: Targets, careers: Career[]) {
  const targets = normalizeTargets(value);
  const names = targets.career_ids
    .map(id => careers.find(career => career.career_id === id)?.name)
    .filter(Boolean);
  const parts = [
    names.length ? names.join(", ") : "",
    targets.grades.length
      ? targets.grades
          .map(
            item =>
              `${item.grade_number}.º ${careers.find(c => c.career_id === item.career_id)?.name ?? ""}`,
          )
          .join(", ")
      : "",
    targets.student_ids.length
      ? `${targets.student_ids.length} estudiante${targets.student_ids.length === 1 ? "" : "s"}`
      : "",
    targets.excluded_student_ids.length
      ? `${targets.excluded_student_ids.length} excluido${targets.excluded_student_ids.length === 1 ? "" : "s"}`
      : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Sin destinatarios";
}

function normalizeTargets(targets: Targets) {
  return {
    career_ids: targets.career_ids ?? [],
    grades: targets.grades ?? [],
    student_ids: targets.student_ids ?? [],
    excluded_student_ids: targets.excluded_student_ids ?? [],
  };
}

function useCareers() {
  const uid = useAuthStore(state => state.user?.user_id);
  return useQuery({
    queryKey: ["billing-careers", uid],
    queryFn: () => fetchAllOptions<Career>("/careers/", "career_id"),
  });
}

export function BillingPlansPage() {
  const uid = useAuthStore(state => state.user?.user_id);
  const access = useAccess();
  const canManage = access.can("finance.manage");
  const client = useQueryClient();
  const [editing, setEditing] = useState<Plan | "new">();
  const [generating, setGenerating] = useState<Plan>();
  const [historyOf, setHistoryOf] = useState<Plan>();
  const plans = useQuery({
    queryKey: ["billing-plans", uid],
    queryFn: () => api.get<Plan[]>("/finance/billing-plans").then(r => r.data),
  });
  const careers = useCareers();
  const toggle = useMutation({
    mutationFn: (plan: Plan) =>
      api.patch(`/finance/billing-plans/${plan.billing_plan_id}`, { active: !plan.active }),
    onSuccess: (_, plan) => {
      toast.success(plan.active ? "Plan pausado" : "Plan reactivado");
      void client.invalidateQueries({ queryKey: ["billing-plans"] });
    },
    onError: error => toast.error(apiMessage(error)),
  });

  return (
    <div className="page billing-plans">
      <header className="page-header">
        <div>
          <Link className="back-link" to="/finance">
            <ArrowLeft size={16} /> Cuentas estudiantiles
          </Link>
          <span className="kicker">Control financiero · RD$</span>
          <h1>Planes de cobro</h1>
          <p>
            Mensualidades e inscripciones por carrera o grado. Revisa la vista previa y genera los
            cargos de cada mes; un mes nunca se cobra dos veces.
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setEditing("new")}>
            <Plus size={18} />
            Nuevo plan
          </Button>
        )}
      </header>
      {plans.isPending ? (
        <Spinner label="Cargando planes" />
      ) : plans.error ? (
        <EmptyState
          icon={<ReceiptText />}
          title="No pudimos cargar los planes"
          description={apiMessage(plans.error)}
          action={<Button onClick={() => plans.refetch()}>Reintentar</Button>}
        />
      ) : plans.data.length === 0 ? (
        <EmptyState
          icon={<CalendarRange />}
          title="Aún no hay planes de cobro"
          description="Crea un plan, por ejemplo «Mensualidad 2026-2027», y elige a qué carreras o grados aplica."
          action={
            canManage ? (
              <Button onClick={() => setEditing("new")}>Crear el primer plan</Button>
            ) : undefined
          }
        />
      ) : (
        <section className="billing-plan-grid" aria-label="Planes de cobro">
          {plans.data.map(plan => {
            const done = plan.generated_cycles.length;
            const total = plan.cycles.length;
            return (
              <article key={plan.billing_plan_id} className="billing-plan-card">
                <header>
                  <div>
                    <h2>{plan.name}</h2>
                    <small>{targetSummary(plan.targets, careers.data ?? [])}</small>
                  </div>
                  <Badge tone={plan.active ? "success" : "neutral"}>
                    {plan.active ? "Activo" : "Pausado"}
                  </Badge>
                </header>
                <p className="billing-plan-amount">
                  <strong>{money(plan.amount)}</strong>
                  <span>{plan.frequency === "monthly" ? "por mes" : "pago único"}</span>
                </p>
                <dl>
                  <div>
                    <dt>Meses</dt>
                    <dd>
                      {plan.frequency === "monthly"
                        ? `${cycleLabel(plan.start_month)} – ${cycleLabel(plan.end_month)}`
                        : cycleLabel(plan.start_month)}
                    </dd>
                  </div>
                  <div>
                    <dt>Vence</dt>
                    <dd>El día {plan.due_day}</dd>
                  </div>
                  <div>
                    <dt>Próximo</dt>
                    <dd>{plan.next_cycle ? cycleLabel(plan.next_cycle) : "—"}</dd>
                  </div>
                </dl>
                <div
                  className="billing-progress"
                  role="progressbar"
                  aria-label={`${done} de ${total} meses generados`}
                  aria-valuemin={0}
                  aria-valuemax={total}
                  aria-valuenow={done}
                >
                  <span style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
                </div>
                <small className="muted">
                  {done} de {total} {total === 1 ? "mes generado" : "meses generados"}
                </small>
                <footer>
                  {canManage && (
                    <Button
                      disabled={!plan.active}
                      onClick={() => setGenerating(plan)}
                      title={plan.active ? undefined : "Reactiva el plan para generar cargos"}
                    >
                      Generar cargos
                    </Button>
                  )}
                  {!canManage && (
                    <Button variant="secondary" onClick={() => setGenerating(plan)}>
                      Vista previa
                    </Button>
                  )}
                  <span className="billing-plan-tools">
                    {canManage && (
                      <Button
                        variant="ghost"
                        title="Editar plan"
                        aria-label={`Editar ${plan.name}`}
                        onClick={() => setEditing(plan)}
                      >
                        <Pencil size={16} />
                      </Button>
                    )}
                    {canManage && (
                      <Button
                        variant="ghost"
                        disabled={toggle.isPending}
                        title={plan.active ? "Pausar plan" : "Reactivar plan"}
                        aria-label={`${plan.active ? "Pausar" : "Reactivar"} ${plan.name}`}
                        onClick={async () => {
                          if (
                            !plan.active ||
                            (await confirmAction(
                              `¿Pausar «${plan.name}»? No se podrán generar cargos hasta reactivarlo.`,
                            ))
                          )
                            toggle.mutate(plan);
                        }}
                      >
                        {plan.active ? <Pause size={16} /> : <Play size={16} />}
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      title="Historial de generaciones"
                      aria-label={`Historial de ${plan.name}`}
                      onClick={() => setHistoryOf(plan)}
                    >
                      <History size={16} />
                    </Button>
                  </span>
                </footer>
              </article>
            );
          })}
        </section>
      )}
      {editing && (
        <PlanEditor
          plan={editing === "new" ? undefined : editing}
          careers={careers.data ?? []}
          onClose={() => setEditing(undefined)}
        />
      )}
      {generating && (
        <GenerateModal
          plan={generating}
          canManage={canManage}
          onClose={() => setGenerating(undefined)}
        />
      )}
      {historyOf && <RunHistory plan={historyOf} onClose={() => setHistoryOf(undefined)} />}
    </div>
  );
}

function StudentPicker({
  label,
  ids,
  onChange,
}: {
  label: string;
  ids: number[];
  onChange: (ids: number[]) => void;
}) {
  const labelId = useId();
  const uid = useAuthStore(state => state.user?.user_id);
  const names = useQuery({
    queryKey: ["billing-student-names", uid],
    queryFn: () =>
      fetchAllOptions<{ student_id: number; first_name: string; last_name: string }>(
        "/students/",
        "student_id",
      ),
    enabled: ids.length > 0,
  });
  const nameOf = (id: number) => {
    const student = names.data?.find(item => item.student_id === id);
    return student ? `${student.first_name} ${student.last_name}` : `Estudiante ${id}`;
  };
  return (
    <div className="form-field">
      <span id={labelId}>{label}</span>
      <LookupSelect
        labelId={labelId}
        value={null}
        config={{
          endpoint: "/students/",
          valueKey: "student_id",
          labelKeys: ["first_name", "last_name"],
          secondaryKey: "enrollment_number",
          placeholder: "Buscar estudiante",
        }}
        onChange={value => {
          const id = Number(value);
          if (id && !ids.includes(id)) onChange([...ids, id]);
        }}
      />
      {ids.length > 0 && (
        <ul className="billing-chips">
          {ids.map(id => (
            <li key={id}>
              {nameOf(id)}
              <button
                type="button"
                aria-label={`Quitar ${nameOf(id)}`}
                onClick={() => onChange(ids.filter(item => item !== id))}
              >
                <X size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function PlanEditor({
  plan,
  careers,
  onClose,
}: {
  plan?: Plan;
  careers: Career[];
  onClose: () => void;
}) {
  const uid = useAuthStore(state => state.user?.user_id);
  const client = useQueryClient();
  const creating = !plan;
  const descriptionId = useId();
  const locked = Boolean(plan?.generated_cycles.length);
  const [name, setName] = useState(plan?.name ?? "");
  const [description, setDescription] = useState(plan?.charge_description ?? "");
  const [conceptId, setConceptId] = useState<number | "">(plan?.billing_concept_id ?? "");
  const [amount, setAmount] = useState(plan ? String(plan.amount) : "");
  const [frequency, setFrequency] = useState(plan?.frequency ?? "monthly");
  const [start, setStart] = useState(plan?.start_month ?? "");
  const [end, setEnd] = useState(plan?.end_month ?? "");
  const [dueDay, setDueDay] = useState(String(plan?.due_day ?? 5));
  const initial = normalizeTargets(plan?.targets ?? {});
  const [careerIds, setCareerIds] = useState<number[]>(initial.career_ids);
  const [studentIds, setStudentIds] = useState<number[]>(initial.student_ids);
  const [excluded, setExcluded] = useState<number[]>(initial.excluded_student_ids);
  const [grades, setGrades] = useState(initial.grades);
  const [yearId, setYearId] = useState<number | "">(plan?.school_year_id ?? "");
  const [sibling, setSibling] = useState(plan?.sibling_discount ?? false);
  const concepts = useQuery({
    queryKey: ["finance-concepts", uid],
    queryFn: () => api.get<Concept[]>("/finance/billing-concepts").then(r => r.data),
    enabled: creating,
  });
  const targets = {
    career_ids: careerIds,
    grades,
    student_ids: studentIds,
    excluded_student_ids: excluded,
  };
  const save = useMutation({
    mutationFn: async () => {
      if (creating) {
        await api.post("/finance/billing-plans", {
          name: name.trim(),
          charge_description: description.trim(),
          billing_concept_id: conceptId || null,
          amount,
          frequency,
          start_month: start || null,
          end_month: frequency === "monthly" ? end || null : null,
          due_day: Number(dueDay),
          school_year_id: yearId || null,
          sibling_discount: sibling,
          targets,
        });
        return;
      }
      await api.patch(`/finance/billing-plans/${plan.billing_plan_id}`, {
        name: name.trim(),
        charge_description: description.trim(),
        amount,
        due_day: Number(dueDay),
        sibling_discount: sibling,
        ...(frequency === "monthly" && end !== plan.end_month ? { end_month: end } : {}),
      });
      await api.put(`/finance/billing-plans/${plan.billing_plan_id}/targets`, targets);
    },
    onSuccess: () => {
      toast.success(creating ? "Plan de cobro creado" : "Plan actualizado");
      void client.invalidateQueries({ queryKey: ["billing-plans"] });
      onClose();
    },
    onError: error => toast.error(apiMessage(error)),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (frequency === "monthly" && start && end && end < start) {
      toast.error("El mes final no puede ser anterior al mes inicial");
      return;
    }
    if (!yearId && (!start || (frequency === "monthly" && !end))) {
      toast.error("Indica los meses o elige el año lectivo");
      return;
    }
    if (!careerIds.length && !studentIds.length && !grades.length) {
      toast.error("Elige al menos una carrera o grado, o un estudiante");
      return;
    }
    save.mutate();
  }
  return (
    <Modal
      title={creating ? "Nuevo plan de cobro" : `Editar «${plan.name}»`}
      description={
        locked
          ? "Los cambios de monto o fecha de vencimiento solo afectan a los meses que aún no se han generado."
          : "Define el cargo, sus meses y a quién se aplica."
      }
      onClose={onClose}
    >
      <form className="billing-editor" onSubmit={submit}>
        <fieldset>
          <legend>Cargo</legend>
          <div className="billing-editor__grid">
            <label className="form-field">
              <span>Nombre del plan</span>
              <input
                required
                minLength={2}
                maxLength={120}
                value={name}
                placeholder="Ej. Mensualidad 2026-2027"
                onChange={event => setName(event.target.value)}
              />
            </label>
            {creating && (
              <label className="form-field">
                <span>Concepto del catálogo (opcional)</span>
                <select
                  value={conceptId}
                  onChange={event => {
                    const id = Number(event.target.value) || "";
                    setConceptId(id);
                    const concept = concepts.data?.find(item => item.billing_concept_id === id);
                    if (concept) {
                      setAmount(String(concept.amount));
                      if (!description) setDescription(concept.name);
                    }
                  }}
                >
                  <option value="">Sin concepto</option>
                  {concepts.data?.map(item => (
                    <option key={item.billing_concept_id} value={item.billing_concept_id}>
                      {item.name} · {money(item.amount)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div className="form-field">
              <label htmlFor={descriptionId}>Texto del cargo</label>
              <input
                id={descriptionId}
                required
                minLength={2}
                maxLength={150}
                value={description}
                placeholder="Ej. Mensualidad"
                aria-describedby={`${descriptionId}-hint`}
                onChange={event => setDescription(event.target.value)}
              />
              <p id={`${descriptionId}-hint`} className="billing-hint">
                Se añade el mes: «{description || "Mensualidad"} · agosto 2026».
              </p>
            </div>
            <label className="form-field">
              <span>Monto RD$</span>
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={event => setAmount(event.target.value)}
              />
            </label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Meses</legend>
          <div className="billing-editor__grid">
            <label className="form-field">
              <span>Frecuencia</span>
              <select
                value={frequency}
                disabled={!creating}
                onChange={event => setFrequency(event.target.value)}
              >
                <option value="monthly">Mensual</option>
                <option value="single">Pago único (inscripción, período)</option>
              </select>
            </label>
            <label className="form-field">
              <span>{frequency === "monthly" ? "Primer mes" : "Mes del cobro"}</span>
              <input
                required={!yearId}
                type="month"
                disabled={!creating}
                value={start}
                onChange={event => setStart(event.target.value)}
              />
            </label>
            {frequency === "monthly" && (
              <label className="form-field">
                <span>Último mes</span>
                <input
                  required={!yearId}
                  type="month"
                  min={start || undefined}
                  value={end}
                  onChange={event => setEnd(event.target.value)}
                />
              </label>
            )}
            <label className="form-field">
              <span>Día de vencimiento</span>
              <input
                required
                type="number"
                min={1}
                max={28}
                value={dueDay}
                onChange={event => setDueDay(event.target.value)}
              />
            </label>
          </div>
        </fieldset>
        <fieldset>
          <legend>A quién se cobra</legend>
          <p className="muted">
            Solo estudiantes activos. Quien ingrese a mitad de año se cobra desde su mes de
            admisión.
          </p>
          <SchoolTargets
            careers={careers}
            yearId={yearId}
            onYearChange={setYearId}
            grades={grades}
            onGradesChange={setGrades}
            disabled={!creating}
          />
          {yearId !== "" && !start && (
            <p className="muted">
              Sin meses indicados, el plan cobra todos los meses del año lectivo.
            </p>
          )}
          <label className="billing-sibling">
            <input
              type="checkbox"
              checked={sibling}
              onChange={event => setSibling(event.target.checked)}
            />
            Aplica descuento por hermanos (según la política de Finanzas)
          </label>
          <div className="billing-careers" role="group" aria-label="Carreras o grados">
            {careers.map(career => (
              <label key={career.career_id}>
                <input
                  type="checkbox"
                  checked={careerIds.includes(career.career_id)}
                  onChange={event =>
                    setCareerIds(
                      event.target.checked
                        ? [...careerIds, career.career_id]
                        : careerIds.filter(id => id !== career.career_id),
                    )
                  }
                />
                <span>
                  <strong>{career.name}</strong>
                  <small>{career.code}</small>
                </span>
              </label>
            ))}
          </div>
          <div className="billing-editor__grid">
            <StudentPicker
              label="Añadir estudiantes sueltos"
              ids={studentIds}
              onChange={setStudentIds}
            />
            <StudentPicker label="Excluir estudiantes" ids={excluded} onChange={setExcluded} />
          </div>
        </fieldset>
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose} disabled={save.isPending}>
            Cancelar
          </Button>
          <Button disabled={save.isPending}>{creating ? "Crear plan" : "Guardar cambios"}</Button>
        </div>
      </form>
    </Modal>
  );
}

export function GenerateModal({
  plan,
  canManage,
  onClose,
}: {
  plan: Plan;
  canManage: boolean;
  onClose: () => void;
}) {
  const uid = useAuthStore(state => state.user?.user_id);
  const client = useQueryClient();
  const [cycle, setCycle] = useState(plan.next_cycle ?? plan.cycles[0]);
  const [reason, setReason] = useState("Generación de cargos del mes");
  const key = useMemo(operationKey, []);
  const preview = useQuery({
    queryKey: ["billing-preview", uid, plan.billing_plan_id, cycle],
    queryFn: () =>
      api
        .post<Preview>(`/finance/billing-plans/${plan.billing_plan_id}/preview`, { cycle })
        .then(r => r.data),
    gcTime: 0,
  });
  const run = useMutation({
    mutationFn: () =>
      api
        .post<Run>(`/finance/billing-plans/${plan.billing_plan_id}/runs`, {
          cycle,
          reason: reason.trim(),
          idempotency_key: `${key}-${cycle}`,
        })
        .then(r => r.data),
    onSuccess: result => {
      toast.success(
        result.charge_count
          ? `${charges(result.charge_count)} ${result.charge_count === 1 ? "generado" : "generados"} por ${money(result.total)}`
          : "No había cargos pendientes en ese mes",
      );
      void client.invalidateQueries({ queryKey: ["billing-plans"] });
      void client.invalidateQueries({ queryKey: ["finance-accounts"] });
      void client.invalidateQueries({ queryKey: ["billing-runs"] });
      onClose();
    },
    onError: error => toast.error(apiMessage(error)),
  });
  const data = preview.data;
  return (
    <Modal
      title={canManage ? `Generar cargos · ${plan.name}` : `Vista previa · ${plan.name}`}
      description="Revisa a quién se cobrará antes de confirmar. Los cargos ya generados no se repiten."
      onClose={onClose}
    >
      <form
        className="billing-generate"
        onSubmit={async event => {
          event.preventDefault();
          if (
            data &&
            (await confirmAction(
              `Se ${data.to_charge === 1 ? "creará" : "crearán"} ${charges(data.to_charge)} de ${money(data.amount)} (${money(data.total)} en total) para ${cycleLabel(cycle, true)}. ¿Confirmar?`,
            ))
          )
            run.mutate();
        }}
      >
        <label className="form-field">
          <span>Mes a cobrar</span>
          <select value={cycle} onChange={event => setCycle(event.target.value)}>
            {plan.cycles.map(item => (
              <option key={item} value={item}>
                {cycleLabel(item, true)}
                {plan.generated_cycles.includes(item) ? " · ya generado" : ""}
              </option>
            ))}
          </select>
        </label>
        {preview.isPending ? (
          <Spinner label="Calculando vista previa" />
        ) : preview.error ? (
          <p className="form-error">{apiMessage(preview.error)}</p>
        ) : data ? (
          <>
            <div className="billing-preview-metrics">
              <div>
                <span>Se cobrarán</span>
                <strong>{data.to_charge}</strong>
              </div>
              <div>
                <span>Total</span>
                <strong>{money(data.total)}</strong>
              </div>
              <div>
                <span>Vence</span>
                <strong>{formatDate(data.due_date)}</strong>
              </div>
              <div>
                <span>Ya cobrados</span>
                <strong>{data.already_charged}</strong>
              </div>
            </div>
            <p className="muted">
              Cargo: <strong>{data.charge_description}</strong> · {money(data.amount)}
            </p>
            {data.to_charge > 0 && data.due_date < todayIso() && (
              <p className="billing-warning" role="note">
                El vencimiento de este mes ya pasó: los cargos quedarán vencidos desde hoy.
              </p>
            )}
            {data.with_payment_plan > 0 && (
              <p className="billing-warning" role="note">
                {data.with_payment_plan} estudiante{data.with_payment_plan === 1 ? "" : "s"} con
                plan de pago activo. El nuevo cargo se suma a su balance fuera del plan.
              </p>
            )}
            {data.students.length > 0 ? (
              <ul className="billing-student-list" aria-label="Estudiantes a cobrar">
                {data.students.map(student => (
                  <li key={student.student_id}>
                    <span>{student.student_name}</span>
                    <small>
                      {student.enrollment_number}
                      {student.has_payment_plan ? " · plan de pago" : ""}
                    </small>
                  </li>
                ))}
                {data.to_charge > data.students.length && (
                  <li className="muted">
                    y {data.to_charge - data.students.length} estudiantes más
                  </li>
                )}
              </ul>
            ) : (
              <p className="muted">No hay cargos pendientes para este mes.</p>
            )}
            {canManage && (
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
          </>
        ) : null}
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose} disabled={run.isPending}>
            {canManage ? "Cancelar" : "Cerrar"}
          </Button>
          {canManage && (
            <Button disabled={run.isPending || !data || data.to_charge === 0}>
              {data ? `Generar ${charges(data.to_charge)}` : "Generar cargos"}
            </Button>
          )}
        </div>
      </form>
    </Modal>
  );
}

function RunHistory({ plan, onClose }: { plan: Plan; onClose: () => void }) {
  const uid = useAuthStore(state => state.user?.user_id);
  const runs = useQuery({
    queryKey: ["billing-runs", uid, plan.billing_plan_id],
    queryFn: () =>
      api.get<Run[]>(`/finance/billing-plans/${plan.billing_plan_id}/runs`).then(r => r.data),
  });
  return (
    <Modal title={`Historial · ${plan.name}`} onClose={onClose}>
      {runs.isPending ? (
        <Spinner />
      ) : runs.error ? (
        <p className="form-error">{apiMessage(runs.error)}</p>
      ) : runs.data.length ? (
        <ol className="billing-history">
          {runs.data.map(run => (
            <li key={run.billing_run_id}>
              <strong>
                {cycleLabel(run.cycle, true)} · {charges(run.charge_count)} · {money(run.total)}
              </strong>
              <small>
                {formatDateTime(run.created_at)} · {run.reason}
              </small>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">Todavía no se han generado cargos con este plan.</p>
      )}
    </Modal>
  );
}
