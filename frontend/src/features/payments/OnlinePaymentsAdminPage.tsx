import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCard, Settings2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { Section } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import { formatDateTime, formatMoney } from "../../lib/format";
import { useAccess } from "../../lib/permissions";
import "./payments.css";

type Row = {
  id: string;
  status: string;
  amount: string;
  gateway: string;
  authorization_code: string | null;
  message: string | null;
  receipts: string[];
  created_at: string;
  payer: string;
  students: { student_id: number; name: string; amount: string }[];
  provider_reference: string | null;
  overpaid: boolean;
};
type Config = {
  enabled: boolean;
  gateway: string;
  merchant_id: string;
  merchant_name: string;
  min_amount: string;
  environment: string;
  auth_key: string;
  terminal: string;
  merchant_type: string;
  gateways: string[];
};

const size = 25;
const statusLabels: Record<
  string,
  { label: string; tone: "success" | "info" | "warning" | "danger" | "neutral" }
> = {
  created: { label: "Creado", tone: "neutral" },
  pending: { label: "En el banco", tone: "info" },
  approved: { label: "Aprobado", tone: "success" },
  declined: { label: "Rechazado", tone: "neutral" },
  expired: { label: "Sin respuesta", tone: "warning" },
  error: { label: "Error", tone: "danger" },
};
const gatewayLabels: Record<string, string> = {
  sandbox: "Prueba (sin cobro real)",
  azul: "Azul",
  cardnet: "CardNet",
};

