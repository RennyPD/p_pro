import { StudentDocuments } from "./StudentDossierActions";
import { RequestApproval } from "../operations/ApprovalsPage";
import { DocumentDownload } from "../../components/DocumentDownload";
import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { Badge, EmptyState, Spinner } from "../../components/ui";

import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { gradeText } from "../../lib/grades";
import { SchoolReportCard } from "../groups/SchoolReportCard";
import { useAuthStore } from "../../store/auth";
import { describeAverage, resultLabel, resultTone, standingLabel } from "../../lib/academicResult";

export function TranscriptPage() {
  const id = useAuthStore(s => s.user?.student_id);
  const query = useQuery({
    queryKey: ["transcript", id],
    queryFn: () =>
      api
        .get<ApiSchema<"AcademicTranscript">>(`/records/students/${id}/transcript`)
        .then(r => r.data),
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
  const average = describeAverage({
    finalAverage: record.cumulative_average,
    finalCount: record.final_result_count,
    provisionalAverage: record.provisional_average,
    provisionalCount: record.provisional_result_count,
  });
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
      {id && <SchoolReportCard studentId={id} />}
      <section className="transcript-metrics">
        <article>
          <span>
            {average.kind === "provisional"
              ? "Promedio acumulado provisional"
              : "Promedio acumulado"}
          </span>
          <strong>{average.value}</strong>
          <small>{average.note}</small>
        </article>
        <article>
          <span>Créditos aprobados</span>
          <strong>{record.earned_credits}</strong>
          <small>
            {record.unverified_credit_courses > 0
              ? `${record.unverified_credit_courses} asignaturas con créditos por verificar`
              : record.recognized_credits > 0
                ? `Incluye ${record.recognized_credits} por equivalencia`
                : "Créditos confirmados"}
          </small>
        </article>
        {record.academic_index !== null && record.academic_index !== undefined && (
          <article>
            <span>Índice académico</span>
            <strong>{record.academic_index.toFixed(2)}</strong>
            <small>Ponderado por créditos · {record.grading_scale_name}</small>
          </article>
        )}
        <article>
          <span>Condición académica</span>
          <strong className="transcript-metrics__text">
            {standingLabel(record.academic_standing)}
          </strong>
          {record.academic_standing === "no_final_results" && (
            <small>Se calcula cuando cierran las evaluaciones.</small>
          )}
        </article>
      </section>
      <section className="table-panel">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Período</th>
                <th>Asignatura</th>
                <th>Créditos</th>
                <th>Nota</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {record.courses.map((course: any, index: number) => (
                <tr key={`${course.period}-${course.subject_code}-${index}`}>
                  <td>{course.period}</td>
                  <td>
                    <b>{course.subject_code}</b> · {course.subject_name}
                  </td>
                  <td>{course.credits ?? <span className="muted">Por verificar</span>}</td>
                  <td>
                    {course.recognition_type === "equivalence"
                      ? `Sin nota · origen ${course.origin_subject_code}`
                      : gradeText(course.average, course.average_label)}
                  </td>
                  <td>
                    <Badge tone={resultTone(course.result)}>{resultLabel(course.result)}</Badge>
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
