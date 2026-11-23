import { DocumentDownload } from "../../components/DocumentDownload";
import { Chip } from "../../components/visual";
import type { ApiSchema } from "../../lib/apiTypes";
import "./report-card.css";

export type ReportCard = ApiSchema<"ReportCard">;

const statusTone = (status: string) =>
  status === "passed"
    ? "success"
    : status === "failed"
      ? "danger"
      : status === "incomplete"
        ? "default"
        : "warning";

/**
 * School report card (Fase 3 F): subjects by period, recovery grades, final
 * grade, attendance, remarks and the year result. Periods not final yet show
 * "En curso" (families see only final results).
 */
export function ReportCardView({
  card,
  download = true,
}: {
  card: ReportCard;
  download?: boolean;
}) {
  const school = card.institution;
  const ids = [
    school.school_code && `Código ${school.school_code}`,
    school.regional && `Regional ${school.regional}`,
    school.district && `Distrito ${school.district}`,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <article className="panel report-card" aria-label={`Boletín de ${card.student_name}`}>
      <header className="report-card__header">
        <div>
          <span className="kicker">
            {school.name}
            {ids && ` · ${ids}`}
          </span>
          <h2>{card.student_name}</h2>
          <p className="muted">
            {card.enrollment_number} · {card.group_label} · Año lectivo {card.school_year}
            {card.homeroom_teacher && ` · Titular: ${card.homeroom_teacher}`}
          </p>
        </div>
        <div className="report-card__result">
          <Chip
            tone={
              card.result === "promoted"
                ? "success"
                : card.result === "repeated"
                  ? "danger"
                  : "default"
            }
          >
            {card.result_label}
          </Chip>
          {download && (
            <DocumentDownload
              path={`/students/${card.student_id}/report-card.pdf`}
              filename={`boletin-${card.enrollment_number}-${card.school_year}.pdf`}
              label="Boletín PDF"
            />
          )}
        </div>
      </header>
      <div className="report-card__table-wrap">
        <table className="report-card__table">
          <thead>
            <tr>
              <th scope="col">Asignatura</th>
              {card.periods.map(period => (
                <th key={period.period_id} scope="col" title={period.name}>
                  {period.short}
                </th>
              ))}
              <th scope="col">Promedio</th>
              <th scope="col">Completiva</th>
              <th scope="col">Extraordinaria</th>
              <th scope="col">Final</th>
              <th scope="col">Situación</th>
            </tr>
          </thead>
          <tbody>
            {card.subjects.map(subject => (
              <tr key={subject.subject_id}>
                <th scope="row">{subject.name}</th>
                {subject.periods.map((value, index) => (
                  <td key={index}>
                    {value ?? (
                      <small className="muted">
                        {card.periods[index]?.closed ? "—" : "En curso"}
                      </small>
                    )}
                  </td>
                ))}
                <td>{subject.average_label ?? "—"}</td>
                <td>{subject.completivo ?? "—"}</td>
                <td>{subject.extraordinario ?? "—"}</td>
                <td>
                  <strong>{subject.final ?? "—"}</strong>
                </td>
                <td>
                  <Chip tone={statusTone(subject.status)}>{subject.status_label}</Chip>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="report-card__table-wrap">
        <table className="report-card__table report-card__attendance">
          <caption>Asistencia</caption>
          <thead>
            <tr>
              <th scope="col">Período</th>
              <th scope="col">Presente</th>
              <th scope="col">Tardanzas</th>
              <th scope="col">Ausencias</th>
              <th scope="col">Excusas</th>
              <th scope="col">%</th>
            </tr>
          </thead>
          <tbody>
            {card.attendance.map(row => (
              <tr key={row.period}>
                <th scope="row">{row.period}</th>
                <td>{row.present}</td>
                <td>{row.late}</td>
                <td>{row.absent}</td>
                <td>{row.excused}</td>
                <td>{row.percentage === null ? "—" : `${row.percentage} %`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {card.comments.length > 0 && (
        <section className="report-card__comments" aria-label="Observaciones del titular">
          <h3>Observaciones del titular</h3>
          {card.comments.map(comment => (
            <p key={comment.period_id}>
              <b>{comment.period}:</b> {comment.comment}
            </p>
          ))}
        </section>
      )}
      <p className="muted report-card__note">
        Nota mínima {card.passing_grade} ({card.scale_name}). Los períodos sin cerrar aparecen «En
        curso».
      </p>
    </article>
  );
}