/** Online payments of the institution: gateway, reconciliation and resolution (Fase 4 E5). */
export function OnlinePaymentsAdminPage() {
  const access = useAccess();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [resolving, setResolving] = useState<Row | null>(null);
  const rows = useQuery({
    queryKey: ["online-payments", status, page],
    queryFn: () =>
      api
        .get<Row[]>("/online-payments", {
          params: { status: status || undefined, skip: page * size, limit: size },
        })
        .then(r => ({ rows: r.data, total: Number(r.headers["x-total-count"] ?? r.data.length) })),
  });
  const total = rows.data?.total ?? 0;
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="kicker">Finanzas</span>
          <h1>Pagos en línea</h1>
          <p>Pagos con tarjeta de las familias, con las referencias del banco para conciliar.</p>
        </div>
      </header>
      {access.can("finance.manage") && <GatewaySettings />}
      <Section
        title="Pagos"
        icon={<CreditCard size={18} />}
        action={
          <label className="form-field online-filter">
            <span>Estado</span>
            <select
              value={status}
              onChange={event => {
                setStatus(event.target.value);
                setPage(0);
              }}
            >
              <option value="">Todos</option>
              {Object.entries(statusLabels).map(([value, item]) => (
                <option key={value} value={value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        }
      >
        {rows.isPending ? (
          <Spinner label="Cargando pagos" />
        ) : rows.isError ? (
          <p className="form-error" role="alert">
            {apiMessage(rows.error)}
          </p>
        ) : !rows.data.rows.length ? (
          <EmptyState
            icon={<CreditCard />}
            title="Sin pagos en línea"
            description="Aquí aparecerán los pagos con tarjeta de las familias."
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Estudiantes</th>
                  <th>Monto</th>
                  <th>Estado</th>
                  <th>Banco</th>
                  <th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {rows.data.rows.map(row => {
                  const state = statusLabels[row.status] ?? statusLabels.created;
                  return (
                    <tr key={row.id}>
                      <td>
                        {formatDateTime(row.created_at)}
                        <div className="muted">{row.payer}</div>
                      </td>
                      <td>
                        {row.students.map(student => (
                          <div key={student.student_id}>
                            {student.name} · {formatMoney(Number(student.amount))}
                          </div>
                        ))}
                      </td>
                      <td>{formatMoney(Number(row.amount))}</td>
                      <td>
                        <Badge tone={state.tone}>{state.label}</Badge>
                        {row.overpaid && <div className="is-low">Saldo a favor por resolver</div>}
                        {row.receipts.length > 0 && (
                          <div className="muted">{row.receipts.join(", ")}</div>
                        )}
                      </td>
                      <td>
                        {gatewayLabels[row.gateway] ?? row.gateway}
                        <div className="muted">
                          {row.authorization_code ? `Aut. ${row.authorization_code}` : ""}
                          {row.provider_reference ? ` · Ref. ${row.provider_reference}` : ""}
                        </div>
                        <div className="muted">Orden {row.id.slice(0, 15)}</div>
                      </td>
                      <td>
                        {["created", "pending", "expired", "error"].includes(row.status) &&
                          access.can("finance.supervise") && (
                            <Button variant="secondary" onClick={() => setResolving(row)}>
                              Resolver
                            </Button>
                          )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <Button
            variant="secondary"
            disabled={page === 0 || rows.isFetching}
            onClick={() => setPage(current => current - 1)}
          >
            Anterior
          </Button>
          <span className="pagination__page">
            Página {page + 1} de {Math.max(1, Math.ceil(total / size))}
          </span>
          <Button
            variant="secondary"
            disabled={(page + 1) * size >= total || rows.isFetching}
            onClick={() => setPage(current => current + 1)}
          >
            Siguiente
          </Button>
        </div>
      </Section>
      {resolving && <ResolveDialog row={resolving} onClose={() => setResolving(null)} />}
    </div>
  );
}

function GatewaySettings() {
  const client = useQueryClient();
  const config = useQuery({
    queryKey: ["online-payments", "config"],
    queryFn: () => api.get<Config>("/online-payments/config/gateway").then(r => r.data),
  });
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.put("/online-payments/config/gateway", body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["online-payments"] }),
  });
  if (config.isPending) return <Spinner label="Cargando la pasarela" />;
  if (config.isError)
    return (
      <p className="form-error" role="alert">
        {apiMessage(config.error)}
      </p>
    );
  const data = config.data;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    save.mutate({
      enabled: form.get("enabled") === "on",
      gateway: text("gateway"),
      merchant_id: text("merchant_id"),
      merchant_name: text("merchant_name"),
      min_amount: text("min_amount") || "100.00",
      environment: text("environment"),
      auth_key: text("auth_key") || null,
      terminal: text("terminal") || null,
      merchant_type: text("merchant_type") || null,
    });
  }
  return (
    <Section title="Pasarela de pago" icon={<Settings2 size={18} />}>
      <p className="muted">
        El dinero llega directo a la cuenta de comercio de la institución. Las claves se guardan
        cifradas y no se vuelven a mostrar.
      </p>
      <form className="online-config" onSubmit={submit}>
        <label className="online-check">
          <input name="enabled" type="checkbox" defaultChecked={data.enabled} /> Recibir pagos en
          línea
        </label>
        <label className="form-field">
          <span>Pasarela</span>
          <select name="gateway" defaultValue={data.gateway}>
            {data.gateways.map(gateway => (
              <option key={gateway} value={gateway}>
                {gatewayLabels[gateway] ?? gateway}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Ambiente</span>
          <select name="environment" defaultValue={data.environment}>
            <option value="test">Pruebas del banco</option>
            <option value="live">Producción</option>
          </select>
        </label>
        <label className="form-field">
          <span>Número de comercio</span>
          <input name="merchant_id" defaultValue={data.merchant_id} />
        </label>
        <label className="form-field">
          <span>Nombre del comercio</span>
          <input name="merchant_name" defaultValue={data.merchant_name} />
        </label>
        <label className="form-field">
          <span>Pago mínimo (RD$)</span>
          <input
            name="min_amount"
            type="number"
            min="1"
            step="0.01"
            defaultValue={data.min_amount}
          />
        </label>
        <label className="form-field">
          <span>AuthKey de Azul {data.auth_key && `(guardada: ${data.auth_key})`}</span>
          <input name="auth_key" type="password" autoComplete="off" placeholder="Sin cambios" />
        </label>
        <label className="form-field">
          <span>Terminal de CardNet {data.terminal && `(guardada: ${data.terminal})`}</span>
          <input name="terminal" type="password" autoComplete="off" placeholder="Sin cambios" />
        </label>
        <label className="form-field">
          <span>Tipo de comercio (opcional)</span>
          <input name="merchant_type" defaultValue={data.merchant_type} />
        </label>
        {save.error && (
          <div className="form-error" role="alert">
            {apiMessage(save.error)}
          </div>
        )}
        {save.isSuccess && (
          <p className="online-saved" role="status">
            Pasarela guardada.
          </p>
        )}
        <div className="form-actions">
          <Button disabled={save.isPending}>Guardar pasarela</Button>
        </div>
      </form>
    </Section>
  );
}

function ResolveDialog({ row, onClose }: { row: Row; onClose: () => void }) {
  const client = useQueryClient();
  const resolve = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(`/online-payments/${row.id}/resolve`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["online-payments"] });
      onClose();
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    resolve.mutate({
      outcome: form.get("outcome"),
      authorization_code: String(form.get("authorization_code") ?? "").trim() || null,
      reason: String(form.get("reason") ?? "").trim(),
    });
  }
  return (
    <Modal
      title="Resolver pago en línea"
      description={`Orden ${row.id.slice(0, 15)} · ${formatMoney(Number(row.amount))}. Usa lo que muestra el portal del banco.`}
      onClose={onClose}
    >
      <form className="online-config" onSubmit={submit}>
        <label className="form-field">
          <span>Resultado en el banco</span>
          <select name="outcome" defaultValue="approved">
            <option value="approved">Aprobado</option>
            <option value="declined">No aprobado</option>
          </select>
        </label>
        <label className="form-field">
          <span>Código de autorización</span>
          <input name="authorization_code" />
        </label>
        <label className="form-field">
          <span>Motivo</span>
          <textarea name="reason" required minLength={5} />
        </label>
        {resolve.error && (
          <div className="form-error" role="alert">
            {apiMessage(resolve.error)}
          </div>
        )}
        <div className="form-actions">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={resolve.isPending}>Guardar resultado</Button>
        </div>
      </form>
    </Modal>
  );
}
