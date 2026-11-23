import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { DocumentDownload } from "../../components/DocumentDownload";
import { Button, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAccess } from "../../lib/permissions";
import { useAuthStore } from "../../store/auth";
import type { ClassGroupDetail } from "./groupsData";
import { ReportCardView, type ReportCard } from "./ReportCardView";

/** Report cards of the group: preview per student, remarks and the group PDF. */
export function GroupReportCardsTab({ group }: { group: ClassGroupDetail }) {
  const members = group.members.filter(member => member.status === "enrolled");
  const [studentId, setStudentId] = useState<number | null>(members[0]?.student_id ?? null);
  const card = useQuery({
    queryKey: ["report-card", studentId, group.school_year_id],
    queryFn: () =>
      api
        .get<ReportCard>(`/students/${studentId}/report-card`, {
          params: { school_year_id: group.school_year_id },
        })
        .then(r => r.data),
    enabled: studentId !== null,
  });
  const teacherId = useAuthStore(state => state.user?.teacher_id);
  const access = useAccess();
  const canComment =
    (teacherId !== null && teacherId !== undefined && teacherId === group.homeroom_teacher_id) ||
    access.can("grades.manage");

  return (
    <section className="groups-section-stack" aria-label="Boletines del grupo">
      <div className="panel groups-section groups-section__header">
        <label className="form-field groups-student-pick">
          <span>Estudiante</span>
          <select
            value={studentId ?? ""}
            onChange={event => setStudentId(Number(event.target.value))}
          >
            {members.map(member => (
              <option key={member.member_id} value={member.student_id}>
                {member.student_name}
              </option>
            ))}
          </select>
        </label>
        {members.length > 0 && (
          <DocumentDownload
            path={`/class-groups/${group.class_group_id}/report-cards.pdf`}
            filename={`boletines-${group.grade_number}${group.name}-${group.school_year_name}.pdf`}
            label="Boletines del grupo (PDF)"
          />
        )}
      </div>
      {members.length === 0 && <p className="muted">El grupo no tiene estudiantes.</p>}
      {card.isPending && studentId !== null && <Spinner />}
      {card.isError && <p className="form-error">{apiMessage(card.error)}</p>}
      {card.data && <ReportCardView card={card.data} />}
      {card.data && canComment && <RemarksEditor group={group} card={card.data} />}
    </section>
  );
}

function RemarksEditor({ group, card }: { group: ClassGroupDetail; card: ReportCard }) {
  const client = useQueryClient();
  const [periodId, setPeriodId] = useState(card.periods[0]?.period_id ?? 0);
  const current = card.comments.find(comment => comment.period_id === periodId)?.comment ?? "";
  const [text, setText] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      api.put<ReportCard>(
        `/class-groups/${group.class_group_id}/members/${card.member_id}/comments/${periodId}`,
        { comment: text ?? current },
      ),
    onSuccess: response => {
      client.setQueryData(["report-card", card.student_id, group.school_year_id], response.data);
      setText(null);
      toast.success("Observación guardada");
    },
    onError: error => toast.error(apiMessage(error)),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  return (
    <form className="panel groups-section groups-form" onSubmit={submit}>
      <h3>Observaciones del titular</h3>
      <label className="form-field">
        <span>Período</span>
        <select
          value={periodId}
          onChange={event => {
            setPeriodId(Number(event.target.value));
            setText(null);
          }}
        >
          {card.periods.map(period => (
            <option key={period.period_id} value={period.period_id}>
              {period.name}
            </option>
          ))}
        </select>
      </label>
      <label className="form-field">
        <span>Observación para {card.student_name}</span>
        <textarea
          rows={3}
          maxLength={1000}
          value={text ?? current}
          onChange={event => setText(event.target.value)}
        />
      </label>
      <div className="form-actions">
        <Button type="submit" disabled={save.isPending || text === null}>
          Guardar observación
        </Button>
      </div>
    </form>
  );
}
