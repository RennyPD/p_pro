import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, PlayCircle, Save, TestTube2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button, Spinner } from "../../components/ui";
import { Section } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { confirmAction } from "../../lib/confirm";
import { useAccess } from "../../lib/permissions";
import "./finance-policy.css";

type Policy = ApiSchema<"FinancePolicyOut">;
type Run = ApiSchema<"AutomationRun">;
type Draft = Record<keyof Policy, string | boolean>;

const toDraft = (policy: Policy): Draft =>
  Object.fromEntries(
    Object.entries(policy).map(([key, value]) => [
      key,
      typeof value === "boolean" ? value : String(value),
    ]),
  ) as Draft;

/**
 * Late fees, automatic holds, sibling discount and scheduled billing (Fase 3 E).
 * Everything starts disabled; the simulation shows its effect before applying it.
 */
export function FinancePolicyPage() {
  const client = useQueryClient();
  const canEdit = useAccess().can("finance.supervise");
  const policy = useQuery({
    queryKey: ["finance-policy"],
    queryFn: () => api.get<Policy>("/finance/policy").then(r => r.data),
  });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [reason, setReason] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  useEffect(() => {
    if (policy.data) setDraft(toDraft(policy.data));
  }, [policy.data]);
  const save = useMutation({
    mutationFn: () => api.put<Policy>("/finance/policy", { ...draft, reason }),
    onSuccess: response => {
      client.setQueryData(["finance-policy"], response.data);
      setReason("");
      toast.success("Política financiera guardada");
    },
    onError: error => toast.error(apiMessage(error)),
  });
  const execute = useMutation({
    mutationFn: (simulate: boolean) =>
      api.post<Run>(simulate ? "/finance/automation/simulate" : "/finance/automation/run"),
    onSuccess: (response, simulate) => {
      setRun(response.data);
      if (!simulate) {
        toast.success("Tareas del día aplicadas");
        client.invalidateQueries({ queryKey: ["finance"] });
      }
    },
    onError: error => toast.error(apiMessage(error)),
  });
  if (policy.isPending || !draft) return <Spinner />;
  if (policy.isError) return <p className="form-error">{apiMessage(policy.error)}</p>;

  const set = (key: keyof Policy, value: string | boolean) =>
    setDraft(current => (current ? { ...current, [key]: value } : current));
  const check = (key: keyof Policy, label: string) => (
    <label className="policy-toggle">
      <input
        type="checkbox"
        disabled={!canEdit}
        checked={Boolean(draft[key])}
        onChange={event => set(key, event.target.checked)}
      />
      {label}
    </label>
  );
  const number = (key: keyof Policy, label: string, step = "1") => (
    <label className="form-field">
      <span>{label}</span>
      <input
        type="number"
        min={0}
        step={step}
        disabled={!canEdit}
        value={String(draft[key])}
        onChange={event => set(key, event.target.value)}
      />
    </label>
  );
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };

  return (
    <div className="page policy-page">
      <Link to="/finance" className="back-link">
        <ArrowLeft /> Cuentas
      </Link>
      <header className="page-header">
        <div>
          <span className="kicker">Finanzas · Reglas automáticas</span>
          <h1>Política financiera</h1>
          <p className="muted">
            Todo empieza desactivado. Un proceso diario aplica lo que actives; simúlalo antes para
            ver a quién afectaría.
          </p>
        </div>
      </header>
      <form className="policy-grid" onSubmit={submit}>
        <Section title="Generación programada" kicker="Planes de cobro">
          {check("auto_billing_enabled", "Generar las mensualidades automáticamente")}
          {number("billing_lead_days", "Días antes del vencimiento")}
        </Section>
        <Section title="Descuento por hermanos" kicker="Familias">
          {check("sibling_discount_enabled", "Aplicar a los planes marcados")}
          <p className="muted">
            Familia: estudiantes con el mismo tutor «responsable de pago». El hijo con la
            mensualidad más alta paga completo.
          </p>
          {number("sibling_second_percent", "2.º hijo (%)", "0.01")}
          {number("sibling_third_percent", "3.º en adelante (%)", "0.01")}
        </Section>
        <Section title="Recargo por mora" kicker="Una vez por cuota">
          {check("late_fee_enabled", "Aplicar recargo a cuotas vencidas")}
          {number("grace_days", "Días de gracia")}
          <label className="form-field">
            <span>Tipo de recargo</span>
            <select
              disabled={!canEdit}
              value={String(draft.late_fee_kind)}
              onChange={event => set("late_fee_kind", event.target.value)}
            >
              <option value="percent">Porcentaje de la cuota</option>
              <option value="fixed">Monto fijo (RD$)</option>
            </select>
          </label>
          {number(
            "late_fee_value",
            draft.late_fee_kind === "fixed" ? "Monto RD$" : "Porcentaje",
            "0.01",
          )}
        </Section>
        <Section title="Bloqueo automático" kicker="Inscripción y grupos">
          {check("hold_enabled", "Bloquear cuentas con atraso")}
          {number("hold_after_days", "Días de atraso")}
          {number("hold_min_amount", "Monto vencido mínimo (RD$)", "0.01")}
          <p className="muted">
            Se levanta solo al ponerse al día. Los bloqueos puestos a mano no se tocan.
          </p>
        </Section>
        {canEdit && (
          <div className="policy-actions">
            <label className="form-field">
              <span>Motivo del cambio</span>
              <input
                required
                minLength={3}
                maxLength={250}
                value={reason}
                onChange={event => setReason(event.target.value)}
              />
            </label>
            <Button type="submit" disabled={save.isPending || reason.trim().length < 3}>
              <Save size={16} /> Guardar política
            </Button>
          </div>
        )}
      </form>
      {canEdit && (
        <Section title="Proceso diario" kicker="Cada mañana">
          <p className="muted">
            Se ejecuta con <code>python -m scripts.run_billing</code>. Puedes simularlo o aplicarlo
            ahora.
          </p>
          <div className="policy-run-actions">
            <Button
              variant="secondary"
              disabled={execute.isPending}
              onClick={() => execute.mutate(true)}
            >
              <TestTube2 size={16} /> Simular hoy
            </Button>
            <Button
              disabled={execute.isPending}
              onClick={async () => {
                if (await confirmAction("¿Aplicar ahora los cobros, recargos y bloqueos del día?"))
                  execute.mutate(false);
              }}
            >
              <PlayCircle size={16} /> Aplicar ahora
            </Button>
          </div>
          {run && (
            <div className="policy-result" role="status">
              <strong>
                {run.simulated ? "Simulación" : "Aplicado"} · {run.today}
              </strong>
              <ul>
                <li>{run.billing_runs.length} cobros generados</li>
                <li>{run.sibling_discounts} descuentos por hermanos</li>
                <li>{run.late_fees.length} recargos por mora</li>
                <li>
                  {run.holds_set.length} bloqueos
                  {run.holds_set.length > 0 && `: ${run.holds_set.join(", ")}`}
                </li>
                <li>
                  {run.holds_lifted.length} desbloqueos
                  {run.holds_lifted.length > 0 && `: ${run.holds_lifted.join(", ")}`}
                </li>
              </ul>
            </div>
          )}
        </Section>
      )}
    </div>
  );
}
