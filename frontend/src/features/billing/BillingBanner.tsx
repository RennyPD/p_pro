import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Info } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { useAccess } from "../../lib/permissions";
import "./billing.css";

type Status = ApiSchema<"BillingStatus">;

const days = (count: number | null | undefined) => (count === 1 ? "1 día" : `${count ?? 0} días`);

/** Trial, overdue payment and read-only notices in the app frame (Fase 4 D3). */
export function BillingBanner() {
  const access = useAccess();
  const status = useQuery({
    queryKey: ["billing", "status"],
    queryFn: () => api.get<Status>("/billing/status").then(r => r.data),
    staleTime: 5 * 60_000,
  });
  const data = status.data;
  if (!data) return null;
  const manager = access.institution && access.can("billing.manage");
  const link = manager ? (
    <Link to="/billing" className="billing-banner__link">
      Ir a Plan y facturación
    </Link>
  ) : null;
  if (data.read_only)
    return (
      <div className="billing-banner billing-banner--danger" role="alert">
        <AlertTriangle aria-hidden />
        <p>
          La institución está en modo de solo lectura por falta de pago: puedes consultar y
          exportar, pero no registrar cambios.
          {manager && data.days_left != null
            ? ` Si no se regulariza en ${days(data.days_left)}, el acceso se suspenderá.`
            : ""}
        </p>
        {link}
      </div>
    );
  if (!manager) return null;
  if (data.status === "past_due")
    return (
      <div className="billing-banner billing-banner--warning" role="status">
        <AlertTriangle aria-hidden />
        <p>
          No pudimos cobrar el plan de Nexo. Tienes {days(data.days_left)} antes de pasar a modo de
          solo lectura.
        </p>
        {link}
      </div>
    );
  if (data.status === "trialing" && data.days_left != null && data.days_left <= 7)
    return (
      <div className="billing-banner" role="status">
        <Info aria-hidden />
        <p>
          {data.days_left === 0
            ? "Tu prueba gratuita termina hoy."
            : `Tu prueba gratuita termina en ${days(data.days_left)}.`}{" "}
          Elige un plan para seguir sin interrupciones.
        </p>
        {link}
      </div>
    );
  return null;
}
