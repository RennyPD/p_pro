import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./ui";

/** Client-side pagination footer: "21–40 de 120" with previous / next. */
export function Pager({
  page,
  pageSize,
  total,
  onPage,
  label = "registros",
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  label?: string;
}) {
  if (total <= pageSize) return null;
  const pages = Math.ceil(total / pageSize);
  const first = page * pageSize + 1;
  const last = Math.min(total, (page + 1) * pageSize);
  return (
    <nav className="pager" aria-label="Paginación">
      <span>
        {first}–{last} de {total} {label}
      </span>
      <div>
        <Button
          variant="secondary"
          disabled={page === 0}
          onClick={() => onPage(page - 1)}
          aria-label="Página anterior"
        >
          <ChevronLeft size={16} /> Anterior
        </Button>
        <span className="pager__page">
          Página {page + 1} de {pages}
        </span>
        <Button
          variant="secondary"
          disabled={page >= pages - 1}
          onClick={() => onPage(page + 1)}
          aria-label="Página siguiente"
        >
          Siguiente <ChevronRight size={16} />
        </Button>
      </div>
    </nav>
  );
}
