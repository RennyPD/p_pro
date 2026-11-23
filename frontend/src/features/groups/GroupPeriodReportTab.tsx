import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DocumentDownload } from "../../components/DocumentDownload";
import { Spinner } from "../../components/ui";
import { Chip } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import type { ClassGroupDetail } from "./groupsData";

type Period = ApiSchema<"AcademicPeriodOut">;
type Report = ApiSchema<"PeriodReport">;

/** Grades of one period for the whole group, with subject averages and pass rates. */
export function GroupPeriodReportTab({ group }: { group: ClassGroupDetail }) {
  const periods = useQuery({
    queryKey: ["periods", "year", group.school_year_id],
    queryFn: () =>
      api
        .get<Period[]>("/periods/", { params: { q: group.school_year_name, limit: 20 } })
        .then(r =>
          r.data
            .filter(period => period.school_year_id === group.school_year_id)
            .sort((a, b) => a.start_date.localeCompare(b.start_date)),
        ),
  });
  const [chosen, setChosen] = useState<number | null>(null);
  const periodId = chosen ?? periods.data?.[0]?.period_id ?? null;
  const report = useQuery({
    queryKey: ["period-report", group.class_group_id, periodId],
    queryFn: () =>
      api
        .get<Report>(`/class-groups/${group.class_group_id}/period-report`, {
          params: { period_id: periodId },
        })
        .then(r => r.data),
    enabled: periodId !== null,
  });
  if (periods.isPending) return <Spinner />;
  if (!periods.data?.length) return <p className="muted">El año lectivo no tiene períodos.</p>;
  const query = `period_id=${periodId}`;
  return (
    <section className="panel groups-section" aria-label="Cuadro del período">
      <header className="groups-section__header">
        <label className="form-field groups-student-pick">
          <span>Período</span>
          <select value={periodId ?? ""} onChange={event => setChosen(Number(event.target.value))}>
            {periods.data.map(period => (
              <option key={period.period_id} value={period.period_id}>
                {period.name}
              </option>
            ))}
          </select>
        </label>
        <div className="groups-actions">
          <DocumentDownload
            path={`/class-groups/${group.class_group_id}/period-report.csv?${query}`}
            filename="cuadro-periodo.csv"
            label="CSV"
          />
          <DocumentDownload
            path={`/class-groups/${group.class_group_id}/period-report.pdf?${query}`}
            filename="cuadro-periodo.pdf"
            label="PDF"
          />
        </div>
      </header>
      {report.isError && <p className="form-error">{apiMessage(report.error)}</p>}
      {report.data && (
        <>
          <p className="muted">
            {report.data.closed ? "Período cerrado" : "Período en curso: notas provisionales"} ·
            Nota mínima {report.data.passing_grade}
          </p>
          <div className="groups-table-wrap">
            <table className="groups-table">
              <thead>
                <tr>
                  <th scope="col">Estudiante</th>
                  {report.data.subjects.map(subject => (
                    <th key={subject.subject_id} scope="col" title={subject.name}>
                      {subject.code}
                    </th>
                  ))}
                  <th scope="col">Asistencia</th>
                </tr>
              </thead>
              <tbody>
                {report.data.students.map(student => (
                  <tr key={student.member_id}>
                    <th scope="row">
                      {student.student_name}
                      <small>{student.enrollment_number}</small>
                    </th>
                    {student.grades.map(grade => (
                      <td
                        key={grade.subject_id}
                        className={
                          grade.value !== null && grade.value < report.data.passing_grade
                            ? "is-low"
                            : undefined
                        }
                      >
                        {grade.label ?? "—"}
                        {grade.value !== null && !grade.final && <small>provisional</small>}
                      </td>
                    ))}
                    <td>{student.attendance === null ? "—" : `${student.attendance} %`}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Promedio</th>
                  {report.data.subjects.map(subject => (
                    <td key={subject.subject_id}>{subject.average ?? "—"}</td>
                  ))}
                  <td />
                </tr>
                <tr>
                  <th scope="row">% aprobados</th>
                  {report.data.subjects.map(subject => (
                    <td key={subject.subject_id}>
                      {subject.passed_percentage === null ? (
                        "—"
                      ) : (
                        <Chip tone={subject.passed_percentage >= 70 ? "success" : "warning"}>
                          {subject.passed_percentage} %
                        </Chip>
                      )}
                    </td>
                  ))}
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
