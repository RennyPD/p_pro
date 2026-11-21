import { Badge } from "../../components/ui";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatDate } from "../../lib/format";
import { Loaded, Meter } from "./guardianShared";
import { alertCategories, alertPriorities, percent, useGuardianDetail } from "./guardianData";

type Performance = ApiSchema<"GuardianPerformance">;

export function GuardianPerformance({ studentId }: { studentId: number }) {
  const query = useGuardianDetail<Performance>(studentId, "performance");
  return (
    <Loaded query={query}>
      {data => (
        <>
          <section className="panel guardian-section" aria-label="Promedio por período">
            <h2>Promedio por período</h2>
            {data.periods.length ? (
              <ul className="guardian-trend">
                {data.periods.map(period => {
                  const value = period.average_grade ?? period.provisional_average_grade;
                  return (
                    <li key={period.period}>
                      <div>
                        <strong>{period.period}</strong>
                        <small>
                          {period.course_count} asignaturas
                          {period.attendance_percentage !== null &&
                            period.attendance_percentage !== undefined &&
                            ` · asistencia ${percent(period.attendance_percentage)}`}
                        </small>
                      </div>
                      <Meter value={value} label={`Promedio de ${period.period}`} />
                      <span className="guardian-figure">
                        {value ?? "—"}
                        {period.average_grade === null && value !== null && (
                          <small> provisional</small>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="muted">Todavía no hay resultados.</p>
            )}
          </section>

          <section className="panel guardian-section" aria-label="Alertas abiertas">
            <h2>Alertas</h2>
            {data.alerts.length ? (
              <ul className="guardian-rows">
                {data.alerts.map(alert => (
                  <li key={alert.early_alert_id}>
                    <div>
                      <strong>{alertCategories[alert.category] ?? "Otra"}</strong>
                      <p>{alert.reason}</p>
                      {alert.follow_up_date && (
                        <small>Seguimiento: {formatDate(alert.follow_up_date)}</small>
                      )}
                    </div>
                    <Badge
                      tone={
                        alert.severity === "high" || alert.severity === "critical"
                          ? "danger"
                          : "warning"
                      }
                    >
                      {alertPriorities[alert.severity] ?? "—"}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Sin alertas abiertas.</p>
            )}
          </section>
        </>
      )}
    </Loaded>
  );
}
