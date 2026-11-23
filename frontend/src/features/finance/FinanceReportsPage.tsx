import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { DocumentDownload } from "../../components/DocumentDownload";
import { EmptyState, Spinner } from "../../components/ui";
import { Chip, Metric, Section, Tabs } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDate, formatMoney, todayIso } from "../../lib/format";
import { useAccess } from "../../lib/permissions";
import "./finance-reports.css";

type Aging = ApiSchema<"AgingSummary">;
type AgingAccount = ApiSchema<"AgingAccount">;
type Income = ApiSchema<"IncomeReport">;
type Expected = ApiSchema<"ExpectedMonth">;
type CashierDay = ApiSchema<"CashierDay">;
type Tab = "aging" | "income" | "expected";

const BUCKETS = [
  ["d1_30", "1–30 días"],
  ["d31_60", "31–60"],
  ["d61_90", "61–90"],
  ["d90_plus", "Más de 90"],
] as const;
const money = (value: number) => formatMoney(Number(value));

/** Aging, income and expected vs collected (Fase 3 E). */
export function FinanceReportsPage() {
  const access = useAccess();
  const [tab, setTab] = useState<Tab>("aging");
  return (
    <div className="page reports-page">
      <Link to="/finance" className="back-link">
        <ArrowLeft /> Cuentas
      </Link>
      <header className="page-header">
        <div>
          <span className="kicker">Finanzas · Reportes</span>
          <h1>Reportes financieros</h1>
          <p className="muted">
            Morosidad por antigüedad, ingresos y cobro esperado contra cobrado.
          </p>
        </div>
      </header>
      {access.can("finance.collect") && <MyCash />}
      <Tabs
        label="Reportes"
        value={tab}
        onChange={setTab}
        panelId="finance-report-panel"
        items={[
          { key: "aging", label: "Morosidad" },
          { key: "income", label: "Ingresos" },
          { key: "expected", label: "Esperado y cobrado" },
        ]}
      />
      <div id="finance-report-panel" role="tabpanel">
        {tab === "aging" && <AgingReport />}
        {tab === "income" && <IncomeReport />}
        {tab === "expected" && <ExpectedReport />}
      </div>
    </div>
  );
}

function MyCash() {
  const cash = useQuery({
    queryKey: ["finance", "cashier-today"],
    queryFn: () => api.get<CashierDay>("/finance/cashier/today").then(r => r.data),
  });
  if (!cash.data) return null;
  return (
    <Section title="Mi caja de hoy" kicker={formatDate(cash.data.day)}>
      <div className="reports-metrics">
        <Metric label="Cobrado" value={money(cash.data.total)} />
        <Metric label="Pagos registrados" value={cash.data.payments} />
        {Object.entries(cash.data.by_method).map(([method, total]) => (
          <Metric key={method} label={method} value={money(total)} />
        ))}
      </div>
    </Section>
  );
}

