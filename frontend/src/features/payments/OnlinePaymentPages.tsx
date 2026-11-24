import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, FlaskConical, XCircle } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { formatMoney } from "../../lib/format";
import type { OnlineIntent } from "./onlinePayments";
import "./payments.css";

const complete = (id: string, params: Record<string, string>) =>
  api.post<OnlineIntent>(`/online-payments/${id}/complete`, { params }).then(r => r.data);

/** Where the bank sends the payer back: the server verifies the signed answer. */
export function OnlinePaymentResultPage() {
  const [params] = useSearchParams();
  const id = params.get("id") ?? "";
  const sent = useRef(false);
  const result = useMutation({ mutationFn: () => complete(id, Object.fromEntries(params)) });
  useEffect(() => {
    if (id && !sent.current) {
      sent.current = true;
      result.mutate();
    }
  }, [id, result]);
  const data = result.data;
  return (
    <main className="online-result">
      <section className="auth-card online-result__card">
        {!id ? (
          <p className="form-error">Falta la referencia del pago.</p>
        ) : result.isPending || result.isIdle ? (
          <Spinner label="Confirmando el pago con el banco" />
        ) : result.isError ? (
          <>
            <XCircle className="online-result__icon is-low" aria-hidden />
            <h2>No pudimos confirmar el pago</h2>
            <p>{apiMessage(result.error)}</p>
            <p className="muted">
              Si el banco te cobró, la institución lo verá en su conciliación. Guarda esta
              referencia: {id.slice(0, 12)}.
            </p>
          </>
        ) : data?.status === "approved" ? (
          <>
            <CheckCircle2 className="online-result__icon is-ok" aria-hidden />
            <h2>Pago aprobado</h2>
            <p>
              Recibimos {formatMoney(Number(data.amount))}. Autorización{" "}
              {data.authorization_code ?? "—"}.
            </p>
            <p>Recibo: {data.receipts.join(", ")}</p>
          </>
        ) : (
          <>
            <XCircle className="online-result__icon is-low" aria-hidden />
            <h2>El pago no se completó</h2>
            <p>{data?.message ?? "El banco no aprobó el pago. No se cobró nada."}</p>
          </>
        )}
        <Link to="/">Volver a Nexo</Link>
      </section>
    </main>
  );
}

/** The test gateway's page (development and demos): approve or decline. */
export function SandboxGatewayPage() {
  const [params] = useSearchParams();
  const id = params.get("id") ?? "";
  const navigate = useNavigate();
  const answer = useMutation({
    mutationFn: (outcome: "approved" | "declined") => complete(id, { outcome }),
    onSuccess: () => navigate(`/pagos/resultado?id=${id}`),
  });
  return (
    <main className="online-result">
      <section className="auth-card online-result__card">
        <FlaskConical className="online-result__icon" aria-hidden />
        <h2>Banco de prueba</h2>
        <p>No se cobra nada: simula la respuesta del banco.</p>
        <div className="form-actions">
          <Button disabled={answer.isPending} onClick={() => answer.mutate("approved")}>
            Aprobar pago
          </Button>
          <Button
            variant="danger"
            disabled={answer.isPending}
            onClick={() => answer.mutate("declined")}
          >
            Rechazar pago
          </Button>
        </div>
        {answer.error && (
          <p className="form-error" role="alert">
            {apiMessage(answer.error)}
          </p>
        )}
      </section>
    </main>
  );
}
