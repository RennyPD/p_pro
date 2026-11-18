import { StudentDocuments } from "./StudentDossierActions";
import { RequestApproval } from "../operations/ApprovalsPage";
import { DocumentDownload } from "../../components/DocumentDownload";
import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { EmptyState, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";

export function TranscriptPage() {
  const id = useAuthStore(s => s.user?.student_id);
  const query = useQuery({
    queryKey: ["transcript", id],
    queryFn: () => api.get(`/records/students/${id}/transcript`).then(r => r.data),
    enabled: Boolean(id),
  });
  if (query.isLoading)
    return (
      <div className="page">
        <Spinner />
      </div>
    );
  if (query.error || !query.data)
    return (
      <div className="page">
        <EmptyState
          icon={<FileText />}
          title="No pudimos abrir tu expediente"
          description={apiMessage(query.error)}
        />
      </div>
    );
  const record = query.data;
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="kicker">Documento oficial</span>
          <h1>Mi expediente</h1>
          <p>
            {record.student_name} · {record.enrollment_number}
          </p>
        </div>
        <div className="form-actions">
          <DocumentDownload
            path={`/documents/students/${id}/transcript.pdf`}
            filename="expediente.pdf"
            label="Expediente PDF"
          />
          <DocumentDownload
            path={`/documents/students/${id}/enrollment-certificate.pdf`}
            filename="constancia.pdf"
            label="Constancia PDF"
          />
          <DocumentDownload
            path={`/documents/students/${id}/report-card.pdf`}
            filename="boletin.pdf"
            label="Boletín PDF"
          />
          {id && <RequestApproval resource="student" id={id} label={record.enrollment_number} />}
        </div>
      </header>
      <section className="profile-metrics">
        <article>
          <small>Promedio acumulado</small>
          <strong>{record.cumulative_average}</strong>
        </article>
        <article>
          <small>Créditos aprobados</small>
          <strong>{record.earned_credits}</strong>
        </article>
        <article>
          <small>Condición</small>
          <strong>{record.academic_standing}</strong>
        </article>
      </section>
      <p>
        {record.recognized_credits ?? 0} créditos reconocidos por equivalencia. No alteran el
        promedio ni los créditos intentados.
      </p>
      {record.unverified_credit_courses > 0 && (
        <p>
          Inscripciones con créditos por verificar: {record.unverified_credit_courses}. Los totales
          incluyen los créditos respaldados.
        </p>
      )}
      <section className="table-panel">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Período</th>
                <th>Asignatura</th>
                <th>Créditos</th>
                <th>Resultado publicado</th>
                <th>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {record.courses.map((course: any, index: number) => (
                <tr key={`${course.period}-${course.subject_code}-${index}`}>
                  <td>{course.period}</td>
                  <td>
                    <b>{course.subject_code}</b> · {course.subject_name}
                  </td>
                  <td>{course.credits ?? "Por verificar"}</td>
                  <td>
                    {course.recognition_type === "equivalence"
                      ? `Sin nota · origen ${course.origin_subject_code}`
                      : (course.average ?? "—")}
                  </td>
                  <td>
                    {{
                      recognized: "Reconocida por equivalencia",
                      passed: "Aprobada",
                      failed: "Reprobada",
                      in_progress: "Provisional",
                    }[course.result as string] ?? course.result}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {id && <StudentDocuments studentId={String(id)} />}
    </div>
  );
}
