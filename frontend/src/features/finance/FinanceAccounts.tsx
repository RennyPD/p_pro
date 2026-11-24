import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, CalendarRange, CreditCard, Settings2, Wallet } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Pager } from "../../components/Pager";
import { Badge, Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { ACCOUNTS_PAGE, money, type Account } from "./financeData";
import { TransferInbox } from "../payments/TransferInbox";
import { FinanceOffice } from "./FinanceOffice";
import "./finance.css";

export function FinanceAccounts() {
  const uid = useAuthStore(s => s.user?.user_id);
  const query = useQuery({
    queryKey: ["finance-accounts", uid],
    queryFn: () => api.get<Account[]>("/finance/accounts").then(r => r.data),
  });
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  const [order, setOrder] = useState("overdue");
  const [page, setPage] = useState(0);
  if (query.isLoading)
    return (
      <div className="page">
        <Spinner />
      </div>
    );
  if (query.error)
    return (
      <div className="page">
        <EmptyState
          icon={<Wallet />}
          title="No pudimos cargar las cuentas"
          description={apiMessage(query.error)}
          action={<Button onClick={() => query.refetch()}>Reintentar</Button>}
        />
      </div>
    );
  const rows = (query.data || [])
    .filter(
      a =>
        `${a.student_name} ${a.enrollment_number}`.toLowerCase().includes(search.toLowerCase()) &&
        (!state ||
          (state === "overdue"
            ? a.overdue_balance > 0
            : state === "debt"
              ? a.balance > 0
              : a.balance <= 0)),
    )
    .sort((a, b) =>
      order === "name"
        ? a.student_name.localeCompare(b.student_name, "es")
        : order === "number"
          ? a.enrollment_number.localeCompare(b.enrollment_number)
          : b.overdue_balance - a.overdue_balance || b.balance - a.balance,
    );
  const pageRows = rows.slice(page * ACCOUNTS_PAGE, (page + 1) * ACCOUNTS_PAGE);
  return (
    <div className="page finance-page">
      <header className="page-header">
        <div>
          <span className="kicker">Control financiero · RD$</span>
          <h1>Cuentas estudiantiles</h1>
          <p>
            Cargos, abonos verificados y compromisos. Los cobros automáticos se configuran en
            Política.
          </p>
        </div>
        <div className="finance-header-links">
          <Link className="button button--secondary finance-plans-link" to="/finance/plans">
            <CalendarRange size={18} />
            Planes de cobro
          </Link>
          <Link className="button button--secondary" to="/finance/reports">
            <BarChart3 size={18} />
            Reportes
          </Link>
          <Link className="button button--secondary" to="/finance/online">
            <CreditCard size={18} />
            Pagos en línea
          </Link>
          <Link className="button button--secondary" to="/finance/policy">
            <Settings2 size={18} />
            Política
          </Link>
        </div>
      </header>
      <section className="profile-metrics">
        <FinanceMetric
          label="Balance institucional"
          value={money(query.data?.reduce((s, a) => s + a.balance, 0))}
        />
        <FinanceMetric
          label="Balance vencido"
          value={money(query.data?.reduce((s, a) => s + a.overdue_balance, 0))}
        />
        <FinanceMetric
          label="Cuentas con deuda"
          value={String(query.data?.filter(a => a.balance > 0).length || 0)}
        />
      </section>
      <TransferInbox />
      <section className="panel">
        <div className="finance-filters">
          <label className="form-field">
            <span>Buscar estudiante</span>
            <input
              value={search}
              onChange={e => {
                setSearch(e.target.value);
                setPage(0);
              }}
              placeholder="Nombre o matrícula"
            />
          </label>
          <label className="form-field">
            <span>Situación de la cuenta</span>
            <select
              value={state}
              onChange={e => {
                setState(e.target.value);
                setPage(0);
              }}
            >
              <option value="">Todas</option>
              <option value="overdue">Con vencimientos</option>
              <option value="debt">Con balance pendiente</option>
              <option value="clear">Sin deuda</option>
            </select>
          </label>
          <label className="form-field">
            <span>Ordenar por</span>
            <select
              value={order}
              onChange={e => {
                setOrder(e.target.value);
                setPage(0);
              }}
            >
              <option value="overdue">Mayor deuda vencida</option>
              <option value="name">Nombre</option>
              <option value="number">Matrícula</option>
            </select>
          </label>
        </div>
        <p className="muted">
          {rows.length} cuentas · Incluye estudiantes activos e inactivos con historial.
        </p>
        <div className="finance-accounts">
          {pageRows.map(a => (
            <article key={a.student_id}>
              <div>
                <strong>{a.student_name}</strong>
                <small>{a.enrollment_number}</small>
              </div>
              <div>
                <small>Balance</small>
                <strong>{money(a.balance)}</strong>
              </div>
              <div>
                <small>Vencido</small>
                <strong>{money(a.overdue_balance)}</strong>
              </div>
              <Badge
                tone={a.overdue_balance > 0 ? "danger" : a.balance > 0 ? "warning" : "success"}
              >
                {a.overdue_balance > 0 ? "Vencida" : a.balance > 0 ? "Pendiente" : "Al día"}
              </Badge>
              <Link className="text-link" to={`/finance/${a.student_id}`}>
                Abrir <ArrowRight size={16} />
              </Link>
            </article>
          ))}
        </div>
        {!rows.length && <p className="muted">No hay cuentas para estos filtros.</p>}
        <Pager
          page={page}
          pageSize={ACCOUNTS_PAGE}
          total={rows.length}
          onPage={setPage}
          label="cuentas"
        />
      </section>
      <FinanceOffice />
    </div>
  );
}

function FinanceMetric({ label, value }: { label: string; value: string }) {
  return (
    <article>
      <small>{label}</small>
      <strong>{value}</strong>
    </article>
  );
}
