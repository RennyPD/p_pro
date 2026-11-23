import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Plus, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button, Modal } from "../../components/ui";
import { Chip, Section } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDate } from "../../lib/format";
import { useAccess } from "../../lib/permissions";

type SchoolYear = ApiSchema<"SchoolYearOut">;

const schemeLabels: Record<string, string> = {
  quarters: "4 períodos (MINERD)",
  trimesters: "3 trimestres",
  bimesters: "6 bimestres",
  quadrimesters: "3 cuatrimestres",
  semesters: "2 semestres",
  annual: "Anual",
};

const emptyForm = { name: "", start_date: "", end_date: "", period_scheme: "" };

/**
 * School years group their periods. An administrator creates the year and
 * generates its periods, with the dates split evenly by the year's scheme.
 */
export function SchoolYearsPanel() {
  const client = useQueryClient();
  const canWrite = useAccess().can("settings.manage");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [failure, setFailure] = useState<string | null>(null);
  const years = useQuery({
    queryKey: ["school-years"],
    queryFn: () =>
      api.get<SchoolYear[]>("/school-years/", { params: { limit: 6 } }).then(r => r.data),
  });
  const refresh = () => {
    client.invalidateQueries({ queryKey: ["school-years"] });
    client.invalidateQueries({ queryKey: ["periods"] });
    client.invalidateQueries({ queryKey: ["lookup", "/periods/"] });
  };
  const create = useMutation({
    mutationFn: () =>
      api.post<SchoolYear>("/school-years/", {
        ...form,
        period_scheme: form.period_scheme || null,
      }),
    onSuccess: response => {
      toast.success(`Año lectivo ${response.data.name} creado`);
      setCreating(false);
      setForm(emptyForm);
      setFailure(null);
      refresh();
    },
    onError: error => setFailure(apiMessage(error)),
  });
  const generate = useMutation({
    mutationFn: (year: SchoolYear) =>
      api.post(`/school-years/${year.school_year_id}/generate-periods`),
    onSuccess: (response, year) => {
      toast.success(`${response.data.length} períodos generados para ${year.name}`);
      refresh();
    },
    onError: error => toast.error(apiMessage(error)),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };
  const field = (name: keyof typeof emptyForm) => ({
    value: form[name],
    disabled: create.isPending,
    onChange: (event: { target: { value: string } }) =>
      setForm(current => ({ ...current, [name]: event.target.value })),
  });

  return (
    <Section
      title="Años lectivos"
      kicker="Calendario"
      icon={<CalendarRange size={18} aria-hidden="true" />}
      className="school-years"
      action={
        canWrite && (
          <Button variant="secondary" onClick={() => setCreating(true)}>
            <Plus size={16} /> Nuevo año
          </Button>
        )
      }
    >
      {years.isError && <p className="form-error">{apiMessage(years.error)}</p>}
      {years.data && years.data.length === 0 && (
        <p className="muted">
          Crea el año lectivo y genera sus períodos con las fechas ya repartidas.
        </p>
      )}
      <ul className="school-years__list">
        {years.data?.map(year => (
          <li key={year.school_year_id}>
            <div>
              <strong>{year.name}</strong>
              <small>
                {formatDate(year.start_date)} – {formatDate(year.end_date)}
              </small>
            </div>
            <Chip tone={year.period_count ? "success" : "default"}>
              {year.period_count
                ? `${year.period_count} períodos`
                : (schemeLabels[year.period_scheme] ?? year.period_scheme)}
            </Chip>
            {canWrite && !year.period_count && (
              <Button
                variant="ghost"
                disabled={generate.isPending}
                onClick={() => generate.mutate(year)}
                aria-label={`Generar períodos de ${year.name}`}
              >
                <Sparkles size={16} /> Generar períodos
              </Button>
            )}
          </li>
        ))}
      </ul>
      {creating && (
        <Modal
          title="Nuevo año lectivo"
          description="Las fechas cubren todo el año; los períodos se reparten dentro."
          onClose={() => {
            if (!create.isPending) setCreating(false);
          }}
        >
          <form className="school-years__form" onSubmit={submit}>
            <label className="form-field">
              <span>Nombre</span>
              <input required maxLength={20} placeholder="2026-2027" {...field("name")} />
            </label>
            <label className="form-field">
              <span>Inicio</span>
              <input required type="date" {...field("start_date")} />
            </label>
            <label className="form-field">
              <span>Fin</span>
              <input required type="date" {...field("end_date")} />
            </label>
            <label className="form-field">
              <span>Esquema de períodos</span>
              <select {...field("period_scheme")}>
                <option value="">Según el tipo de institución</option>
                {Object.entries(schemeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            {failure && (
              <p className="form-error" role="alert">
                {failure}
              </p>
            )}
            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={create.isPending}
                onClick={() => setCreating(false)}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Guardando…" : "Crear año"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </Section>
  );
}
