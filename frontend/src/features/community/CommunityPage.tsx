import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, Send } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./community.css";

type Notification = { notification_id: number; title: string; body: string; created_at: string; read_at: string | null };
type Sent = { announcement_id: number; title: string; body: string; audience: string; section_name: string | null; author_name: string; published_at: string; delivery_count: number | null; read_count: number | null };
type Preview = { count: number; fingerprint: string; roles: Record<string, number> };
const audiences: Record<string, string> = { all: "Toda la institución", student: "Estudiantes", teacher: "Docentes", admin: "Administración", guardian: "Tutores", section: "Estudiantes de una sección", section_guardians: "Tutores de una sección" };
const dateLabel = (value: string) => new Date(value.endsWith("Z") ? value : value + "Z").toLocaleString("es-DO", { timeZone: "America/Santo_Domingo" });
const operationKey = () => globalThis.crypto?.randomUUID?.() || `notice-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export function CommunityPage() {
  const user = useAuthStore(s => s.user);
  const client = useQueryClient();
  const canPublish = user?.role_name === "admin" || user?.role_name === "teacher";
  const admin = user?.role_name === "admin";
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState(admin ? "all" : "section");
  const [sectionId, setSectionId] = useState("");
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  const [tab, setTab] = useState("inbox");
  const [preview, setPreview] = useState<Preview>();
  const [deliveryKey, setDeliveryKey] = useState(operationKey);
  const query = useQuery({ queryKey: ["notifications", user?.user_id], queryFn: () => api.get<Notification[]>("/community/notifications").then(r => r.data) });
  const sent = useQuery({ queryKey: ["sent-announcements", user?.user_id], queryFn: () => api.get<Sent[]>("/community/announcements").then(r => r.data), enabled: canPublish });
  const sections = useQuery({ queryKey: ["communication-sections", user?.user_id], queryFn: () => api.get<{ section_id: number; label: string }[]>("/community/sections").then(r => r.data), enabled: canPublish });
  const payload = { title, body, audience, section_id: ["section", "section_guardians"].includes(audience) ? Number(sectionId) : null, delivery_key: deliveryKey };
  const refresh = () => { void client.invalidateQueries({ queryKey: ["notifications"] }); void client.invalidateQueries({ queryKey: ["sent-announcements"] }); };
  const mark = useMutation({ mutationFn: (id?: number) => api.post(id ? `/community/notifications/${id}/read` : "/community/notifications/read-all"), onSuccess: refresh, onError: e => toast.error(apiMessage(e)) });
  const inspect = useMutation({ mutationFn: () => api.post<Preview>("/community/announcements/preview", payload).then(r => r.data), onSuccess: setPreview, onError: e => toast.error(apiMessage(e)) });
  const publish = useMutation({ mutationFn: () => api.post("/community/announcements", { ...payload, expected_recipients: preview?.fingerprint }), onSuccess: () => { toast.success("Aviso publicado"); setTitle(""); setBody(""); setPreview(undefined); setDeliveryKey(operationKey()); refresh(); setTab("sent"); }, onError: e => { toast.error(apiMessage(e)); setPreview(undefined); } });
  const busy = inspect.isPending || publish.isPending;
  const unread = query.data?.filter(n => !n.read_at).length || 0;
  const items = (query.data || []).filter(n => (!state || (state === "unread" ? !n.read_at : n.read_at)) && `${n.title} ${n.body}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="page community-page">
    <header className="page-header"><div><span className="kicker">Comunidad</span><h1>Comunicaciones</h1><p>Avisos internos con destinatarios definidos. No se envían correos ni mensajes externos.</p></div><Badge tone={unread ? "info" : "neutral"}>{unread} sin leer</Badge></header>
    <nav className="community-tabs" aria-label="Vistas de comunicaciones"><button aria-pressed={tab === "inbox"} onClick={() => setTab("inbox")}>Recibidos</button>{canPublish && <><button aria-pressed={tab === "compose"} onClick={() => setTab("compose")}>Nuevo aviso</button><button aria-pressed={tab === "sent"} onClick={() => setTab("sent")}>Publicados</button></>}</nav>
    {tab === "compose" && canPublish && <form className="panel communication-compose" onChange={() => setPreview(undefined)} onSubmit={e => { e.preventDefault(); if (!preview) inspect.mutate(); else publish.mutate(); }}>
      <div><span className="kicker">Nuevo aviso</span><h2>Publicar comunicación</h2><p className="muted">Revisa el alcance antes de confirmar. No se incluyen retirados ni estudiantes en espera de las secciones.</p></div>
      <label className="form-field"><span>Título</span><input required disabled={busy} minLength={2} maxLength={150} value={title} onChange={e => setTitle(e.target.value)} /></label>
      <label className="form-field"><span>Destinatarios</span><select disabled={busy} value={audience} onChange={e => setAudience(e.target.value)}>{Object.entries(audiences).filter(([key]) => admin || ["section", "section_guardians"].includes(key)).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      {["section", "section_guardians"].includes(audience) && <label className="form-field"><span>Sección destinataria</span><select required disabled={busy || sections.isLoading} value={sectionId} onChange={e => setSectionId(e.target.value)}><option value="">Selecciona una sección</option>{sections.data?.map(s => <option key={s.section_id} value={s.section_id}>{s.label}</option>)}</select></label>}
      <label className="form-field communication-wide"><span>Mensaje</span><textarea required disabled={busy} minLength={2} maxLength={5000} value={body} onChange={e => setBody(e.target.value)} /></label>
      {sections.error && <p className="form-error">{apiMessage(sections.error)}</p>}
      {preview && <div className="communication-preview" role="status"><strong>{preview.count} destinatarios elegibles</strong><p>{Object.entries(preview.roles).filter(([, count]) => count > 0).map(([role, count]) => `${audiences[role]}: ${count}`).join(" · ") || "Sin destinatarios"}</p><small>La lectura indica que el usuario pulsó Leído, no acredita comprensión.</small></div>}
      <Button disabled={busy || Boolean(preview && !preview.count)}><Send size={17} />{busy ? "Procesando…" : preview ? "Confirmar publicación" : "Revisar destinatarios"}</Button>
    </form>}
    {tab === "sent" && canPublish && <section className="panel sent-announcements"><h2>Avisos publicados</h2>{sent.isLoading ? <Spinner /> : sent.error ? <p className="form-error">{apiMessage(sent.error)}</p> : sent.data?.length ? sent.data.map(a => <article key={a.announcement_id}><div><strong>{a.title}</strong><small>{dateLabel(a.published_at)} · {a.author_name}</small><small>{audiences[a.audience]}{a.section_name ? " · " + a.section_name : ""}</small><small>{a.delivery_count === null ? "Aviso histórico: entrega no vinculada" : `${a.delivery_count} entregados · ${a.read_count} marcados como leídos`}</small></div><p>{a.body}</p></article>) : <p className="muted">No hay avisos publicados.</p>}</section>}
    {tab === "inbox" && <><section className="panel community-filters"><label className="form-field"><span>Buscar avisos</span><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Título o mensaje" /></label><label className="form-field"><span>Lectura</span><select value={state} onChange={e => setState(e.target.value)}><option value="">Todos</option><option value="unread">Sin leer</option><option value="read">Leídos</option></select></label><Button variant="secondary" disabled={!unread || mark.isPending} onClick={() => mark.mutate(undefined)}>Marcar todos como leídos</Button></section>
      <section className="notification-list">{query.isLoading ? <Spinner /> : query.error ? <EmptyState icon={<Bell />} title="No pudimos cargar tus avisos" description={apiMessage(query.error)} /> : items.length ? items.map(n => <article key={n.notification_id} className={`notification-card ${n.read_at ? "is-read" : ""}`}><span className="notification-icon"><Bell /></span><div><small>{dateLabel(n.created_at)}</small><h3>{n.title}</h3><p>{n.body}</p></div>{!n.read_at && <Button variant="ghost" disabled={mark.isPending} onClick={() => mark.mutate(n.notification_id)}><Check size={16} />Leído</Button>}</article>) : <EmptyState icon={<Bell />} title="Sin avisos para estos filtros" description="Las comunicaciones destinadas a tu cuenta aparecerán aquí." />}</section></>}
  </div>;
}
