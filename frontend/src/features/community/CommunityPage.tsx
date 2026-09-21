import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, Send } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./community.css";

type Notification = { notification_id: number; title: string; body: string; created_at: string; read_at: string | null };

export function CommunityPage() {
  const user = useAuthStore(state => state.user);
  const client = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState("all");
  const query = useQuery<Notification[]>({ queryKey: ["notifications"], queryFn: () => api.get("/community/notifications").then(response => response.data) });
  const sent = useQuery({ queryKey: ["sent-announcements"], queryFn: () => api.get("/community/announcements").then(response => response.data), enabled: user?.role_name === "admin" || user?.role_name === "teacher" });
  const mark = useMutation({ mutationFn: (id: number) => api.post(`/community/notifications/${id}/read`), onSuccess: () => client.invalidateQueries({ queryKey: ["notifications"] }) });
  const publish = useMutation({ mutationFn: () => api.post("/community/announcements", { title, body, audience }), onSuccess: () => { toast.success("Aviso publicado"); setTitle(""); setBody(""); client.invalidateQueries({ queryKey: ["notifications"] }); client.invalidateQueries({ queryKey: ["sent-announcements"] }); }, onError: error => toast.error(apiMessage(error)) });
  const canPublish = user?.role_name === "admin" || user?.role_name === "teacher";

  return <div className="page">
    <header className="page-header"><div><span className="kicker">Comunidad</span><h1>Comunicaciones</h1><p>Avisos internos claros y visibles únicamente para sus destinatarios.</p></div></header>
    {canPublish && <section className="panel communication-compose"><div><span className="kicker">Nuevo aviso</span><h2>Publicar comunicación</h2></div><label className="form-field"><span>Título</span><input value={title} onChange={event => setTitle(event.target.value)} /></label><label className="form-field"><span>Mensaje</span><textarea value={body} onChange={event => setBody(event.target.value)} /></label>{user?.role_name === "admin" && <label className="form-field"><span>Destinatarios</span><select value={audience} onChange={event => setAudience(event.target.value)}><option value="all">Toda la institución</option><option value="student">Estudiantes</option><option value="teacher">Docentes</option><option value="admin">Administración</option></select></label>}<Button disabled={title.length < 2 || body.length < 2 || publish.isPending} onClick={() => publish.mutate()}><Send size={17} /> Publicar</Button></section>}
    {canPublish && sent.data?.length > 0 && <section className="panel sent-announcements"><span className="kicker">Trazabilidad</span><h2>Avisos publicados</h2>{sent.data.map((item: any) => <article key={item.announcement_id}><div><strong>{item.title}</strong><small>{new Date(item.published_at).toLocaleString("es-DO")} · {item.audience}</small></div><p>{item.body}</p></article>)}</section>}
    <section className="notification-list">{query.isLoading ? <Spinner /> : query.error ? <EmptyState icon={<Bell />} title="No pudimos cargar tus avisos" description={apiMessage(query.error)} /> : query.data?.length ? query.data.map(item => <article key={item.notification_id} className={`notification-card ${item.read_at ? "is-read" : ""}`}><span className="notification-icon"><Bell /></span><div><small>{new Date(item.created_at).toLocaleString()}</small><h3>{item.title}</h3><p>{item.body}</p></div>{!item.read_at && <Button variant="ghost" onClick={() => mark.mutate(item.notification_id)}><Check size={16} /> Leído</Button>}</article>) : <EmptyState icon={<Bell />} title="No tienes avisos" description="Las comunicaciones de tu institución aparecerán aquí." />}</section>
  </div>;
}
