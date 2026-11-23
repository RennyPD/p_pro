import { Link } from "react-router-dom";
import { DocumentDownload } from "../../components/DocumentDownload";
import type { ApiSchema } from "../../lib/apiTypes";
import { formatMoney } from "../../lib/format";

type Family = ApiSchema<"FamilyAccount">;

/** Students sharing the guardian responsible for payment, with the family balance. */
export function FamilyTab({ family, studentId }: { family: Family; studentId: number }) {
  return (
    <section className="panel finance-family" aria-label="Cuenta familiar">
      <header>
        <div>
          <h2>Cuenta familiar</h2>
          <p className="muted">Responsable de pago: {family.responsible.join(", ")}</p>
        </div>
        <DocumentDownload
          path={`/finance/students/${studentId}/family.pdf`}
          filename={`estado-familiar-${studentId}.pdf`}
          label="Estado familiar PDF"
        />
      </header>
      <ul className="finance-family__list">
        {family.members.map(member => (
          <li key={member.student_id}>
            <div>
              {member.student_id === studentId ? (
                <strong>{member.student_name}</strong>
              ) : (
                <Link to={`/finance/${member.student_id}`}>{member.student_name}</Link>
              )}
              <small>{member.enrollment_number}</small>
            </div>
            <span className={member.overdue_balance > 0 ? "is-low" : undefined}>
              {formatMoney(member.balance)}
              {member.overdue_balance > 0 && (
                <small> · {formatMoney(member.overdue_balance)} vencido</small>
              )}
            </span>
          </li>
        ))}
      </ul>
      <p className="finance-family__total">
        Total familiar <strong>{formatMoney(family.balance)}</strong>
        {family.overdue_balance > 0 && (
          <span> · {formatMoney(family.overdue_balance)} vencido</span>
        )}
      </p>
    </section>
  );
}
