import { useMutation, useQuery } from "@tanstack/react-query";
import { CreditCard, Receipt } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Badge, Button, EmptyState, Spinner } from "../../components/ui";
import { Progress, Section } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDate } from "../../lib/format";
import { billingStatus } from "./billingLabels";
import "./billing.css";

type Overview = ApiSchema<"BillingOverview">;
type Invoice = ApiSchema<"Invoice">;
type Limit = ApiSchema<"Limit">;
type PlanOption = ApiSchema<"PlanOption">;

function Usage({ label, limit, unit = "" }: { label: string; limit: Limit; unit?: string }) {
  const percent = limit.limit ? (limit.used / limit.limit) * 100 : 0;
  const tone = percent >= 100 ? "danger" : percent >= 85 ? "warning" : "info";
  return (
    <div className="billing-usage">
      <div className="billing-usage__text">
        <span>{label}</span>
        <strong>
          {limit.used.toLocaleString("es-DO")}
          {unit}
          {limit.limit != null
            ? ` de ${limit.limit.toLocaleString("es-DO")}${unit}`
            : " · sin límite"}
        </strong>
      </div>
      {limit.limit != null && <Progress value={percent} label={label} tone={tone} />}
    </div>
  );
}

/** «Plan y facturación»: the institution's Nexo plan, usage and payments (Fase 4 D2). */
export function BillingPage() {
  const [params] = useSearchParams();
  const [interval, setInterval] = useState<"monthly" | "yearly">("monthly");
  const overview = useQuery({
    queryKey: ["billing", "overview"],
    queryFn: () => api.get<Overview>("/billing/subscription").then(r => r.data),
  });
  const invoices = useQuery({
    queryKey: ["billing", "invoices"],
    queryFn: () => api.get<Invoice[]>("/billing/invoices").then(r => r.data),
  });
  const go = (url: string) => window.location.assign(url);
  const checkout = useMutation({
    mutationFn: (plan: PlanOption) =>
      api
        .post<{ url: string }>("/billing/checkout", { plan_code: plan.code, interval })
        .then(r => r.data.url),
    onSuccess: go,
  });
  const portal = useMutation({
    mutationFn: () => api.post<{ url: string }>("/billing/portal").then(r => r.data.url),
    onSuccess: go,
  });
  if (overview.isPending) return <Spinner label="Cargando tu plan" />;
  if (overview.isError)
    return (
      <p className="form-error" role="alert">
        {apiMessage(overview.error)}
      </p>
    );
  const data = overview.data;
  const status = billingStatus[data.status] ?? { label: data.status, tone: "neutral" as const };
  const result = params.get("resultado");
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="kicker">Configuración</span>
          <h1>Plan y facturación</h1>
          <p>Tu plan de Nexo, lo que usas de él y los pagos.</p>
        </div>
      </header>
      {result === "ok" && (
        <div className="billing-notice billing-notice--success" role="status">
          Pago recibido. Tu plan ya está activo.
        </div>
      )}
      {result === "cancelado" && (
        <div className="billing-notice" role="status">
          No se completó el pago. Tu plan sigue igual.
        </div>
      )}
      <Section
        title={data.plan ? `Plan ${data.plan.name}` : "Sin plan"}
        kicker="Plan actual"
        icon={<CreditCard size={18} />}
        action={<Badge tone={status.tone}>{status.label}</Badge>}
      >
        <p className="muted billing-dates">
          {data.status === "trialing" && data.trial_ends_at
            ? `La prueba gratuita termina el ${formatDate(data.trial_ends_at)}.`
            : data.current_period_end
              ? `Próxima renovación: ${formatDate(data.current_period_end)}.`
              : "Plan asignado por el equipo de Nexo."}
        </p>
        <div className="billing-usages">
          <Usage label="Estudiantes activos" limit={data.students} />
          <Usage label="Cuentas del personal" limit={data.staff} />
          <Usage label="Archivos" limit={data.storage_gb} unit=" GB" />
        </div>
        {data.has_payment_method && data.online_checkout && (
          <Button variant="secondary" disabled={portal.isPending} onClick={() => portal.mutate()}>
            Gestionar método de pago
          </Button>
        )}
        {portal.error && (
          <p className="form-error" role="alert">
            {apiMessage(portal.error)}
          </p>
        )}
      </Section>
      <Section
        title="Cambiar de plan"
        kicker="Planes"
        action={
          <div className="billing-interval" role="group" aria-label="Facturación">
            <Button
              variant={interval === "monthly" ? "primary" : "ghost"}
              aria-pressed={interval === "monthly"}
              onClick={() => setInterval("monthly")}
            >
              Mensual
            </Button>
            <Button
              variant={interval === "yearly" ? "primary" : "ghost"}
              aria-pressed={interval === "yearly"}
              onClick={() => setInterval("yearly")}
            >
              Anual
            </Button>
          </div>
        }
      >
        {!data.online_checkout && (
          <p className="billing-notice">
            El pago en línea aún no está disponible. Para cambiar de plan, escribe al equipo de
            Nexo.
          </p>
        )}
        <div className="billing-plans">
          {data.plans.map(plan => {
            const current = data.plan?.code === plan.code && data.status === "active";
            return (
              <article key={plan.code} className="billing-plan" aria-label={`Plan ${plan.name}`}>
                <h3>{plan.name}</h3>
                <p className="muted">{plan.description}</p>
                <p className="billing-plan__price">
                  <strong>
                    {interval === "yearly" ? plan.yearly_price : plan.monthly_price} {plan.currency}
                  </strong>
                  <span>{interval === "yearly" ? " al año" : " al mes"}</span>
                </p>
                <ul>
                  <li>
                    {plan.max_students != null
                      ? `Hasta ${plan.max_students.toLocaleString("es-DO")} estudiantes activos`
                      : "Estudiantes sin límite"}
                  </li>
                  <li>
                    {plan.max_staff != null
                      ? `${plan.max_staff.toLocaleString("es-DO")} cuentas del personal`
                      : "Personal sin límite"}
                  </li>
                  <li>
                    {plan.storage_gb != null
                      ? `${plan.storage_gb} GB de archivos`
                      : "Archivos sin límite"}
                  </li>
                </ul>
                <Button
                  disabled={current || !data.online_checkout || checkout.isPending}
                  onClick={() => checkout.mutate(plan)}
                >
                  {current ? "Plan actual" : `Elegir ${plan.name}`}
                </Button>
              </article>
            );
          })}
        </div>
        {checkout.error && (
          <p className="form-error" role="alert">
            {apiMessage(checkout.error)}
          </p>
        )}
      </Section>
      <Section title="Facturas" kicker="Pagos" icon={<Receipt size={18} />}>
        {invoices.isPending ? (
          <Spinner label="Cargando facturas" />
        ) : !invoices.data?.length ? (
          <EmptyState
            icon={<Receipt />}
            title="Sin facturas"
            description="Las facturas aparecerán aquí después del primer pago."
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Factura</th>
                  <th>Fecha</th>
                  <th>Monto</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {invoices.data.map(invoice => (
                  <tr key={invoice.number}>
                    <td>
                      {invoice.url ? (
                        <a href={invoice.url} target="_blank" rel="noreferrer">
                          {invoice.number}
                        </a>
                      ) : (
                        invoice.number
                      )}
                    </td>
                    <td>{invoice.date ? formatDate(invoice.date) : "—"}</td>
                    <td>
                      {invoice.amount} {invoice.currency}
                    </td>
                    <td>{invoice.status === "paid" ? "Pagada" : invoice.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}
