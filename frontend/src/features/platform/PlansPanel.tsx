import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Layers } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Badge, Button, Modal, Spinner } from "../../components/ui";
import { apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { platformApi } from "../../lib/platformApi";
import { usePlans } from "./platformData";

type Plan = ApiSchema<"PlanOut">;
type Institution = ApiSchema<"InstitutionOut">;

const limitText = (value: number | null | undefined, unit = "") =>
  value == null ? "Sin límite" : `${value.toLocaleString("es-DO")}${unit}`;

/** Plans and their limits; prices are edited here, never in code (Fase 4 D1). */
export function PlansPanel() {
  const plans = usePlans();
  const [editing, setEditing] = useState<Plan | "new" | null>(null);
  return (
    <section className="panel platform-audit" aria-labelledby="plans-title">
      <div className="platform-section-header">
        <h2 id="plans-title">
          <Layers size={18} /> Planes
        </h2>
        <Button variant="secondary" onClick={() => setEditing("new")}>
          Nuevo plan
        </Button>
      </div>
      {plans.isLoading ? (
        <Spinner label="Cargando planes" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Plan</th>
                <th>Mensual</th>
                <th>Anual</th>
                <th>Estudiantes</th>
                <th>Personal</th>
                <th>Archivos</th>
                <th>Estado</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {plans.data?.map(plan => (
                <tr key={plan.plan_id}>
                  <td>
                    <strong>{plan.name}</strong>
                    <div className="muted">{plan.code}</div>
                  </td>
                  <td>
                    {plan.monthly_price} {plan.currency}
                  </td>
                  <td>
                    {plan.yearly_price} {plan.currency}
                  </td>
                  <td>{limitText(plan.max_students)}</td>
                  <td>{limitText(plan.max_staff)}</td>
                  <td>{limitText(plan.storage_gb, " GB")}</td>
                  <td>
                    {!plan.active ? (
                      <Badge tone="neutral">Inactivo</Badge>
                    ) : plan.public ? (
                      <Badge tone="success">Público</Badge>
                    ) : (
                      <Badge tone="info">A medida</Badge>
                    )}
                  </td>
                  <td>
                    <Button variant="ghost" onClick={() => setEditing(plan)}>
                      Editar
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && (
        <PlanEditor plan={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
      )}
    </section>
  );
}

const optionalNumber = (value: FormDataEntryValue | null) => {
  const text = String(value ?? "").trim();
  return text ? Number(text) : null;
};

function PlanEditor({ plan, onClose }: { plan: Plan | null; onClose: () => void }) {
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      plan
        ? platformApi.put(`/platform/plans/${plan.code}`, body)
        : platformApi.post("/platform/plans", body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["platform"] });
      onClose();
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    save.mutate({
      ...(plan ? {} : { code: String(form.get("code")).trim() }),
      name: String(form.get("name")).trim(),
      description: String(form.get("description") ?? "").trim(),
      currency: String(form.get("currency")).trim().toUpperCase(),
      monthly_price: String(form.get("monthly_price")),
      yearly_price: String(form.get("yearly_price")),
      max_students: optionalNumber(form.get("max_students")),
      max_staff: optionalNumber(form.get("max_staff")),
      storage_gb: optionalNumber(form.get("storage_gb")),
      public: form.get("public") === "on",
      active: form.get("active") === "on",
      sort_order: Number(form.get("sort_order") || 0),
      provider_monthly_price: String(form.get("provider_monthly_price") ?? "").trim() || null,
      provider_yearly_price: String(form.get("provider_yearly_price") ?? "").trim() || null,
    });
  }
  return (
    <Modal
      title={plan ? `Editar ${plan.name}` : "Nuevo plan"}
      description="Los límites vacíos significan «sin límite». Se permite un 10 % de margen antes de bloquear altas."
      onClose={onClose}
    >
      <form className="platform-form" onSubmit={submit}>
        {!plan && (
          <label className="form-field">
            <span>Código</span>
            <input name="code" required pattern="[a-z0-9-]+" placeholder="profesional" />
          </label>
        )}
        <label className="form-field">
          <span>Nombre</span>
          <input name="name" required defaultValue={plan?.name} />
        </label>
        <label className="form-field">
          <span>Descripción</span>
          <input name="description" defaultValue={plan?.description} />
        </label>
        <div className="platform-form-row">
          <label className="form-field">
            <span>Moneda</span>
            <input name="currency" required maxLength={3} defaultValue={plan?.currency ?? "USD"} />
          </label>
          <label className="form-field">
            <span>Precio mensual</span>
            <input
              name="monthly_price"
              type="number"
              min="0"
              step="0.01"
              required
              defaultValue={plan?.monthly_price ?? "0"}
            />
          </label>
          <label className="form-field">
            <span>Precio anual</span>
            <input
              name="yearly_price"
              type="number"
              min="0"
              step="0.01"
              required
              defaultValue={plan?.yearly_price ?? "0"}
            />
          </label>
        </div>
        <div className="platform-form-row">
          <label className="form-field">
            <span>Estudiantes activos</span>
            <input
              name="max_students"
              type="number"
              min="1"
              defaultValue={plan?.max_students ?? ""}
            />
          </label>
          <label className="form-field">
            <span>Cuentas del personal</span>
            <input name="max_staff" type="number" min="1" defaultValue={plan?.max_staff ?? ""} />
          </label>
          <label className="form-field">
            <span>Archivos (GB)</span>
            <input name="storage_gb" type="number" min="1" defaultValue={plan?.storage_gb ?? ""} />
          </label>
        </div>
        <div className="platform-form-row">
          <label className="form-field">
            <span>Precio mensual en el proveedor</span>
            <input
              name="provider_monthly_price"
              defaultValue={plan?.provider_monthly_price ?? ""}
            />
          </label>
          <label className="form-field">
            <span>Precio anual en el proveedor</span>
            <input name="provider_yearly_price" defaultValue={plan?.provider_yearly_price ?? ""} />
          </label>
          <label className="form-field">
            <span>Orden</span>
            <input name="sort_order" type="number" defaultValue={plan?.sort_order ?? 0} />
          </label>
        </div>
        <label className="platform-check">
          <input name="public" type="checkbox" defaultChecked={plan?.public ?? true} /> Se ofrece en
          el registro y en «Plan y facturación»
        </label>
        <label className="platform-check">
          <input name="active" type="checkbox" defaultChecked={plan?.active ?? true} /> Activo
        </label>
        {save.error && (
          <div className="form-error" role="alert">
            {apiMessage(save.error)}
          </div>
        )}
        <div className="form-actions">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={save.isPending}>Guardar plan</Button>
        </div>
      </form>
    </Modal>
  );
}

/** Assign a plan to an institution (sales agreements, custom plans, trials). */
export function ChangePlan({
  institution,
  onClose,
}: {
  institution: Institution;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const plans = usePlans();
  const change = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      platformApi.put(`/platform/institutions/${institution.institution_id}/subscription`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["platform"] });
      onClose();
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    change.mutate({
      plan_code: form.get("plan_code"),
      interval: form.get("interval"),
      trial_days: optionalNumber(form.get("trial_days")),
      reason: String(form.get("reason")).trim(),
    });
  }
  return (
    <Modal
      title={`Plan de ${institution.name}`}
      description="El cambio queda en la auditoría de la plataforma."
      onClose={onClose}
    >
      <form className="platform-form" onSubmit={submit}>
        <label className="form-field">
          <span>Plan</span>
          <select name="plan_code" defaultValue={institution.subscription?.plan_code}>
            {plans.data
              ?.filter(plan => plan.active)
              .map(plan => (
                <option key={plan.code} value={plan.code}>
                  {plan.name}
                </option>
              ))}
          </select>
        </label>
        <label className="form-field">
          <span>Facturación</span>
          <select name="interval" defaultValue={institution.subscription?.interval ?? "monthly"}>
            <option value="monthly">Mensual</option>
            <option value="yearly">Anual</option>
          </select>
        </label>
        <label className="form-field">
          <span>Días de prueba (opcional)</span>
          <input name="trial_days" type="number" min="1" max="365" />
        </label>
        <label className="form-field">
          <span>Motivo</span>
          <textarea name="reason" required minLength={5} />
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
          <Button disabled={change.isPending}>Guardar</Button>
        </div>
      </form>
    </Modal>
  );
}
