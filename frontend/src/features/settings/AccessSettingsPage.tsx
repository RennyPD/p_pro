import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./institutional-control.css";

type Role = { role_id: number; name: string };
type Permission = { permission_id: number; slug: string; description: string };
type Change = { id: number; actor: string; action: string; detail: string; created_at: string };
const roleNames: Record<string, string> = { admin: "Administración", teacher: "Docente", student: "Estudiante", guardian: "Tutor" };
export function AccessSettingsPage() {
  const uid = useAuthStore(s => s.user?.user_id);
  const client = useQueryClient();
  const [chosen, setChosen] = useState(0);
  const [draft, setDraft] = useState<{ role: number; selected: string[]; before: string[] }>();
  const [reason, setReason] = useState("");
  const roles = useQuery({ queryKey: ["access-roles", uid], queryFn: () => api.get<Role[]>("/roles/").then(r => r.data) });
  const id = chosen || roles.data?.[0]?.role_id || 0;
  const permissions = useQuery({ queryKey: ["access-catalog", uid], queryFn: () => api.get<Permission[]>("/access/permissions").then(r => r.data) });
  const current = useQuery({ queryKey: ["role-permissions", uid, id], queryFn: () => api.get<{ permissions: string[] }>(`/access/roles/${id}/permissions`).then(r => r.data), enabled: Boolean(id) });
  const history = useQuery({ queryKey: ["access-history", uid, id], queryFn: () => api.get<Change[]>(`/access/roles/${id}/history`).then(r => r.data), enabled: Boolean(id) });
  const selected = draft?.role === id ? draft.selected : current.data?.permissions || [];
  const before = draft?.role === id ? draft.before : current.data?.permissions || [];
  const dirty = [...selected].sort().join() !== [...before].sort().join();
  useEffect(() => { if (!dirty) return; const guard = (e: BeforeUnloadEvent) => e.preventDefault(); window.addEventListener("beforeunload", guard); return () => window.removeEventListener("beforeunload", guard); }, [dirty]);
  const save = useMutation({ mutationFn: () => api.put(`/access/roles/${id}/permissions`, { permissions: selected, expected_permissions: before, reason }), onSuccess: async () => { toast.success("Permisos actualizados"); setDraft(undefined); setReason(""); await client.invalidateQueries({ queryKey: ["role-permissions"] }); void client.invalidateQueries({ queryKey: ["my-permissions"] }); void client.invalidateQueries({ queryKey: ["access-history"] }); }, onError: e => toast.error(apiMessage(e)) });
  if (roles.isLoading || permissions.isLoading) return <div className="page"><Spinner /></div>;
  const error = roles.error || permissions.error;
  if (error) return <div className="page"><EmptyState icon={<ShieldCheck />} title="No pudimos cargar los accesos" description={apiMessage(error)} /></div>;
  return <div className="page access-settings"><header className="page-header"><div><span className="kicker">Configuración · Seguridad</span><h1>Permisos por rol</h1><p>Revisa los cambios antes de guardar. No puedes retirar tus propios permisos esenciales ni dejar la institución sin gestión de acceso.</p></div></header>
    <section className="panel"><label className="form-field"><span>Rol que se modificará</span><select disabled={save.isPending} value={id} onChange={e => { if (dirty && !window.confirm("¿Descartar los cambios de este rol?")) return; setChosen(Number(e.target.value)); setDraft(undefined); setReason(""); }}>{roles.data?.map(r => <option key={r.role_id} value={r.role_id}>{roleNames[r.name] || r.name}</option>)}</select></label>
      {current.isFetching ? <Spinner /> : current.error ? <p className="form-error">{apiMessage(current.error)}</p> : <form onSubmit={e => { e.preventDefault(); if (window.confirm("¿Aplicar los cambios de permisos a todos los usuarios de este rol?")) save.mutate(); }}>
        <div className="permission-list">{permissions.data?.map(p => <label key={p.permission_id}><input disabled={save.isPending} type="checkbox" checked={selected.includes(p.slug)} onChange={e => setDraft({ role: id, before, selected: e.target.checked ? [...selected, p.slug] : selected.filter(s => s !== p.slug) })} /><span><strong>{p.description}</strong><small>{p.slug}</small></span></label>)}</div>
        {dirty && <aside className="period-effect"><p>Se conceden: {selected.filter(s => !before.includes(s)).join(", ") || "Ninguno"}</p><p>Se retiran: {before.filter(s => !selected.includes(s)).join(", ") || "Ninguno"}</p></aside>}
        <label className="form-field"><span>Motivo del cambio de permisos</span><input required minLength={3} maxLength={250} disabled={save.isPending} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <div className="form-actions"><Button type="button" variant="secondary" disabled={save.isPending || !dirty} onClick={() => { setDraft(undefined); setReason(""); }}>Descartar cambios</Button><Button disabled={!dirty || save.isPending || !id}>Guardar permisos</Button></div>
      </form>}
    </section><section className="panel"><h2>Historial de este rol</h2>{history.isLoading ? <Spinner /> : history.error ? <p className="form-error">{apiMessage(history.error)}</p> : history.data?.length ? history.data.map(h => <article className="intervention-history" key={h.id}><strong>{h.actor} · {new Date(h.created_at + "Z").toLocaleString("es-DO", { timeZone: "America/Santo_Domingo" })}</strong><p>{h.detail}</p></article>) : <p className="muted">Sin cambios auditados desde la incorporación de este control.</p>}</section>
  </div>;
}
