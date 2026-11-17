import { useQuery } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { isCustomRole, useModuleViews } from "../../lib/moduleViews";
import { useAuthStore } from "../../store/auth";

const pageSize = 25;

export function CustomModuleHome() {
  const modules = useModuleViews();
  return <div className="page">
    <header className="page-header"><h1>Módulos de consulta</h1></header>
    {modules.isPending ? <Spinner /> : modules.isError
      ? <p role="alert">{apiMessage(modules.error)} <Button onClick={() => void modules.refetch()}>Reintentar</Button></p>
      : modules.data.length
        ? <ul>{modules.data.map(item => <li key={item.key}><Link to={`/modules/${item.key}`}>{item.label}</Link></li>)}</ul>
        : <EmptyState icon={<BookOpen />} title="Sin módulos asignados" description="Solicita acceso a la administración si necesitas consultar un módulo." />}
  </div>;
}

export function CustomModuleRoute() {
  const role = useAuthStore(state => state.user?.role_name);
  const { module } = useParams();
  return isCustomRole(role) && module ? <CustomModulePage key={module} module={module} /> : <Navigate to="/" replace />;
}

function CustomModulePage({ module }: { module: string }) {
  const userId = useAuthStore(state => state.user?.user_id);
  const modules = useModuleViews();
  const allowed = modules.data?.some(item => item.key === module);
  const [page, setPage] = useState(0);
  const data = useQuery({
    queryKey: ["module-views", userId, module, page],
    queryFn: () => api.get<{ title: string; headings: string[]; rows: (string | number | null)[][] }>(
      `/module-views/${encodeURIComponent(module)}`, { params: { skip: page * pageSize, limit: pageSize } },
    ).then(response => ({ ...response.data, hasMore: response.headers["x-has-more"] === "true" })),
    enabled: allowed === true,
    retry: false,
    refetchOnWindowFocus: "always",
  });
  return <div className="page">
    {modules.isPending ? <Spinner /> : modules.isError || !allowed
      ? <EmptyState icon={<BookOpen />} title="Módulo no disponible" description={modules.isError ? apiMessage(modules.error) : "Tu cuenta no tiene acceso de consulta a este módulo."} />
      : data.isError
        ? <p role="alert">{apiMessage(data.error)} <Button onClick={() => void data.refetch()}>Reintentar</Button></p>
        : data.isPending ? <Spinner /> : <>
          <header className="page-header"><h1>{data.data.title}</h1></header>
          {data.data.rows.length ? <section className="table-panel"><div className="table-scroll"><table>
            <thead><tr>{data.data.headings.map(heading => <th key={heading}>{heading}</th>)}</tr></thead>
            <tbody>{data.data.rows.map((row, index) => <tr key={index}>{row.map((value, column) => <td key={column}>{value || "—"}</td>)}</tr>)}</tbody>
          </table></div></section> : <p>No hay registros en esta página.</p>}
          {(page > 0 || data.data.hasMore) && <div className="form-actions">
            <Button variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</Button>
            <span>Página {page + 1}</span>
            <Button variant="secondary" disabled={!data.data.hasMore} onClick={() => setPage(page + 1)}>Siguiente</Button>
          </div>}
        </>}
  </div>;
}
