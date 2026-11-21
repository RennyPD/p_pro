import { Badge } from "../../components/ui";
import { attendanceLabels, attendanceTones, isLowAttendance } from "../../lib/academicResult";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDate } from "../../lib/format";
import { Loaded, Meter } from "./guardianShared";
import { percent, useGuardianDetail } from "./guardianData";

type Attendance = ApiSchema<"GuardianAttendance">;
const SHOWN = ["present", "absent", "late", "excused"] as const;

export function GuardianAttendance({ studentId }: { studentId: number }) {
  const query = useGuardianDetail<Attendance>(studentId, "attendance");
  return (
    <Loaded query={query}>
      {data => (
        <>
          <section className="panel guardian-section guardian-lead">
            <div>
              <span className="kicker">{data.period ?? "Todos los períodos"}</span>
              <strong className={isLowAttendance(data.percentage) ? "is-low" : undefined}>
                {percent(data.percentage)}
              </strong>
              <small>
                {data.present_count} de {data.total_count} clases con asistencia
              </small>
            </div>
            <ul className="guardian-counters" aria-label="Registros por estado">
              {SHOWN.map(status => (
                <li key={status}>
                  <b>{data.counts[status] ?? 0}</b>
                  <span>{attendanceLabels[status]}</span>
                </li>
              ))}
            </ul>
          </section>

          {data.courses.length ? (
            <ul className="guardian-cards">
              {data.courses.map(course => (
                <li key={course.enrollment_id} className="panel">
                  <details>
                    <summary>
                      <div>
                        <strong>{course.subject_name}</strong>
                        <small>
                          {course.section_code} · {course.present_count}/{course.total_count} clases
                        </small>
                      </div>
                      <span
                        className={
                          isLowAttendance(course.percentage)
                            ? "guardian-figure is-low"
                            : "guardian-figure"
                        }
                      >
                        {percent(course.percentage)}
                      </span>
                    </summary>
                    <Meter
                      value={course.percentage}
                      label={`Asistencia en ${course.subject_name}`}
                    />
                    {course.records?.length ? (
                      <ul className="guardian-days" aria-label={`Días de ${course.subject_name}`}>
                        {course.records.map(record => (
                          <li key={record.attendance_id}>
                            <span>{formatDate(record.date)}</span>
                            <Badge tone={attendanceTones[record.status] ?? "neutral"}>
                              {attendanceLabels[record.status] ?? record.status}
                            </Badge>
                            {record.note && <small>{record.note}</small>}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">Todavía no hay clases registradas.</p>
                    )}
                  </details>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Sin asignaturas en el período actual.</p>
          )}
        </>
      )}
    </Loaded>
  );
}
