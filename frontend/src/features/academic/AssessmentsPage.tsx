import { confirmAction } from "../../lib/confirm";
import { useQuery } from "@tanstack/react-query";
import { BookCheck } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./assessments.css";
import { type Section } from "./assessmentsShared";
import { SectionBook } from "./SectionBook";

export function AssessmentsPage() {
  const user = useAuthStore(state => state.user);
  const [params] = useSearchParams();
  const [selected, setSelected] = useState(() => Number(params.get("section")) || 0);
  const sections = useQuery<Section[]>({
    queryKey: ["assessment-sections", user?.user_id],
    queryFn: async () => {
      const items: Section[] = [];
      for (let skip = 0; ; skip += 100) {
        const response = await api.get<Section[]>("/sections/", { params: { skip, limit: 100 } });
        items.push(...response.data);
        if (response.data.length < 100) return items;
      }
    },
  });
  const section = sections.data?.find(item => item.section_id === selected) ?? sections.data?.[0];
  if (sections.isLoading)
    return (
      <div className="page">
        <Spinner />
      </div>
    );
  if (sections.error)
    return (
      <div className="page">
        <EmptyState
          icon={<BookCheck />}
          title="No pudimos cargar las secciones"
          description={apiMessage(sections.error)}
        />
      </div>
    );
  if (!section)
    return (
      <div className="page">
        <EmptyState
          icon={<BookCheck />}
          title="No hay secciones disponibles"
          description="Asigna un docente a una sección para preparar su plan de evaluación."
        />
      </div>
    );
  return (
    <div className="page assessments-page">
      <header className="page-header">
        <div>
          <span className="kicker">Evaluación académica</span>
          <h1>Plan y libro de notas</h1>
          <p>Configura la distribución, prepara notas y publica resultados de cada sección.</p>
        </div>
        <label className="form-field">
          <span>Sección y asignatura</span>
          <select
            value={section.section_id}
            onChange={async event => {
              if (
                document.querySelector('[data-unsaved-grades="true"]') &&
                !(await confirmAction(
                  "Hay cambios sin guardar. ¿Cambiar de sección y descartarlos?",
                ))
              )
                return;
              setSelected(Number(event.target.value));
            }}
          >
            {sections.data?.map(item => (
              <option key={item.section_id} value={item.section_id}>
                {item.code} · {item.subject_name} · {item.period_name || "Sin período"}
              </option>
            ))}
          </select>
        </label>
      </header>
      <SectionBook key={section.section_id + ":" + user?.user_id} section={section} />
    </div>
  );
}
