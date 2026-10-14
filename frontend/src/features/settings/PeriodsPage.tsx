import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LockKeyhole, RotateCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Modal } from "../../components/ui";
import type { EntityRecord, ResourceConfig } from "../../types";
import { resources } from "../../config/resources";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { ResourcePage } from "../resources/ResourcePage";
import "./periods.css";

const labels: Record<string, string> = { planning: "Planificación", registration: "Selección abierta", active: "Docencia activa", closed: "Cerrado" };
const config: ResourceConfig = {
  ...resources.periods,
  description: "Organiza las fechas y controla el cierre académico desde cada período.",
  columns: [
    { key: "name", label: "Período", render: (value, row) => <div className="period-identity"><strong>{String(value)}</strong><div><Badge tone={row.status === "closed" ? "neutral" : row.status === "active" ? "success" : "info"}>{labels[String(row.status)] ?? String(row.status)}</Badge>{row.active && <span className="period-current">Vigente</span>}</div></div> },
    ...resources.periods.columns.filter(column => !["name", "status", "active"].includes(column.key)),
  ],
};

export function PeriodsPage() {
  const uid = useAuthStore(s => s.user?.user_id);
  const [reason, setReason] = useState("");
  const client = useQueryClient();
  const [selected, setSelected] = useState<EntityRecord | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const closing = selected?.status !== "closed";
  const preview = useQuery({ queryKey: ["period-closing-preview", uid, selected?.period_id], queryFn: () => api.get<{ can_close: boolean; blockers: string[]; restorable: boolean }>(`/periods/${selected?.period_id}/closing-preview`).then(r => r.data), enabled: Boolean(selected) });
  const lifecycle = useMutation({
    mutationFn: (period: EntityRecord) => api.post(`/periods/${period.period_id}/${period.status === "closed" ? "reopen" : "close"}`, { reason }),
    onSuccess: (response, period) => {
      toast.success(period.status === "closed" ? "Período reabierto" : `Período cerrado: ${response.data.sections_closed} secciones`);
      for (const key of ["periods", "sections", "enrollments", "period-closing-preview", "academic-analytics", "my-progress", "graduation-audit"]) client.invalidateQueries({ queryKey: [key] });
      client.invalidateQueries({ queryKey: ["lookup", "/periods/"] });
      setSelected(null);
      setFailure(null);
    },
    onError: error => setFailure(apiMessage(error)),
  });
  return <div className="periods-workspace">
    <ResourcePage config={config} rowActions={period => <button className={`period-control ${period.status === "closed" ? "period-control--reopen" : "period-control--close"}`} title={period.status === "closed" ? "Reabrir período" : "Cerrar período"} aria-label={`${period.status === "closed" ? "Reabrir" : "Cerrar"} ${period.name}`} disabled={lifecycle.isPending} onClick={() => { setSelected(period); setFailure(null); setReason(""); }}>{period.status === "closed" ? <RotateCcw size={16} /> : <LockKeyhole size={16} />}<span>{period.status === "closed" ? "Reabrir" : "Cerrar"}</span></button>} />
    {selected && <Modal title={`${closing ? "Cerrar" : "Reabrir"} ${selected.name}`} description="Control académico del período" onClose={() => { if (!lifecycle.isPending) setSelected(null); }}>
      <div className="period-confirmation"><div className="period-confirmation-icon">{closing ? <LockKeyhole /> : <RotateCcw />}</div><p>{closing ? "Se comprobarán evaluaciones cerradas, ponderación de 100 % y notas finales publicadas para cada estudiante. No se generan notas faltantes." : "Este período pasará a docencia activa y será el vigente. Los demás períodos dejarán de estar marcados como vigentes."}</p><div className="period-effect">{closing ? "Se cerrarán sus secciones y cada selección activa quedará aprobada o reprobada según su resultado final. El período dejará de estar vigente." : "Los cierres nuevos restauran los estados que cambiaron durante el cierre. Las evaluaciones conservan su cierre y requieren reapertura individual para corregir notas."}</div>{preview.isFetching && <p className="muted">Revisando condiciones…</p>}{preview.error && <p className="form-error">{apiMessage(preview.error)}</p>}{closing && preview.data?.blockers.map((b, i) => <p key={i} className="form-error">{b}</p>)}{!closing && preview.data && !preview.data.restorable && <p className="form-error">Cierre histórico sin estados previos: las secciones no se restaurarán automáticamente. Requiere revisión manual.</p>}<label className="form-field"><span>Motivo del control de período</span><input disabled={lifecycle.isPending} minLength={3} maxLength={250} value={reason} onChange={e => setReason(e.target.value)} /></label>{failure && <div className="period-error" role="alert"><strong>No se pudo completar la acción</strong><p>{failure}</p></div>}<div className="form-actions"><Button variant="secondary" disabled={lifecycle.isPending} onClick={() => setSelected(null)}>Cancelar</Button><Button variant={closing ? "danger" : "primary"} disabled={lifecycle.isPending || preview.isFetching || Boolean(preview.error) || reason.trim().length < 3 || (closing && !preview.data?.can_close)} onClick={() => lifecycle.mutate(selected)}>{lifecycle.isPending ? "Procesando…" : closing ? "Confirmar cierre" : "Reabrir período"}</Button></div></div>
    </Modal>}
  </div>;
}
