import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, ReceiptText, Wallet } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./finance.css";

type Account = { student_id: number; enrollment_number: string; student_name: string; balance: number; overdue_balance: number };
type Transaction = { transaction_id: number; type: string; description: string; amount: number; date: string; due_date?: string; direction?: string; status?: string; kind?: string; method?: string; receipt_number?: string; reversal_reason?: string };
type Summary = Account & { cutoff_day: number; due_day: number; total_charges: number; total_payments: number; total_adjustments?: number; transactions: Transaction[] };
type Transfer = { transfer_request_id: number; amount: number; reference: string; bank: string; note: string; status: string; submitted_at: string; review_reason?: string; payment_id?: number };
type Plan = { payment_plan_id: number; name: string; active: boolean; installments: { installment_id: number; due_date: string; amount: number; paid_amount: number; remaining: number; status: string }[] };
type Concept = { billing_concept_id: number; name: string; amount: number; frequency: string; active: boolean };
type Closing = { cash_closing_id: number; closing_date: string; total_payments: number; payment_count: number; cash_total: number; transfer_total: number };
type Event = { id: number; action: string; actor: string; detail: string; created_at: string };
type Action = { path: string; payload: unknown; method?: "put"; done?: () => void };
const money = (value = 0) => new Intl.NumberFormat("es-DO", { style: "currency", currency: "DOP" }).format(value);
const auditNames: Record<string, string> = { "account.updated": "Configuración de cuenta", "charge.created": "Cargo registrado", "payment.posted": "Pago confirmado", "adjustment.created": "Ajuste registrado", "transaction.reversed": "Movimiento reversado", "plan.created": "Plan creado", "plan.cancelled": "Plan cancelado", "transfer.submitted": "Transferencia reportada", "transfer.reviewed": "Transferencia revisada" };
function auditDetail(value: string) {
  const names: Record<string, string> = { reason: "Motivo", description: "Concepto", reference: "Referencia", method: "Método", receipt: "Recibo", amount_cents: "Monto", due_date: "Vencimiento", status: "Estado", installments: "Cuotas", first_due_date: "Primera cuota", balance_before: "Balance anterior", balance_after: "Balance posterior", name: "Nombre", before: "Configuración anterior", after: "Configuración nueva" };
  try { return Object.entries(JSON.parse(value) as Record<string, unknown>).filter(([key]) => key in names).map(([key, v]) => `${names[key]}: ${key === "amount_cents" ? money(Number(v) / 100) : key.startsWith("balance_") ? money(Number(v)) : typeof v === "object" && v ? Object.entries(v).map(([field, n]) => `${field === "cutoff_day" ? "Corte" : field === "due_day" ? "Vencimiento" : field} día ${n}`).join(", ") : labels[String(v)] || String(v ?? "—")}`).join(" · "); } catch { return "Detalle histórico no disponible"; }
}
const day = () => new Date(Date.now() - 4 * 3600000).toISOString().slice(0, 10);
const dateLabel = (value: string) => new Date(value.length === 10 ? value + "T12:00:00" : value.endsWith("Z") ? value : value + "Z").toLocaleString("es-DO", { timeZone: "America/Santo_Domingo", ...(value.length === 10 ? { dateStyle: "medium" as const } : { dateStyle: "medium" as const, timeStyle: "short" as const }) });
const labels: Record<string, string> = { charge: "Cargo", payment: "Abono", adjustment: "Ajuste", cash: "Efectivo", transfer: "Transferencia verificada", legacy: "Registro anterior", posted: "Registrado", reversed: "Reversado", pending: "Pendiente", approved: "Aprobada", rejected: "Rechazada", paid: "Pagada", partial: "Parcial", overdue: "Vencida", discount: "Descuento", scholarship: "Beca", credit: "Crédito", late_fee: "Mora", debit: "Débito", once: "Única", monthly: "Mensual", term: "Por período", annual: "Anual" };
function useActions() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (a: Action) => a.method === "put" ? api.put(a.path, a.payload) : api.post(a.path, a.payload), onSuccess: (_r, a) => { for (const key of ["finance", "finance-accounts", "finance-plans", "finance-transfers", "finance-history", "finance-closings", "finance-concepts", "dashboard", "guardian-overview"]) void client.invalidateQueries({ queryKey: [key] }); a.done?.(); toast.success("Operación registrada"); }, onError: e => toast.error(apiMessage(e)) });
}
async function download(path: string, name: string) {
  try { const r = await api.get(path, { responseType: "blob" }); const url = URL.createObjectURL(r.data); const a = document.createElement("a"); a.href = url; a.download = r.headers?.["content-disposition"]?.match(/filename="([^"]+)"/)?.[1] || name; a.click(); URL.revokeObjectURL(url); } catch (e) { toast.error(apiMessage(e)); }
}
export function FinancePage() {
  const user = useAuthStore(s => s.user);
  const { studentId } = useParams();
  const id = studentId ?? user?.student_id;
  if (user?.role_name === "admin" && !id) return <FinanceAccounts />;
  if (!id || !Number.isInteger(Number(id)) || Number(id) <= 0) return <div className="page"><EmptyState icon={<Wallet />} title="Cuenta no disponible" description="Selecciona un estudiante con una cuenta válida." /></div>;
  return <StudentFinance key={String(id)} studentId={Number(id)} canManage={user?.role_name === "admin"} />;
}
function FinanceAccounts() {
  const uid = useAuthStore(s => s.user?.user_id);
  const query = useQuery({ queryKey: ["finance-accounts", uid], queryFn: () => api.get<Account[]>("/finance/accounts").then(r => r.data) });
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  if (query.isLoading) return <div className="page"><Spinner /></div>;
  if (query.error) return <div className="page"><EmptyState icon={<Wallet />} title="No pudimos cargar las cuentas" description={apiMessage(query.error)} action={<Button onClick={() => query.refetch()}>Reintentar</Button>} /></div>;
  const rows = (query.data || []).filter(a => `${a.student_name} ${a.enrollment_number}`.toLowerCase().includes(search.toLowerCase()) && (!state || (state === "overdue" ? a.overdue_balance > 0 : state === "debt" ? a.balance > 0 : a.balance <= 0)));
  return <div className="page finance-page"><header className="page-header"><div><span className="kicker">Control financiero · RD$</span><h1>Cuentas estudiantiles</h1><p>Cargos, abonos verificados y compromisos. No se procesan tarjetas ni cobros automáticos.</p></div></header>
    <section className="profile-metrics"><FinanceMetric label="Balance institucional" value={money(query.data?.reduce((s, a) => s + a.balance, 0))} /><FinanceMetric label="Balance vencido" value={money(query.data?.reduce((s, a) => s + a.overdue_balance, 0))} /><FinanceMetric label="Cuentas con deuda" value={String(query.data?.filter(a => a.balance > 0).length || 0)} /></section>
    <section className="panel"><div className="finance-filters"><label className="form-field"><span>Buscar estudiante</span><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Nombre o matrícula" /></label><label className="form-field"><span>Situación de la cuenta</span><select value={state} onChange={e => setState(e.target.value)}><option value="">Todas</option><option value="overdue">Con vencimientos</option><option value="debt">Con balance pendiente</option><option value="clear">Sin deuda</option></select></label></div>
      <p className="muted">{rows.length} cuentas · Incluye estudiantes activos e inactivos con historial.</p><div className="finance-accounts">{rows.map(a => <article key={a.student_id}><div><strong>{a.student_name}</strong><small>{a.enrollment_number}</small></div><div><small>Balance</small><strong>{money(a.balance)}</strong></div><div><small>Vencido</small><strong>{money(a.overdue_balance)}</strong></div><Badge tone={a.overdue_balance > 0 ? "danger" : a.balance > 0 ? "warning" : "success"}>{a.overdue_balance > 0 ? "Vencida" : a.balance > 0 ? "Pendiente" : "Al día"}</Badge><Link className="text-link" to={`/finance/${a.student_id}`}>Abrir <ArrowRight size={16} /></Link></article>)}</div>{!rows.length && <p className="muted">No hay cuentas para estos filtros.</p>}</section>
    <FinanceOffice />
  </div>;
}
function FinanceOffice() {
  const uid = useAuthStore(s => s.user?.user_id);
  const action = useActions();
  const concepts = useQuery({ queryKey: ["finance-concepts", uid], queryFn: () => api.get<Concept[]>("/finance/billing-concepts").then(r => r.data) });
  const closings = useQuery({ queryKey: ["finance-closings", uid], queryFn: () => api.get<Closing[]>("/finance/cash-closings").then(r => r.data) });
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [frequency, setFrequency] = useState("once");
  const [closingDate, setClosingDate] = useState(day());
  return <details className="panel finance-office"><summary>Caja y catálogo de conceptos</summary><div className="finance-actions">
    <section><h2>Conceptos de cobro</h2><p className="muted">Plantillas de importes. La frecuencia es informativa; no genera cargos automáticamente.</p>
      <form className="finance-form" onSubmit={e => { e.preventDefault(); action.mutate({ path: "/finance/billing-concepts", payload: { name, amount, frequency }, done: () => { setName(""); setAmount(""); } }); }}>
        <label className="form-field"><span>Nombre del concepto</span><input required minLength={2} maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
        <label className="form-field"><span>Importe RD$</span><input required type="number" min=".01" step=".01" value={amount} onChange={e => setAmount(e.target.value)} /></label>
        <label className="form-field"><span>Frecuencia informativa</span><select value={frequency} onChange={e => setFrequency(e.target.value)}>{["once", "monthly", "term", "annual"].map(f => <option key={f} value={f}>{labels[f]}</option>)}</select></label><Button disabled={action.isPending}>Crear concepto</Button>
      </form>{concepts.error && <p className="form-error">{apiMessage(concepts.error)}</p>}<div className="finance-mini-list">{concepts.data?.map(c => <article key={c.billing_concept_id}><strong>{c.name}</strong><small>{money(c.amount)} · {labels[c.frequency]}</small></article>)}</div>
    </section>
    <section><h2>Cierre diario</h2><p className="muted">Un cierre impide registrar pagos y reversos para ese día. Los registros anteriores no se reclasifican como efectivo.</p>
      <form className="finance-form" onSubmit={e => { e.preventDefault(); if (window.confirm(`¿Cerrar la caja del ${closingDate}? No podrás registrar pagos hoy si cierras el día actual.`)) action.mutate({ path: `/finance/cash-closings/${closingDate}`, payload: {} }); }}>
        <label className="form-field"><span>Fecha de caja (República Dominicana)</span><input required type="date" max={day()} value={closingDate} onChange={e => setClosingDate(e.target.value)} /></label><Button disabled={action.isPending} variant="secondary">Confirmar cierre de caja</Button>
      </form>{closings.error && <p className="form-error">{apiMessage(closings.error)}</p>}<div className="finance-mini-list">{closings.data?.map(c => <article key={c.cash_closing_id}><strong>{dateLabel(c.closing_date)} · {money(c.total_payments)}</strong><small>{c.payment_count} pagos · Efectivo {money(c.cash_total)} · Transferencias {money(c.transfer_total)} · Anteriores {money(c.total_payments - c.cash_total - c.transfer_total)}</small></article>)}</div>
    </section>
  </div></details>;
}
function StudentFinance({ studentId, canManage }: { studentId: number; canManage: boolean }) {
  const uid = useAuthStore(s => s.user?.user_id);
  const action = useActions();
  const base = `/finance/students/${studentId}`;
  const query = useQuery({ queryKey: ["finance", uid, studentId], queryFn: () => api.get<Summary>(base).then(r => r.data) });
  const options = useQuery({ queryKey: ["finance-options", uid], queryFn: () => api.get<{ transfer_instructions: string; simulator_enabled: boolean }>(`/finance/options`).then(r => r.data) });
  const transfers = useQuery({ queryKey: ["finance-transfers", uid, studentId], queryFn: () => api.get<Transfer[]>(base + "/transfers").then(r => r.data) });
  const plans = useQuery({ queryKey: ["finance-plans", uid, studentId], queryFn: () => api.get<Plan[]>(base + "/payment-plans").then(r => r.data) });
  const history = useQuery({ queryKey: ["finance-history", uid, studentId], queryFn: () => api.get<Event[]>(base + "/history").then(r => r.data), enabled: canManage });
  const concepts = useQuery({ queryKey: ["finance-concepts", uid], queryFn: () => api.get<Concept[]>("/finance/billing-concepts").then(r => r.data), enabled: canManage });
  const [tab, setTab] = useState("movements");
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("");
  const [charge, setCharge] = useState({ description: "", amount: "", due_date: "" });
  const [payment, setPayment] = useState({ amount: "", reference: "", note: "", key: crypto.randomUUID() });
  const [adjustment, setAdjustment] = useState({ kind: "scholarship", description: "", amount: "", due_date: "" });
  const [transfer, setTransfer] = useState({ amount: "", reference: "", bank: "", note: "" });
  const [file, setFile] = useState<File>();
  const [fileNonce, setFileNonce] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [plan, setPlan] = useState({ name: "", installments: "3", first_due_date: day() });
  const [review, setReview] = useState<Transfer>();
  const [reverse, setReverse] = useState<Transaction>();
  const [cancelPlan, setCancelPlan] = useState<Plan>();
  const [reason, setReason] = useState("");
  const [outcome, setOutcome] = useState("approved");
  const [simulation, setSimulation] = useState<string>();
  const [simAmount, setSimAmount] = useState("100");
  const [simBusy, setSimBusy] = useState(false);
  const [editingDays, setEditingDays] = useState(false);
  const [accountDays, setAccountDays] = useState({ cutoff_day: "15", due_day: "30" });
  if (query.isLoading) return <div className="page"><Spinner /></div>;
  if (query.error || !query.data) return <div className="page"><EmptyState icon={<Wallet />} title="No pudimos cargar la cuenta" description={apiMessage(query.error)} /></div>;
  const data = query.data;
  const movements = data.transactions.filter(t => (!filterType || t.type === filterType) && `${t.description} ${t.receipt_number || ""}`.toLowerCase().includes(search.toLowerCase()));
  async function reportTransfer() {
    if (!file || file.size > 2 * 1024 * 1024) { toast.error("Selecciona PDF, PNG o JPEG de máximo 2 MB"); return; }
    setUploading(true);
    try {
      const proof = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",")[1]); reader.onerror = () => reject(new Error("No se pudo leer el comprobante")); reader.readAsDataURL(file); });
      await action.mutateAsync({ path: base + "/transfers", payload: { ...transfer, proof_base64: proof }, done: () => { setTransfer({ amount: "", reference: "", bank: "", note: "" }); setFile(undefined); setFileNonce(n => n + 1); } });
    } catch (e) { if (e instanceof Error && e.message === "No se pudo leer el comprobante") toast.error(e.message); } finally { setUploading(false); }
  }
  return <div className="page finance-page">
    {canManage && <Link to="/finance" className="back-link"><ArrowLeft /> Cuentas</Link>}
    <header className="workspace-hero"><div><span className="kicker">Cuenta estudiantil · RD$</span><h1>{data.student_name}</h1><p>{data.enrollment_number} · Corte informativo: día {data.cutoff_day} · Vencimiento sugerido: día {data.due_day}</p></div><strong className={data.balance > 0 ? "finance-balance is-due" : "finance-balance"}>{money(data.balance)}<small>Balance pendiente</small></strong></header>
    <section className="profile-metrics"><FinanceMetric label="Cargos vigentes" value={money(data.total_charges)} /><FinanceMetric label="Abonos verificados" value={money(data.total_payments)} /><FinanceMetric label="Ajustes netos" value={money(data.total_adjustments)} /><FinanceMetric label="Balance vencido" value={money(data.overdue_balance)} /></section>
    <aside className="panel finance-notice">Los pagos son internos en pesos dominicanos. Una transferencia pendiente no reduce la deuda. Los recibos no son comprobantes fiscales y el bloqueo financiero se gestiona por separado.</aside>
    {canManage && <Button variant="secondary" onClick={() => { setAccountDays({ cutoff_day: String(data.cutoff_day), due_day: String(data.due_day) }); setEditingDays(true); }}>Configurar días de la cuenta</Button>}
    {canManage && <details className="panel finance-office"><summary>Registrar cargo, efectivo o ajuste</summary><div className="finance-actions finance-actions--three">
      <form className="finance-form" onSubmit={e => { e.preventDefault(); action.mutate({ path: base + "/charges", payload: { ...charge, due_date: charge.due_date || null }, done: () => setCharge({ description: "", amount: "", due_date: "" }) }); }}>
        <h2>Nuevo cargo</h2><label className="form-field"><span>Usar concepto del catálogo</span><select defaultValue="" onChange={e => { const c = concepts.data?.find(c => c.billing_concept_id === Number(e.target.value)); if (c) setCharge({ ...charge, description: c.name, amount: String(c.amount) }); }}><option value="">Cargo personalizado</option>{concepts.data?.filter(c => c.active).map(c => <option key={c.billing_concept_id} value={c.billing_concept_id}>{c.name} · {money(c.amount)}</option>)}</select></label>
        <label className="form-field"><span>Concepto del cargo</span><input required minLength={2} maxLength={200} value={charge.description} onChange={e => setCharge({ ...charge, description: e.target.value })} /></label>
        <label className="form-field"><span>Monto del cargo RD$</span><input required type="number" min=".01" step=".01" value={charge.amount} onChange={e => setCharge({ ...charge, amount: e.target.value })} /></label>
        <label className="form-field"><span>Vencimiento del cargo</span><input type="date" value={charge.due_date} onChange={e => setCharge({ ...charge, due_date: e.target.value })} /></label><small className="muted">Vacío: próximo día {data.due_day}, adaptado al mes.</small><Button disabled={action.isPending}>Registrar cargo</Button>
      </form>
      <form className="finance-form" onSubmit={e => { e.preventDefault(); if (window.confirm(`¿Confirmas que recibiste ${money(Number(payment.amount))} en efectivo?`)) action.mutate({ path: base + "/payments", payload: { amount: payment.amount, reference: payment.reference, note: payment.note, method: "cash", idempotency_key: payment.key }, done: () => setPayment({ amount: "", reference: "", note: "", key: crypto.randomUUID() }) }); }}>
        <h2>Efectivo recibido</h2><p className="muted">Registra únicamente dinero recibido en caja. Las transferencias se revisan en su pestaña.</p>
        <label className="form-field"><span>Monto recibido RD$</span><input required type="number" min=".01" max={Math.max(data.balance, 0)} step=".01" value={payment.amount} onChange={e => setPayment({ ...payment, amount: e.target.value })} /></label>
        <label className="form-field"><span>Referencia del efectivo</span><input required minLength={2} maxLength={100} value={payment.reference} onChange={e => setPayment({ ...payment, reference: e.target.value })} /></label>
        <label className="form-field"><span>Nota del pago</span><input maxLength={250} value={payment.note} onChange={e => setPayment({ ...payment, note: e.target.value })} /></label><Button disabled={action.isPending || data.balance <= 0}>Registrar efectivo</Button>
      </form>
      <form className="finance-form" onSubmit={e => { e.preventDefault(); action.mutate({ path: base + "/adjustments", payload: { ...adjustment, due_date: adjustment.due_date || null }, done: () => setAdjustment({ kind: "scholarship", description: "", amount: "", due_date: "" }) }); }}>
        <h2>Becas y ajustes</h2><label className="form-field"><span>Tipo de ajuste</span><select value={adjustment.kind} onChange={e => setAdjustment({ ...adjustment, kind: e.target.value })}>{["scholarship", "discount", "credit", "late_fee", "debit"].map(k => <option key={k} value={k}>{labels[k]} · {["late_fee", "debit"].includes(k) ? "aumenta deuda" : "reduce deuda"}</option>)}</select></label>
        <label className="form-field"><span>Motivo del ajuste</span><input required minLength={2} maxLength={200} value={adjustment.description} onChange={e => setAdjustment({ ...adjustment, description: e.target.value })} /></label>
        <label className="form-field"><span>Monto del ajuste RD$</span><input required type="number" min=".01" step=".01" value={adjustment.amount} onChange={e => setAdjustment({ ...adjustment, amount: e.target.value })} /></label>
        {["late_fee", "debit"].includes(adjustment.kind) && <label className="form-field"><span>Vencimiento del ajuste</span><input type="date" value={adjustment.due_date} onChange={e => setAdjustment({ ...adjustment, due_date: e.target.value })} /></label>}
        <Button disabled={action.isPending}>Registrar ajuste</Button>
      </form>
    </div></details>}
    <nav className="finance-tabs" aria-label="Vistas financieras">{[["movements", "Movimientos"], ["transfers", "Transferencias"], ["plans", "Cuotas y planes"], ...(canManage ? [["history", "Auditoría"]] : [])].map(([key, label]) => <button key={key} aria-pressed={tab === key} onClick={() => setTab(key)}>{label}</button>)}</nav>
    {tab === "movements" && <section className="panel"><div className="panel-heading"><h2>Movimientos</h2><ReceiptText /></div><div className="finance-filters"><label className="form-field"><span>Buscar movimientos</span><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Concepto, referencia o recibo" /></label><label className="form-field"><span>Tipo de movimiento</span><select value={filterType} onChange={e => setFilterType(e.target.value)}><option value="">Todos</option>{["charge", "payment", "adjustment"].map(t => <option key={t} value={t}>{labels[t]}</option>)}</select></label></div>
      <div className="finance-movements">{movements.map(t => <article className={t.status === "reversed" ? "is-reversed" : ""} key={`${t.type}-${t.transaction_id}`}><div><strong>{t.description}</strong><small>{labels[t.kind || t.type]} · {dateLabel(t.date)}{t.due_date ? " · vence " + dateLabel(t.due_date) : ""}{t.method ? " · " + labels[t.method] : ""}</small>{t.receipt_number && <small>Recibo {t.receipt_number}</small>}{t.reversal_reason && <small>Reverso: {t.reversal_reason}</small>}</div><strong className={t.direction === "credit" || t.type === "payment" ? "finance-credit" : "finance-debit"}>{t.direction === "credit" || t.type === "payment" ? "−" : "+"}{money(t.amount)}</strong><Badge tone={t.status === "reversed" ? "neutral" : "info"}>{labels[t.status || "posted"]}</Badge><div className="finance-row-actions">{t.type === "payment" && <Button variant="ghost" onClick={() => download(`/finance/payments/${t.transaction_id}/receipt.pdf`, `recibo-${t.transaction_id}.pdf`)}>Recibo</Button>}{canManage && t.status !== "reversed" && <Button variant="secondary" onClick={() => { setReverse(t); setReason(""); }}>Reversar</Button>}</div></article>)}</div>{!movements.length && <p className="muted">No hay movimientos para estos filtros.</p>}
    </section>}
    {tab === "transfers" && <section className="panel"><h2>Transferencias bancarias</h2><p className="muted">Reporta un depósito ya realizado. El administrador verifica el ingreso en el banco y aprueba o rechaza el comprobante.</p>
      {options.isLoading ? <Spinner /> : options.error ? <p className="form-error">{apiMessage(options.error)}</p> : options.data?.transfer_instructions ? <><p className="finance-bank-instructions">{options.data.transfer_instructions}</p><form className="finance-form finance-transfer-form" onSubmit={e => { e.preventDefault(); void reportTransfer(); }}>
        <label className="form-field"><span>Monto transferido RD$</span><input required type="number" min=".01" max={Math.max(data.balance, 0)} step=".01" value={transfer.amount} onChange={e => setTransfer({ ...transfer, amount: e.target.value })} /></label>
        <label className="form-field"><span>Referencia bancaria</span><input required minLength={2} maxLength={100} value={transfer.reference} onChange={e => setTransfer({ ...transfer, reference: e.target.value })} /></label>
        <label className="form-field"><span>Banco de origen</span><input required minLength={2} maxLength={100} value={transfer.bank} onChange={e => setTransfer({ ...transfer, bank: e.target.value })} /></label>
        <label className="form-field"><span>Nota de la transferencia</span><input maxLength={250} value={transfer.note} onChange={e => setTransfer({ ...transfer, note: e.target.value })} /></label>
        <label className="form-field"><span>Comprobante privado (PDF, PNG o JPEG, máximo 2 MB)</span><input key={fileNonce} type="file" required accept=".pdf,.png,.jpg,.jpeg" onChange={e => setFile(e.target.files?.[0])} />{file && <small>{file.name}</small>}</label><Button disabled={uploading || action.isPending || data.balance <= 0 || !file}>Enviar para revisión</Button>
      </form></> : <p className="finance-notice">La institución todavía no ha configurado sus instrucciones bancarias. No realices transferencias hasta recibirlas.</p>}
      {transfers.error && <p className="form-error">{apiMessage(transfers.error)}</p>}<div className="finance-mini-list">{transfers.data?.map(t => <article key={t.transfer_request_id}><strong>{t.reference} · {money(t.amount)}</strong><small>{t.bank} · {dateLabel(t.submitted_at)} · {t.note}</small><Badge tone={t.status === "approved" ? "success" : t.status === "rejected" ? "danger" : "warning"}>{labels[t.status]}</Badge>{t.review_reason && <p>{t.review_reason}</p>}<div className="finance-row-actions"><Button variant="ghost" onClick={() => download(`/finance/transfers/${t.transfer_request_id}/proof`, `comprobante-${t.transfer_request_id}`)}>Descargar comprobante</Button>{canManage && t.status === "pending" && <Button onClick={() => { setReview(t); setReason(""); }}>Revisar ingreso</Button>}{t.payment_id && <Button variant="secondary" onClick={() => download(`/finance/payments/${t.payment_id}/receipt.pdf`, `recibo-${t.payment_id}.pdf`)}>Recibo</Button>}</div></article>)}</div>{transfers.data?.length === 0 && <p className="muted">No hay transferencias reportadas.</p>}
    </section>}
    {tab === "plans" && <section className="panel"><h2>Cuotas y planes</h2><p className="muted">Distribuyen el balance actual en compromisos mensuales. Abonos y créditos posteriores cubren las cuotas en orden. No reemplazan los vencimientos originales de los cargos ni añaden otra deuda.</p>
      {canManage && <form className="finance-form finance-transfer-form" onSubmit={e => { e.preventDefault(); action.mutate({ path: base + "/payment-plans", payload: { ...plan, installments: Number(plan.installments) }, done: () => setPlan({ name: "", installments: "3", first_due_date: day() }) }); }}>
        <label className="form-field"><span>Nombre del plan</span><input required minLength={2} maxLength={100} value={plan.name} onChange={e => setPlan({ ...plan, name: e.target.value })} /></label>
        <label className="form-field"><span>Cantidad de cuotas</span><input required type="number" min={2} max={24} value={plan.installments} onChange={e => setPlan({ ...plan, installments: e.target.value })} /></label>
        <label className="form-field"><span>Primer vencimiento</span><input required type="date" min={day()} value={plan.first_due_date} onChange={e => setPlan({ ...plan, first_due_date: e.target.value })} /></label><Button disabled={action.isPending || data.balance <= 0 || plans.data?.some(p => p.active)}>Crear plan</Button>
      </form>}{plans.error && <p className="form-error">{apiMessage(plans.error)}</p>}<div className="finance-mini-list">{plans.data?.map(p => <article key={p.payment_plan_id}><div className="panel-heading"><h3>{p.name}</h3><Badge tone={p.active ? "info" : "neutral"}>{p.active ? "Activo" : "Cancelado"}</Badge></div>{p.installments.map(i => <div className="finance-installment" key={i.installment_id}><span>{dateLabel(i.due_date)}</span><span>{money(i.amount)} · cubierto {money(i.paid_amount)} · pendiente {money(i.remaining)}</span><Badge tone={i.status === "paid" ? "success" : i.status === "overdue" ? "danger" : "warning"}>{labels[i.status]}</Badge></div>)}{canManage && p.active && <Button variant="secondary" onClick={() => { setCancelPlan(p); setReason(""); }}>Cancelar plan sin borrar pagos</Button>}</article>)}</div>{plans.data?.length === 0 && <p className="muted">No hay planes registrados.</p>}
    </section>}
    {tab === "history" && canManage && <section className="panel"><h2>Auditoría financiera</h2><p className="muted">Autor, fecha y detalle de las operaciones registradas desde esta mejora. No se inventan autores para movimientos antiguos.</p>{history.error && <p className="form-error">{apiMessage(history.error)}</p>}<div className="finance-mini-list">{history.data?.map(h => <article key={h.id}><strong>{auditNames[h.action] || h.action} · {h.actor}</strong><small>{dateLabel(h.created_at)}</small><p>{auditDetail(h.detail)}</p></article>)}</div>{history.data?.length === 0 && <p className="muted">Todavía no hay eventos auditados.</p>}</section>}
    {canManage && options.data?.simulator_enabled && <details className="panel finance-simulator"><summary>Simulador de pagos · sin dinero real</summary><p>Herramienta de pruebas: no crea pagos, recibos ni reduce balances. No solicita datos de tarjeta.</p><form className="finance-form finance-transfer-form" onSubmit={async e => { e.preventDefault(); setSimBusy(true); try { const r = await api.post(base + "/simulate", { amount: simAmount, outcome }); setSimulation(`SIMULACIÓN: ${r.data.outcome === "approved" ? "aprobada" : r.data.outcome === "declined" ? "rechazada" : "cancelada"}. Balance sin cambios.`); } catch (err) { toast.error(apiMessage(err)); } finally { setSimBusy(false); } }}>
      <label className="form-field"><span>Monto simulado RD$</span><input required type="number" min=".01" step=".01" value={simAmount} onChange={e => setSimAmount(e.target.value)} /></label><label className="form-field"><span>Resultado simulado</span><select value={outcome} onChange={e => setOutcome(e.target.value)}><option value="approved">Aprobado</option><option value="declined">Rechazado</option><option value="cancelled">Cancelado</option></select></label><Button disabled={simBusy} variant="secondary">Ejecutar simulación</Button>{simulation && <p role="status">{simulation}</p>}
    </form></details>}
    {editingDays && <Modal title="Días de la cuenta" description="El corte es informativo. El vencimiento solo se usa para cargos nuevos sin fecha explícita; no cambia deudas existentes." onClose={() => { if (!action.isPending) setEditingDays(false); }}><form className="finance-form finance-modal-form" onSubmit={e => { e.preventDefault(); action.mutate({ path: base + "/account", method: "put", payload: { cutoff_day: Number(accountDays.cutoff_day), due_day: Number(accountDays.due_day) }, done: () => setEditingDays(false) }); }}><label className="form-field"><span>Día de corte informativo</span><input required disabled={action.isPending} type="number" min={1} max={31} value={accountDays.cutoff_day} onChange={e => setAccountDays({ ...accountDays, cutoff_day: e.target.value })} /></label><label className="form-field"><span>Día de vencimiento sugerido</span><input required disabled={action.isPending} type="number" min={1} max={31} value={accountDays.due_day} onChange={e => setAccountDays({ ...accountDays, due_day: e.target.value })} /></label><Button disabled={action.isPending}>Guardar días de la cuenta</Button></form></Modal>}
    {(review || reverse || cancelPlan) && <Modal title={review ? "Verificar transferencia" : reverse ? "Reversar movimiento" : "Cancelar plan"} description={review ? "Confirma el ingreso en el banco; el comprobante por sí solo no demuestra recepción." : "Se conserva el historial. Esta operación no devuelve dinero al banco ni borra registros."} onClose={() => { if (!action.isPending) { setReview(undefined); setReverse(undefined); setCancelPlan(undefined); } }}>
      <form className="finance-form finance-modal-form" onSubmit={e => { e.preventDefault(); const path = review ? `/finance/transfers/${review.transfer_request_id}/review` : reverse ? `${base}/transactions/${reverse.type}/${reverse.transaction_id}/reverse` : `${base}/payment-plans/${cancelPlan?.payment_plan_id}/cancel`; if (window.confirm("¿Confirmar esta operación financiera?")) action.mutate({ path, payload: review ? { reason, approve: true } : { reason }, done: () => { setReview(undefined); setReverse(undefined); setCancelPlan(undefined); } }); }}>
        {review && <p>{review.reference} · {money(review.amount)} · {review.bank}</p>}{reverse && <p>{reverse.description} · {money(reverse.amount)}</p>}<label className="form-field"><span>Motivo de la operación</span><input required minLength={3} maxLength={250} value={reason} onChange={e => setReason(e.target.value)} /></label><div className="finance-row-actions"><Button disabled={action.isPending}>{review ? "Confirmar dinero recibido" : "Confirmar operación"}</Button>{review && <Button type="button" variant="danger" disabled={action.isPending || reason.trim().length < 3} onClick={() => action.mutate({ path: `/finance/transfers/${review.transfer_request_id}/review`, payload: { reason, approve: false }, done: () => setReview(undefined) })}>Rechazar comprobante</Button>}</div>
      </form>
    </Modal>}
  </div>;
}
function FinanceMetric({ label, value }: { label: string; value: string }) { return <article><small>{label}</small><strong>{value}</strong></article>; }
