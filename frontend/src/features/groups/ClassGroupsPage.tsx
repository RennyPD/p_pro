import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Users } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { Chip, Progress } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import { useAccess } from "../../lib/permissions";
import type { CareerRow, ClassGroup, SchoolYear, TeacherRow } from "./groupsData";
import "./class-groups.css";

type Option = { id: number; label: string; terms?: number };

const SCHOOL_LEVELS = new Set(["initial", "primary", "secondary"]);

/** Fixed school groups of a year, by program and grade (Fase 3 C). */
export function ClassGroupsPage() {
  const canManage = useAccess().can("sections.manage");
  const [yearId, setYearId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const years = useQuery({
    queryKey: ["school-years", "groups"],
    queryFn: () =>
      api.get<SchoolYear[]>("/school-years/", { params: { limit: 20 } }).then(r => r.data),
  });
  const selectedYear = yearId ?? years.data?.[0]?.school_year_id ?? null;
  const groups = useQuery({
    queryKey: ["class-groups", selectedYear],
    queryFn: () =>
      api
        .get<ClassGroup[]>("/class-groups/", {
          params: { school_year_id: selectedYear, limit: 100 },
        })
        .then(r => r.data),
    enabled: years.isSuccess,
  });

  const byProgram = new Map<string, ClassGroup[]>();
  for (const group of groups.data ?? []) {
    byProgram.set(group.career_name, [...(byProgram.get(group.career_name) ?? []), group]);
  }

  return (
    <div className="page groups-page">
      <header className="page-header">
        <div>
          <span className="kicker">Académico · Escuela</span>
          <h1>Grupos</h1>
          <p className="muted">
            Grupos fijos por grado y año lectivo: estudiantes, materias y promoción.
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setCreating(true)} disabled={!years.data?.length}>
            <Plus size={16} /> Nuevo grupo
          </Button>
        )}
      </header>
      {years.data && years.data.length > 0 && (
        <label className="form-field groups-year">
          <span>Año lectivo</span>
          <select
            value={selectedYear ?? ""}
            onChange={event => setYearId(Number(event.target.value))}
          >
            {years.data.map(year => (
              <option key={year.school_year_id} value={year.school_year_id}>
                {year.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {(years.isPending || groups.isLoading) && <Spinner />}
      {years.data?.length === 0 && (
        <EmptyState
          icon={<Users />}
          title="Aún no hay años lectivos"
          description="Crea el año lectivo y sus períodos en Configuración › Períodos."
        />
      )}
      {groups.data?.length === 0 && (
        <EmptyState
          icon={<Users />}
          title="Sin grupos en este año"
          description="Crea los grupos de cada grado, por ejemplo 1.º A y 1.º B."
        />
      )}
      {[...byProgram.entries()].map(([program, items]) => (
        <section key={program} className="groups-program" aria-label={program}>
          <h2>{program}</h2>
          <ul className="groups-grid">
            {items.map(group => (
              <li key={group.class_group_id}>
                <Link to={`/class-groups/${group.class_group_id}`} className="panel group-card">
                  <div className="group-card__head">
                    <strong>
                      {group.grade_number}.º {group.name}
                    </strong>
                    {group.status !== "active" && <Chip>Cerrado</Chip>}
                  </div>
                  <small>{group.homeroom_teacher_name ?? "Sin titular"}</small>
                  <Progress
                    value={(group.member_count / group.capacity) * 100}
                    label={`${group.member_count} de ${group.capacity} estudiantes`}
                  />
                  <small>
                    {group.member_count} / {group.capacity} estudiantes · {group.room}
                  </small>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {creating && selectedYear && (
        <CreateGroupDialog
          years={years.data ?? []}
          defaultYear={selectedYear}
          onClose={() => setCreating(false)}
        />
      )}
    </div>
  );
}

function CreateGroupDialog({
  years,
  defaultYear,
  onClose,
}: {
  years: SchoolYear[];
  defaultYear: number;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [form, setForm] = useState({
    career_id: "",
    grade_number: "1",
    name: "A",
    school_year_id: String(defaultYear),
    homeroom_teacher_id: "",
    room: "",
    capacity: "35",
  });
  const [failure, setFailure] = useState<string | null>(null);
  const careers = useQuery({
    queryKey: ["lookup", "school-programs"],
    queryFn: () =>
      api.get<CareerRow[]>("/careers/", { params: { limit: 100 } }).then(r =>
        r.data
          .filter(item => SCHOOL_LEVELS.has(item.academic_level))
          .map<Option>(item => ({
            id: item.career_id,
            label: item.name,
            terms: item.duration_terms,
          })),
      ),
  });
  const teachers = useQuery({
    queryKey: ["lookup", "teachers-active"],
    queryFn: () =>
      api
        .get<TeacherRow[]>("/teachers/", { params: { limit: 100 } })
        .then(r =>
          r.data.map<Option>(t => ({ id: t.teacher_id, label: `${t.first_name} ${t.last_name}` })),
        ),
  });
  const create = useMutation({
    mutationFn: () =>
      api.post<ClassGroup>("/class-groups/", {
        career_id: Number(form.career_id),
        grade_number: Number(form.grade_number),
        name: form.name,
        school_year_id: Number(form.school_year_id),
        homeroom_teacher_id: form.homeroom_teacher_id ? Number(form.homeroom_teacher_id) : null,
        room: form.room || "Por asignar",
        capacity: Number(form.capacity),
      }),
    onSuccess: response => {
      toast.success(`Grupo ${response.data.label} creado`);
      client.invalidateQueries({ queryKey: ["class-groups"] });
      onClose();
    },
    onError: error => setFailure(apiMessage(error)),
  });
  const field = (name: keyof typeof form) => ({
    value: form[name],
    disabled: create.isPending,
    onChange: (event: { target: { value: string } }) =>
      setForm(current => ({ ...current, [name]: event.target.value })),
  });
  const terms = careers.data?.find(item => String(item.id) === form.career_id)?.terms ?? 6;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };

  return (
    <Modal title="Nuevo grupo" description="Grupo fijo de un grado" onClose={onClose}>
      <form className="groups-form" onSubmit={submit}>
        <label className="form-field">
          <span>Programa</span>
          <select required {...field("career_id")}>
            <option value="">Selecciona un programa escolar</option>
            {careers.data?.map(item => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        {careers.data?.length === 0 && (
          <p className="muted">
            No hay programas de nivel inicial, primario o secundario. Créalos en Carreras.
          </p>
        )}
        <div className="groups-form__row">
          <label className="form-field">
            <span>Grado</span>
            <select required {...field("grade_number")}>
              {Array.from({ length: terms }, (_, index) => index + 1).map(grade => (
                <option key={grade} value={grade}>
                  {grade}.º
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Grupo</span>
            <input required maxLength={20} {...field("name")} />
          </label>
        </div>
        <label className="form-field">
          <span>Año lectivo</span>
          <select required {...field("school_year_id")}>
            {years.map(year => (
              <option key={year.school_year_id} value={year.school_year_id}>
                {year.name}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Docente titular</span>
          <select {...field("homeroom_teacher_id")}>
            <option value="">Sin titular</option>
            {teachers.data?.map(item => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <div className="groups-form__row">
          <label className="form-field">
            <span>Aula</span>
            <input maxLength={100} placeholder="Por asignar" {...field("room")} />
          </label>
          <label className="form-field">
            <span>Cupo</span>
            <input required type="number" min={1} max={80} {...field("capacity")} />
          </label>
        </div>
        {failure && (
          <p className="form-error" role="alert">
            {failure}
          </p>
        )}
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Guardando…" : "Crear grupo"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
