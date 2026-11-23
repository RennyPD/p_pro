import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button, Modal, Spinner } from "../../components/ui";
import { Chip } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import { gradeText } from "../../lib/grades";
import { useAccess } from "../../lib/permissions";
import {
  groupKey,
  resultLabels,
  type ClassGroup,
  type ClassGroupDetail,
  type Promotion,
  type Reinscription,
} from "./groupsData";

const choices = ["promoted", "completivo", "extraordinario", "repeated"] as const;

type Recovery = {
  memberId: number;
  student: string;
  subjectId: number;
  subject: string;
  kind: string;
};

/**
 * Year-end: the system proposes a result from the annual average of each
 * subject; a person confirms it, then re-enrolls the group in the next year.
 */
export function GroupPromotionTab({ group }: { group: ClassGroupDetail }) {
  const client = useQueryClient();
  const access = useAccess();
  const canOverride = access.can("finance.manage");
  const canGrade = access.can("grades.manage");
  const [recovery, setRecovery] = useState<Recovery | null>(null);
  const key = [...groupKey(group.class_group_id), "promotion"];
  const proposal = useQuery({
    queryKey: key,
    queryFn: () =>
      api.get<Promotion>(`/class-groups/${group.class_group_id}/promotion`).then(r => r.data),
  });
  const [decisions, setDecisions] = useState<Record<number, string>>({});
  const [target, setTarget] = useState("");
  const [override, setOverride] = useState("");
  const [outcome, setOutcome] = useState<Reinscription | null>(null);
  const targets = useQuery({
    queryKey: ["class-groups", "targets", group.career_id],
    queryFn: () =>
      api
        .get<ClassGroup[]>("/class-groups/", { params: { limit: 100 } })
        .then(r => r.data.filter(item => item.school_year_id !== group.school_year_id)),
  });
  const confirm = useMutation({
    mutationFn: () =>
      api.post<Promotion>(`/class-groups/${group.class_group_id}/promotion`, {
        decisions: Object.entries(decisions).map(([member_id, result]) => ({
          member_id: Number(member_id),
          result,
        })),
      }),
    onSuccess: response => {
      client.setQueryData(key, response.data);
      client.invalidateQueries({ queryKey: groupKey(group.class_group_id) });
      setDecisions({});
      toast.success("Resultados confirmados");
    },
    onError: error => toast.error(apiMessage(error)),
  });
  const ready = (proposal.data?.members ?? []).filter(
    row => row.confirmed && (row.result === "promoted" || row.result === "repeated"),
  );
  const reinscribe = useMutation({
    mutationFn: () =>
      api.post<Reinscription>(`/class-groups/${group.class_group_id}/reinscribe`, {
        target_group_id: Number(target),
        member_ids: ready.map(row => row.member_id),
        override_reason: override.trim() || null,
      }),
    onSuccess: response => {
      setOutcome(response.data);
      client.invalidateQueries({ queryKey: ["class-groups"] });
      toast.success(`${response.data.reinscribed.length} estudiantes reinscritos`);
    },
    onError: error => toast.error(apiMessage(error)),
  });

  if (proposal.isPending) return <Spinner />;
  if (proposal.isError) return <p className="form-error">{apiMessage(proposal.error)}</p>;
  const data = proposal.data;

  return (
    <>
      <section className="panel groups-section" aria-label="Promoción">
        <header className="groups-section__header">
          <div>
            <h2>Promoción</h2>
            <p className="muted">
              Promedio anual de cada materia frente a la nota mínima ({data.passing_grade},{" "}
              {data.scale_name}). Completivo: {data.completivo_average_weight} % promedio +{" "}
              {100 - data.completivo_average_weight} % examen; extraordinario:{" "}
              {data.extraordinario_average_weight} % + {100 - data.extraordinario_average_weight} %.
              Revisa la propuesta y confirma el resultado de cada estudiante.
            </p>
          </div>
          <Button
            onClick={() => confirm.mutate()}
            disabled={!Object.keys(decisions).length || confirm.isPending}
          >
            <CheckCircle2 size={16} /> Confirmar resultados
          </Button>
        </header>
        {data.members.length === 0 && <p className="muted">El grupo no tiene estudiantes.</p>}
        <div className="groups-table-wrap">
          <table className="groups-table">
            <thead>
              <tr>
                <th scope="col">Estudiante</th>
                {data.members[0]?.subjects.map(subject => (
                  <th key={subject.subject_id} scope="col" title={subject.name}>
                    {subject.code}
                  </th>
                ))}
                <th scope="col">Propuesta</th>
                <th scope="col">Resultado</th>
              </tr>
            </thead>
            <tbody>
              {data.members.map(row => {
                const proposed = row.proposal ? resultLabels[row.proposal] : null;
                const value = decisions[row.member_id] ?? (row.confirmed ? row.result : "");
                return (
                  <tr key={row.member_id}>
                    <th scope="row">
                      {row.student_name}
                      <small>{row.enrollment_number}</small>
                    </th>
                    {row.subjects.map(subject => (
                      <td
                        key={subject.subject_id}
                        className={subject.passed === false ? "is-low" : undefined}
                      >
                        {gradeText(subject.average, subject.average_label, true)}
                        {!subject.complete && <small>incompleta</small>}
                        {subject.completivo !== null && subject.completivo !== undefined && (
                          <small>Completivo {subject.completivo}</small>
                        )}
                        {subject.extraordinario !== null &&
                          subject.extraordinario !== undefined && (
                            <small>Extraordinario {subject.extraordinario}</small>
                          )}
                        {canGrade &&
                          (subject.status === "completivo" ||
                            subject.status === "extraordinario") && (
                            <button
                              type="button"
                              className="groups-recovery"
                              onClick={() =>
                                setRecovery({
                                  memberId: row.member_id,
                                  student: row.student_name,
                                  subjectId: subject.subject_id,
                                  subject: subject.name,
                                  kind: subject.status,
                                })
                              }
                            >
                              Registrar {subject.status}
                            </button>
                          )}
                      </td>
                    ))}
                    <td>
                      {proposed ? (
                        <Chip tone={proposed.tone}>{proposed.label}</Chip>
                      ) : (
                        <small className="muted">Faltan notas finales</small>
                      )}
                    </td>
                    <td>
                      <select
                        aria-label={`Resultado de ${row.student_name}`}
                        value={value}
                        onChange={event =>
                          setDecisions(current => ({
                            ...current,
                            [row.member_id]: event.target.value,
                          }))
                        }
                      >
                        <option value="" disabled>
                          Sin confirmar
                        </option>
                        {choices.map(choice => (
                          <option key={choice} value={choice}>
                            {resultLabels[choice].label}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel groups-section" aria-label="Reinscripción">
        <header className="groups-section__header">
          <div>
            <h2>Reinscripción</h2>
            <p className="muted">
              Los promovidos pasan al grado siguiente y quienes repiten, al mismo grado. Los
              completivos se resuelven antes de reinscribir.
            </p>
          </div>
        </header>
        <div className="groups-form groups-form--inline">
          <label className="form-field">
            <span>Grupo de destino</span>
            <select value={target} onChange={event => setTarget(event.target.value)}>
              <option value="">Selecciona un grupo del año siguiente</option>
              {targets.data?.map(item => (
                <option key={item.class_group_id} value={item.class_group_id}>
                  {item.label} · {item.school_year_name}
                </option>
              ))}
            </select>
          </label>
          {canOverride && (
            <label className="form-field">
              <span>Excepción al bloqueo financiero (opcional)</span>
              <input
                maxLength={250}
                value={override}
                placeholder="Motivo, si autorizas a estudiantes con bloqueo"
                onChange={event => setOverride(event.target.value)}
              />
            </label>
          )}
          <Button
            onClick={() => reinscribe.mutate()}
            disabled={!target || !ready.length || reinscribe.isPending}
          >
            <Send size={16} /> Reinscribir {ready.length} estudiantes
          </Button>
        </div>
        {outcome && (
          <div className="groups-outcome" role="status">
            {outcome.reinscribed.length > 0 && <p>Reinscritos: {outcome.reinscribed.join(", ")}</p>}
            {outcome.blocked.map(item => (
              <p key={item.student_name} className="form-error">
                {item.student_name}: {item.reason}
              </p>
            ))}
          </div>
        )}
      </section>
      {recovery && (
        <RecoveryDialog
          groupId={group.class_group_id}
          recovery={recovery}
          onClose={() => setRecovery(null)}
          onSaved={proposal => client.setQueryData(key, proposal)}
        />
      )}
    </>
  );
}

function RecoveryDialog({
  groupId,
  recovery,
  onClose,
  onSaved,
}: {
  groupId: number;
  recovery: Recovery;
  onClose: () => void;
  onSaved: (proposal: Promotion) => void;
}) {
  const [grade, setGrade] = useState("");
  const [failure, setFailure] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      api.post<Promotion>(`/class-groups/${groupId}/members/${recovery.memberId}/recovery`, {
        subject_id: recovery.subjectId,
        kind: recovery.kind,
        exam_grade: Number(grade),
      }),
    onSuccess: response => {
      onSaved(response.data);
      toast.success(`Examen ${recovery.kind} registrado`);
      onClose();
    },
    onError: error => setFailure(apiMessage(error)),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  return (
    <Modal
      title={`Examen ${recovery.kind}`}
      description={`${recovery.student} · ${recovery.subject}`}
      onClose={onClose}
    >
      <form className="groups-form" onSubmit={submit}>
        <label className="form-field">
          <span>Nota del examen (0–100)</span>
          <input
            required
            type="number"
            min={0}
            max={100}
            step="0.01"
            value={grade}
            onChange={event => setGrade(event.target.value)}
          />
        </label>
        <p className="muted">
          La calificación final combina el promedio anual y el examen con los pesos de la escala.
        </p>
        {failure && (
          <p className="form-error" role="alert">
            {failure}
          </p>
        )}
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={save.isPending || grade === ""}>
            Guardar
          </Button>
        </div>
      </form>
    </Modal>
  );
}
