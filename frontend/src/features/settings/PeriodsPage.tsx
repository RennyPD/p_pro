import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, LockKeyhole, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { resources } from "../../config/resources";
import { api, apiMessage } from "../../lib/api";
import { ResourcePage } from "../resources/ResourcePage";
import "./periods.css";

export function PeriodsPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["period-lifecycle"], queryFn: () => api.get("/periods/").then(response => response.data) });
  const refresh = () => { client.invalidateQueries({ queryKey: ["period-lifecycle"] }); client.invalidateQueries({ queryKey: ["resource", "periods"] }); };
  const close = useMutation({ mutationFn: (id: number) => api.post(`/periods/${id}/close`), onSuccess: response => { toast.success(`Período cerrado: ${response.data.sections_closed} secciones`); refresh(); }, onError: error => toast.error(apiMessage(error)) });
  const reopen = useMutation({ mutationFn: (id: number) => api.post(`/periods/${id}/reopen`), onSuccess: () => { toast.success("Período reabierto"); refresh(); }, onError: error => toast.error(apiMessage(error)) });
  return <><ResourcePage config={resources.periods} /><section className="page period-lifecycle"><div className="panel"><div className="panel-heading"><div><span className="kicker">Control académico</span><h2>Cierre de períodos</h2><p>El cierre valida que todas las evaluaciones estén completas antes de consolidar las selecciones.</p></div><CalendarCheck /></div>{query.isLoading ? <Spinner /> : query.error ? <EmptyState icon={<CalendarCheck />} title="No pudimos cargar los períodos" description={apiMessage(query.error)} /> : <div className="period-list">{query.data?.map((period: any) => <article key={period.period_id}><div><strong>{period.name}</strong><small>{period.academic_year} · {period.status}</small></div>{period.status === "closed" ? <Button variant="secondary" onClick={() => reopen.mutate(period.period_id)}><RotateCcw size={16} /> Reabrir</Button> : <Button variant="danger" onClick={() => close.mutate(period.period_id)}><LockKeyhole size={16} /> Cerrar período</Button>}</article>)}</div>}</div></section></>;
}