function AgingReport() {
  const [term, setTerm] = useState("");
  const [page, setPage] = useState(0);
  const limit = 25;
  const summary = useQuery({
    queryKey: ["finance", "aging"],
    queryFn: () => api.get<Aging>("/finance/reports/aging").then(r => r.data),
  });
  const accounts = useQuery({
    queryKey: ["finance", "aging-accounts", term, page],
    queryFn: () =>
      api
        .get<AgingAccount[]>("/finance/reports/aging/accounts", {
          params: { q: term || undefined, skip: page * limit, limit },
        })
        .then(r => ({ rows: r.data, total: Number(r.headers["x-total-count"] ?? r.data.length) })),
  });
  if (summary.isPending) return <Spinner />;
  if (summary.isError) return <p className="form-error">{apiMessage(summary.error)}</p>;
  const data = summary.data;
  return (
    <>
      <div className="reports-metrics">
        <Metric
          label="Vencido total"
          value={money(data.totals.total - data.totals.current)}
          note={`${data.students_overdue} estudiantes con atraso`}
          tone={data.students_overdue ? "danger" : "success"}
        />
        {BUCKETS.map(([key, label]) => (
          <Metric key={key} label={label} value={money(data.totals[key])} />
        ))}
      </div>
      {data.groups.length > 0 && (
        <Section title="Por grupo o programa">
          <div className="reports-table-wrap">
            <table className="reports-table">
              <thead>
                <tr>
                  <th scope="col">Grupo</th>
                  <th scope="col">Estudiantes</th>
                  {BUCKETS.map(([key, label]) => (
                    <th key={key} scope="col">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.groups.map(group => (
                  <tr key={group.label}>
                    <th scope="row">{group.label}</th>
                    <td>{group.students}</td>
                    {BUCKETS.map(([key]) => (
                      <td key={key}>{money(group[key])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
      <Section
        title="Cuentas con atraso"
        action={
          <DocumentDownload
            path={`/finance/reports/aging/accounts.csv${term ? `?q=${encodeURIComponent(term)}` : ""}`}
            filename={`morosidad-${todayIso()}.csv`}
            label="Exportar CSV"
          />
        }
      >
        <label className="form-field reports-search">
          <span>Buscar estudiante</span>
          <input
            value={term}
            placeholder="Nombre o matrícula"
            onChange={event => {
              setTerm(event.target.value);
              setPage(0);
            }}
          />
        </label>
        {accounts.data?.rows.length === 0 && (
          <EmptyState
            icon={<Download />}
            title="Sin cuentas con atraso"
            description="Todo al día."
          />
        )}
        {accounts.data && accounts.data.rows.length > 0 && (
          <div className="reports-table-wrap">
            <table className="reports-table">
              <thead>
                <tr>
                  <th scope="col">Estudiante</th>
                  <th scope="col">Grupo</th>
                  <th scope="col">Familia</th>
                  {BUCKETS.map(([key, label]) => (
                    <th key={key} scope="col">
                      {label}
                    </th>
                  ))}
                  <th scope="col">Total</th>
                </tr>
              </thead>
              <tbody>
                {accounts.data.rows.map(row => (
                  <tr key={row.student_id}>
                    <th scope="row">
                      <Link to={`/finance/${row.student_id}`}>{row.student_name}</Link>
                      <small>
                        {row.enrollment_number}
                        {row.oldest_due && ` · desde ${formatDate(row.oldest_due)}`}
                      </small>
                      {row.financial_hold && <Chip tone="danger">Bloqueado</Chip>}
                    </th>
                    <td>{row.group}</td>
                    <td>{row.family ?? "—"}</td>
                    {BUCKETS.map(([key]) => (
                      <td key={key}>{row[key] ? money(row[key]) : "—"}</td>
                    ))}
                    <td>
                      <strong>{money(row.total)}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {accounts.data && accounts.data.total > limit && (
          <div className="reports-pager">
            <button type="button" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
              Anterior
            </button>
            <span>
              {page * limit + 1}–{Math.min((page + 1) * limit, accounts.data.total)} de{" "}
              {accounts.data.total}
            </span>
            <button
              type="button"
              disabled={(page + 1) * limit >= accounts.data.total}
              onClick={() => setPage(p => p + 1)}
            >
              Siguiente
            </button>
          </div>
        )}
      </Section>
    </>
  );
}

function IncomeReport() {
  const today = todayIso();
  const [start, setStart] = useState(`${today.slice(0, 7)}-01`);
  const [end, setEnd] = useState(today);
  const [groupBy, setGroupBy] = useState("day");
  const params = `start=${start}&end=${end}&group_by=${groupBy}`;
  const income = useQuery({
    queryKey: ["finance", "income", params],
    queryFn: () => api.get<Income>(`/finance/reports/income?${params}`).then(r => r.data),
    enabled: Boolean(start && end),
  });
  return (
    <Section
      title="Ingresos"
      action={
        <DocumentDownload
          path={`/finance/reports/income.csv?${params}`}
          filename={`ingresos-${start}-${end}.csv`}
          label="Exportar CSV"
        />
      }
    >
      <div className="reports-filters">
        <label className="form-field">
          <span>Desde</span>
          <input type="date" value={start} onChange={event => setStart(event.target.value)} />
        </label>
        <label className="form-field">
          <span>Hasta</span>
          <input type="date" value={end} onChange={event => setEnd(event.target.value)} />
        </label>
        <label className="form-field">
          <span>Agrupar por</span>
          <select value={groupBy} onChange={event => setGroupBy(event.target.value)}>
            <option value="day">Día</option>
            <option value="method">Método</option>
            <option value="cashier">Cajero</option>
          </select>
        </label>
      </div>
      {income.isError && <p className="form-error">{apiMessage(income.error)}</p>}
      {income.data && (
        <>
          <p>
            <strong>{money(income.data.total)}</strong> en {income.data.payments} pagos
          </p>
          <ul className="reports-bars">
            {income.data.rows.map(row => (
              <li key={row.key}>
                <span>{groupBy === "day" ? formatDate(row.key) : row.label}</span>
                <span className="reports-bar" aria-hidden="true">
                  <span
                    style={{
                      width: `${income.data.total ? (row.total / income.data.total) * 100 : 0}%`,
                    }}
                  />
                </span>
                <b>{money(row.total)}</b>
                <small>{row.payments} pagos</small>
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
}

const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

function ExpectedReport() {
  const [year, setYear] = useState(new Date().getFullYear());
  const expected = useQuery({
    queryKey: ["finance", "expected", year],
    queryFn: () =>
      api.get<Expected[]>("/finance/reports/expected", { params: { year } }).then(r => r.data),
  });
  return (
    <Section title="Cobro esperado y cobrado">
      <label className="form-field reports-year">
        <span>Año</span>
        <input
          type="number"
          min={2000}
          max={2100}
          value={year}
          onChange={event => setYear(Number(event.target.value))}
        />
      </label>
      {expected.data && (
        <div className="reports-table-wrap">
          <table className="reports-table">
            <thead>
              <tr>
                <th scope="col">Mes</th>
                <th scope="col">Esperado (vence)</th>
                <th scope="col">Cobrado</th>
                <th scope="col">Diferencia</th>
                <th scope="col">Conceptos</th>
              </tr>
            </thead>
            <tbody>
              {expected.data.map(month => (
                <tr key={month.month}>
                  <th scope="row">
                    {MONTHS[Number(month.month.slice(5)) - 1]} {month.month.slice(0, 4)}
                  </th>
                  <td>{money(month.expected)}</td>
                  <td>{money(month.collected)}</td>
                  <td className={month.collected < month.expected ? "is-low" : undefined}>
                    {money(month.collected - month.expected)}
                  </td>
                  <td>
                    {Object.entries(month.by_concept)
                      .map(([name, total]) => `${name}: ${money(total)}`)
                      .join(" · ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}
