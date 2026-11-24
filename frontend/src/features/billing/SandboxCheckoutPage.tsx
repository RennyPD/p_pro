import { useMutation, useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button, Spinner } from "../../components/ui";
import { Section } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import "./billing.css";

type PlanOption = ApiSchema<"PlanOption">;

/** Fake payment page of the sandbox provider (development and demos only). */
export function SandboxCheckoutPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const session = useQuery({
    queryKey: ["billing", "sandbox", token],
    queryFn: () =>
      api
        .get<{ plan: PlanOption; interval: string }>("/billing/sandbox/session", {
          params: { token },
        })
        .then(r => r.data),
    enabled: Boolean(token),
    retry: false,
  });
  const complete = useMutation({
    mutationFn: (outcome: "paid" | "failed") =>
      api.post("/billing/sandbox/complete", { token, outcome }),
    onSuccess: (_data, outcome) =>
      navigate(outcome === "paid" ? "/billing?resultado=ok" : "/billing?resultado=cancelado"),
  });
  if (session.isPending && token) return <Spinner label="Preparando el pago de prueba" />;
  if (!token || session.isError)
    return (
      <div className="page">
        <p className="form-error" role="alert">
          {session.error ? apiMessage(session.error) : "Falta el enlace del pago de prueba."}
        </p>
        <Link to="/billing">Volver a Plan y facturación</Link>
      </div>
    );
  const { plan, interval } = session.data!;
  const yearly = interval === "yearly";
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="kicker">Modo de prueba</span>
          <h1>Pago de prueba</h1>
          <p>No se cobra nada: simula la respuesta del proveedor de pagos.</p>
        </div>
      </header>
      <Section title={`Plan ${plan.name}`} icon={<FlaskConical size={18} />}>
        <p className="billing-plan__price">
          <strong>
            {yearly ? plan.yearly_price : plan.monthly_price} {plan.currency}
          </strong>
          <span>{yearly ? " al año" : " al mes"}</span>
        </p>
        <div className="form-actions">
          <Button disabled={complete.isPending} onClick={() => complete.mutate("paid")}>
            Simular pago aprobado
          </Button>
          <Button
            variant="danger"
            disabled={complete.isPending}
            onClick={() => complete.mutate("failed")}
          >
            Simular pago rechazado
          </Button>
        </div>
        {complete.error && (
          <p className="form-error" role="alert">
            {apiMessage(complete.error)}
          </p>
        )}
      </Section>
    </div>
  );
}
