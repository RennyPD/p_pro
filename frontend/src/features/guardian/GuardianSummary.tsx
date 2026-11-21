import { AlertTriangle, CalendarDays, ChevronRight, FileText } from "lucide-react";
import type { ReactNode } from "react";
import { DocumentDownload } from "../../components/DocumentDownload";
import { describeAverage, isLowAttendance } from "../../lib/academicResult";
import { formatDate, formatMoney, formatTime, todayIso } from "../../lib/format";
import { scheduleBlocks } from "../../lib/schedule";
import { RequestApproval } from "../operations/ApprovalsPage";
import type { StudentOverview } from "./GuardianPortalPage";
import { alertCategories, alertPriorities, percent } from "./guardianData";

type Tab = "attendance" | "grades" | "finance" | "performance";

function Metric({
  label,
  value,
  note,
  tone,
  onOpen,
}: {
  label: string;
  value: ReactNode;
  note: string;
  tone?: "low";
  onOpen?: () => void;
}) {
  const body = (
    <>
      <span>{label}</span>
      <strong className={tone === "low" ? "is-low" : undefined}>{value}</strong>
      <small>{note}</small>
      {onOpen && <ChevronRight className="guardian-metric__go" aria-hidden="true" />}
    </>
  );
  return onOpen ? (
    <button type="button" className="guardian-metric" onClick={onOpen}>
      {body}
    </button>
  ) : (
    <div className="guardian-metric">{body}</div>
  );
}

export function GuardianSummary({
  student,
  onOpen,
}: {
  student: StudentOverview;
  onOpen: (tab: Tab) => void;
}) {
  const { permissions } = student;
  const average = describeAverage({
    finalAverage: student.average_grade,
    finalCount: student.final_grade_count,
    provisionalAverage: student.provisional_average_grade,
    provisionalCount: student.provisional_grade_count,
  });
  const today = todayIso();
  const balance = student.balance ?? 0;

  return (
    <>
      <section className="guardian-metrics" aria-label="Indicadores principales">
        {permissions.academic && (
          <Metric
            label={average.kind === "provisional" ? "Promedio provisional" : "Promedio"}
            value={average.value}
            note={student.metrics_period ?? "Sin período vigente"}
            onOpen={() => onOpen("grades")}
          />
        )}
        {permissions.attendance && (
          <Metric
            label="Asistencia"
            value={percent(student.attendance_percentage)}
            note={`${student.attendance_count} clases`}
            tone={isLowAttendance(student.attendance_percentage) ? "low" : undefined}
            onOpen={() => onOpen("attendance")}
          />
        )}
        {permissions.finance && (
          <Metric
            label="Balance"
            value={formatMoney(balance)}
            note={balance > 0 ? "Pendiente" : "Al día"}
            onOpen={() => onOpen("finance")}
          />
        )}
        {permissions.academic && (
          <Metric
            label="Alertas"
            value={student.alerts.length}
            note={student.alerts.length ? "Requieren atención" : "Sin pendientes"}
            onOpen={() => onOpen("performance")}
          />
        )}
      </section>

      {student.alerts.length > 0 && (
        <section className="panel guardian-section" aria-label="Alertas abiertas">
          <h2>
            <AlertTriangle aria-hidden="true" /> Alertas abiertas
          </h2>
          <ul className="guardian-rows">
            {student.alerts.map(alert => (
              <li key={alert.early_alert_id}>
                <div>
                  <strong>{alertCategories[alert.category] ?? "Otra"}</strong>
                  <p>{alert.reason}</p>
                  {alert.follow_up_date && (
                    <small className={alert.follow_up_date < today ? "is-overdue" : undefined}>
                      {alert.follow_up_date < today
                        ? "Seguimiento vencido desde el"
                        : "Próximo seguimiento:"}{" "}
                      {formatDate(alert.follow_up_date)}
                    </small>
                  )}
                </div>
                <span className="guardian-chip">
                  Prioridad {alertPriorities[alert.severity] ?? "No especificada"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {permissions.academic && (
        <section className="panel guardian-section" aria-label="Horario actual">
          <h2>
            <CalendarDays aria-hidden="true" /> Horario
          </h2>
          {student.schedule.length ? (
            <ul className="guardian-rows">
              {student.schedule.map(item => (
                <li key={item.section_id}>
                  <div>
                    <strong>{item.subject_name}</strong>
                    {scheduleBlocks(item).map((block, index) => (
                      <small key={index}>
                        {block.day_of_week} · {formatTime(block.start_time)}–
                        {formatTime(block.end_time)} · {block.room}
                      </small>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Sin asignaturas en el período actual.</p>
          )}
        </section>
      )}

      <details className="panel guardian-section guardian-documents">
        <summary>
          <FileText aria-hidden="true" /> Documentos
        </summary>
        <div className="guardian-downloads">
          {permissions.academic && (
            <>
              <DocumentDownload
                path={`/documents/students/${student.student_id}/report-card.pdf`}
                filename={`boletin-${student.enrollment_number}.pdf`}
                label="Boletín"
              />
              <DocumentDownload
                path={`/documents/students/${student.student_id}/enrollment-certificate.pdf`}
                filename={`constancia-${student.enrollment_number}.pdf`}
                label="Constancia"
              />
              <DocumentDownload
                path={`/documents/students/${student.student_id}/transcript.pdf`}
                filename={`expediente-${student.enrollment_number}.pdf`}
                label="Expediente"
              />
            </>
          )}
          {permissions.finance && (
            <DocumentDownload
              path={`/documents/students/${student.student_id}/statement.pdf`}
              filename={`estado-${student.enrollment_number}.pdf`}
              label="Estado de cuenta"
            />
          )}
        </div>
      </details>

      <div className="guardian-request">
        <RequestApproval
          resource="student"
          id={student.student_id}
          label={`${student.student_name} · ${student.enrollment_number}`}
        />
      </div>
    </>
  );
}
