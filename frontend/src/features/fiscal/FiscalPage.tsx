import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FileText, Hash, Landmark } from "lucide-react";
import { useState, type FormEvent } from "react";
import { DocumentDownload } from "../../components/DocumentDownload";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { Section } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import { formatDate, formatDateTime, formatMoney } from "../../lib/format";
import { useAccess } from "../../lib/permissions";
import "./fiscal.css";

type Profile = {
  enabled: boolean;
  mode: string;
  rnc: string;
  legal_name: string;
  trade_name: string;
  fiscal_address: string;
  issue_on: string;
  doc_types: Record<string, string>;
};
type Sequence = {
  fiscal_sequence_id: number;
  doc_type: string;
  label: string;
  range_start: number;
  range_end: number;
  next_number: number;
  remaining: number;
  expires_on: string | null;
  active: boolean;
};
type Alert = { fiscal_sequence_id: number; kind: string; message: string };
type Document = {
  fiscal_document_id: number;
  doc_type: string;
  label: string;
  ncf: string;
  status: string;
  issued_at: string;
  buyer_name: string;
  buyer_tax_id: string;
  itbis: string;
  total: string;
};

const size = 25;
const VOID_REASONS: Record<string, string> = {
  "01": "Deterioro de factura preimpresa",
  "02": "Errores de impresión (factura preimpresa)",
  "03": "Impresión defectuosa",
  "04": "Corrección de la información",
  "05": "Cambio de productos",
  "06": "Devolución de productos",
  "07": "Omisión de productos",
  "08": "Errores en secuencia de NCF",
  "09": "Por cese de operaciones",
  "10": "Pérdida o hurto de talonarios",
};

/** Fiscal receipts of the institution: issuer, DGII ranges, receipts and reports (Fase 4 F). */
export function FiscalPage() {
  const access = useAccess();
  const profile = useQuery({
    queryKey: ["fiscal", "profile"],
    queryFn: () => api.get<Profile>("/fiscal/profile").then(r => r.data),
  });
  if (profile.isPending) return <Spinner label="Cargando datos fiscales" />;
  if (profile.isError)
    return (
      <p className="form-error" role="alert">
        {apiMessage(profile.error)}
      </p>
    );
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="kicker">Finanzas</span>
          <h1>Comprobantes fiscales</h1>
          <p>
            NCF o e-CF de la institución, secuencias autorizadas por la DGII y reportes 607 y 608.
          </p>
        </div>
      </header>
      {access.can("finance.manage") && <IssuerForm profile={profile.data} />}
      <Sequences types={profile.data.doc_types} canManage={access.can("finance.manage")} />
      <Documents canVoid={access.can("finance.supervise")} />
      <Reports />
    </div>
  );
}

function IssuerForm({ profile }: { profile: Profile }) {
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.put("/fiscal/profile", body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["fiscal"] }),
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    save.mutate({
      enabled: form.get("enabled") === "on",
      mode: text("mode"),
      rnc: text("rnc"),
      legal_name: text("legal_name"),
      trade_name: text("trade_name"),
      fiscal_address: text("fiscal_address"),
      issue_on: text("issue_on"),
    });
  }
  return (
    <Section title="Emisor" icon={<Landmark size={18} />}>
      <form className="fiscal-form" onSubmit={submit}>
        <label className="fiscal-check">
          <input name="enabled" type="checkbox" defaultChecked={profile.enabled} /> Emitir
          comprobantes fiscales
        </label>
        <label className="form-field">
          <span>RNC</span>
          <input name="rnc" inputMode="numeric" maxLength={11} defaultValue={profile.rnc} />
        </label>
        <label className="form-field">
          <span>Razón social</span>
          <input name="legal_name" defaultValue={profile.legal_name} />
        </label>
        <label className="form-field">
          <span>Nombre comercial</span>
          <input name="trade_name" defaultValue={profile.trade_name} />
        </label>
        <label className="form-field fiscal-wide">
          <span>Dirección fiscal</span>
          <input name="fiscal_address" defaultValue={profile.fiscal_address} />
        </label>
        <label className="form-field">
          <span>Tipo de comprobante</span>
          <select name="mode" defaultValue={profile.mode}>
            <option value="ncf">NCF (B01, B02…)</option>
            <option value="ecf">Electrónico e-CF (E31, E32…)</option>
          </select>
        </label>
        <label className="form-field">
          <span>Cuándo se emite</span>
          <select name="issue_on" defaultValue={profile.issue_on}>
            <option value="payment">Al registrar cada pago</option>
            <option value="request">Solo a solicitud</option>
          </select>
        </label>
        {save.error && (
          <div className="form-error fiscal-wide" role="alert">
            {apiMessage(save.error)}
          </div>
        )}
        {save.isSuccess && (
          <p className="fiscal-saved fiscal-wide" role="status">
            Datos del emisor guardados.
          </p>
        )}
        <div className="form-actions fiscal-wide">
          <Button disabled={save.isPending}>Guardar emisor</Button>
        </div>
      </form>
    </Section>
  );
}

