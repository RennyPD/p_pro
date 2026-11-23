import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../../components/ui";
import { Chip } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import { useAccess } from "../../lib/permissions";
import { groupKey, type ClassGroupDetail, type TeacherRow } from "./groupsData";

/** Subjects of the grade, who teaches each one, and the per-period sections. */
export function GroupSubjectsTab({ group }: { group: ClassGroupDetail }) {
  const client = useQueryClient();
  const canManage = useAccess().can("sections.manage");
  const teachers = useQuery({
    queryKey: ["lookup", "teachers-active"],
    queryFn: () =>
      api.get<TeacherRow[]>("/teachers/", { params: { limit: 100 } }).then(r => r.data),
    enabled: canManage,
  });
  const refresh = () => client.invalidateQueries({ queryKey: groupKey(group.class_group_id) });
  const assign = useMutation({
    mutationFn: ({ subjectId, teacherId }: { subjectId: number; teacherId: number }) =>
      api.put(`/class-groups/${group.class_group_id}/subjects/${subjectId}`, {
        teacher_id: teacherId,
      }),
    onSuccess: () => {
      toast.success("Docente asignado");
      refresh();
    },
    onError: error => toast.error(apiMessage(error)),
  });
  const generate = useMutation({
    mutationFn: () =>
      api.post<{ sections_created: number; enrollments_created: number }>(
        `/class-groups/${group.class_group_id}/generate-subjects`,
      ),
    onSuccess: response => {
      const { sections_created, enrollments_created } = response.data;
      toast.success(
        sections_created || enrollments_created
          ? `${sections_created} secciones y ${enrollments_created} inscripciones creadas`
          : "Las materias ya estaban al día",
      );
      refresh();
      client.invalidateQueries({ queryKey: ["sections"] });
    },
    onError: error => toast.error(apiMessage(error)),
  });

  return (
    <section className="panel groups-section" aria-label="Materias del grupo">
      <header className="groups-section__header">
        <div>
          <h2>Materias del grado</h2>
          <p className="muted">
            Cada materia se abre como sección en cada período del año. Los horarios se completan en
            Secciones.
          </p>
        </div>
        {canManage && (
          <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
            <Sparkles size={16} /> Generar materias
          </Button>
        )}
      </header>
      {group.subjects.length === 0 && (
        <p className="muted">
          El plan de estudios no tiene asignaturas en el grado {group.grade_number}. Agrégalas en el
          programa.
        </p>
      )}
      <ul className="groups-list">
        {group.subjects.map(subject => (
          <li key={subject.subject_id}>
            <div>
              <strong>{subject.name}</strong>
              <small>{subject.code}</small>
            </div>
            <Chip tone={subject.sections ? "success" : "default"}>
              {subject.sections ? `${subject.sections} períodos` : "Sin generar"}
            </Chip>
            {canManage ? (
              <label className="groups-teacher">
                <span className="sr-only">Docente de {subject.name}</span>
                <select
                  value={subject.teacher_id ?? ""}
                  disabled={assign.isPending}
                  onChange={event =>
                    assign.mutate({
                      subjectId: subject.subject_id,
                      teacherId: Number(event.target.value),
                    })
                  }
                >
                  <option value="" disabled>
                    Sin docente
                  </option>
                  {teachers.data?.map(teacher => (
                    <option key={teacher.teacher_id} value={teacher.teacher_id}>
                      {teacher.first_name} {teacher.last_name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <small>{subject.teacher_name ?? "Sin docente"}</small>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