function Sequences({ types, canManage }: { types: Record<string, string>; canManage: boolean }) {
  const client = useQueryClient();
  const data = useQuery({
    queryKey: ["fiscal", "sequences"],
    queryFn: () =>
      api.get<{ sequences: Sequence[]; alerts: Alert[] }>("/fiscal/sequences").then(r => r.data),
  });
  const add = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/fiscal/sequences", body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["fiscal", "sequences"] }),
  });
  const deactivate = useMutation({
    mutationFn: (id: number) => api.post(`/fiscal/sequences/${id}/deactivate`),
    onSuccess: () => client.invalidateQueries({ queryKey: ["fiscal", "sequences"] }),
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    add.mutate({
      doc_type: form.get("doc_type"),
      range_start: Number(form.get("range_start")),
      range_end: Number(form.get("range_end")),
      expires_on: String(form.get("expires_on") ?? "") || null,
    });
  }
  return (
    <Section title="Secuencias autorizadas" icon={<Hash size={18} />}>
      {data.data?.alerts.map(alert => (
        <p key={`${alert.fiscal_sequence_id}-${alert.kind}`} className="fiscal-alert" role="alert">
          <AlertTriangle size={16} aria-hidden /> {alert.message}
        </p>
      ))}
      {data.isPending ? (
        <Spinner label="Cargando secuencias" />
      ) : !data.data?.sequences.length ? (
        <p className="muted">
          Registra las secuencias que te autorizó la DGII para empezar a emitir.
        </p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Rango</th>
                <th>Siguiente</th>
                <th>Disponibles</th>
                <th>Vence</th>
                <th>Estado</th>
                {canManage && <th>Acción</th>}
              </tr>
            </thead>
            <tbody>
              {data.data.sequences.map(sequence => (
                <tr key={sequence.fiscal_sequence_id}>
                  <td>
                    <strong>{sequence.doc_type}</strong>
                    <div className="muted">{sequence.label}</div>
                  </td>
                  <td>
                    {sequence.range_start}–{sequence.range_end}
                  </td>
                  <td>{sequence.next_number}</td>
                  <td>{sequence.remaining}</td>
                  <td>{sequence.expires_on ? formatDate(sequence.expires_on) : "—"}</td>
                  <td>
                    <Badge tone={sequence.active ? "success" : "neutral"}>
                      {sequence.active ? "Activa" : "Inactiva"}
                    </Badge>
                  </td>
                  {canManage && (
                    <td>
                      {sequence.active && (
                        <Button
                          variant="ghost"
                          disabled={deactivate.isPending}
                          onClick={() => deactivate.mutate(sequence.fiscal_sequence_id)}
                        >
                          Desactivar
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {canManage && (
        <form className="fiscal-form fiscal-sequence-form" onSubmit={submit}>
          <label className="form-field">
            <span>Tipo</span>
            <select name="doc_type" defaultValue="B02">
              {Object.entries(types).map(([code, label]) => (
                <option key={code} value={code}>
                  {code} · {label}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Desde</span>
            <input name="range_start" type="number" min="1" required />
          </label>
          <label className="form-field">
            <span>Hasta</span>
            <input name="range_end" type="number" min="1" required />
          </label>
          <label className="form-field">
            <span>Fecha de vencimiento</span>
            <input name="expires_on" type="date" />
          </label>
          {add.error && (
            <div className="form-error fiscal-wide" role="alert">
              {apiMessage(add.error)}
            </div>
          )}
          <div className="form-actions fiscal-wide">
            <Button variant="secondary" disabled={add.isPending}>
              Registrar secuencia
            </Button>
          </div>
        </form>
      )}
    </Section>
  );
}

function Documents({ canVoid }: { canVoid: boolean }) {
  const [term, setTerm] = useState("");
  const [page, setPage] = useState(0);
  const [voiding, setVoiding] = useState<Document | null>(null);
  const rows = useQuery({
    queryKey: ["fiscal", "documents", term, page],
    queryFn: () =>
      api
        .get<Document[]>("/fiscal/documents", {
          params: { q: term || undefined, skip: page * size, limit: size },
        })
        .then(r => ({ rows: r.data, total: Number(r.headers["x-total-count"] ?? r.data.length) })),
  });
  const total = rows.data?.total ?? 0;
  return (
    <Section
      title="Comprobantes emitidos"
      icon={<FileText size={18} />}
      action={
        <label className="form-field">
          <span>Buscar</span>
          <input
            placeholder="NCF, cliente o RNC"
            onChange={event => {
              setTerm(event.target.value.trim());
              setPage(0);
            }}
          />
        </label>
      }
    >
      {rows.isPending ? (
        <Spinner label="Cargando comprobantes" />
      ) : !rows.data?.rows.length ? (
        <EmptyState
          icon={<FileText />}
          title="Sin comprobantes"
          description="Los comprobantes aparecen al registrar pagos con la emisión activa."
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>NCF</th>
                <th>Fecha</th>
                <th>Cliente</th>
                <th>ITBIS</th>
                <th>Total</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {rows.data.rows.map(row => (
                <tr key={row.fiscal_document_id}>
                  <td>
                    <strong>{row.ncf}</strong>
                    <div className="muted">{row.label}</div>
                    {row.status === "voided" && <Badge tone="neutral">Anulado</Badge>}
                  </td>
                  <td>{formatDateTime(row.issued_at)}</td>
                  <td>
                    {row.buyer_name}
                    <div className="muted">{row.buyer_tax_id || "Consumidor final"}</div>
                  </td>
                  <td>{formatMoney(Number(row.itbis))}</td>
                  <td>{formatMoney(Number(row.total))}</td>
                  <td className="fiscal-actions">
                    <DocumentDownload
                      path={`/fiscal/documents/${row.fiscal_document_id}.pdf`}
                      filename={`${row.ncf}.pdf`}
                      label="PDF"
                      accessibleLabel={`PDF del comprobante ${row.ncf}`}
                    />
                    {canVoid && row.status === "issued" && (
                      <Button variant="ghost" onClick={() => setVoiding(row)}>
                        Anular
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
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
      {voiding && <VoidDialog document={voiding} onClose={() => setVoiding(null)} />}
    </Section>
  );
}

function VoidDialog({ document, onClose }: { document: Document; onClose: () => void }) {
  const client = useQueryClient();
  const run = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(`/fiscal/documents/${document.fiscal_document_id}/void`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["fiscal", "documents"] });
      onClose();
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    run.mutate({ reason: form.get("reason"), note: String(form.get("note") ?? "").trim() });
  }
  return (
    <Modal
      title={`Anular ${document.ncf}`}
      description="Para deshacer un cobro emite una nota de crédito revirtiendo el pago. Anula solo comprobantes emitidos por error; saldrán en el 608."
      onClose={onClose}
    >
      <form className="fiscal-form" onSubmit={submit}>
        <label className="form-field fiscal-wide">
          <span>Motivo (DGII)</span>
          <select name="reason" defaultValue="04">
            {Object.entries(VOID_REASONS).map(([code, label]) => (
              <option key={code} value={code}>
                {code} · {label}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field fiscal-wide">
          <span>Detalle</span>
          <textarea name="note" required minLength={5} />
        </label>
        {run.error && (
          <div className="form-error fiscal-wide" role="alert">
            {apiMessage(run.error)}
          </div>
        )}
        <div className="form-actions fiscal-wide">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button variant="danger" disabled={run.isPending}>
            Anular comprobante
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function Reports() {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const compact = month.replace("-", "");
  return (
    <Section title="Reportes para la DGII" icon={<FileText size={18} />}>
      <p className="muted">
        Formatos 607 (ventas) y 608 (anulados) para subir en la Oficina Virtual. Valida el primero
        con la herramienta de la DGII junto con tu contador.
      </p>
      <div className="fiscal-reports">
        <label className="form-field">
          <span>Mes</span>
          <input type="month" value={month} onChange={event => setMonth(event.target.value)} />
        </label>
        <DocumentDownload
          path={`/fiscal/reports/607.txt?month=${month}`}
          filename={`DGII_F_607_${compact}.txt`}
          label="Descargar 607"
        />
        <DocumentDownload
          path={`/fiscal/reports/608.txt?month=${month}`}
          filename={`DGII_F_608_${compact}.txt`}
          label="Descargar 608"
        />
      </div>
    </Section>
  );
}
