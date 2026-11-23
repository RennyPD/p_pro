import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft, UserMinus, UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button, Modal } from "../../components/ui";
import { Avatar, Chip } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import { formatDate } from "../../lib/format";
import { useAccess } from "../../lib/permissions";
import {
  groupKey,
  memberStatus,
  resultLabels,
  type ClassGroup,
  type ClassGroupDetail,
  type GroupMember,
  type StudentRow,
} from "./groupsData";

type Action = { kind: "withdraw" | "transfer"; member: GroupMember };

export function GroupMembersTab({ group }: { group: ClassGroupDetail }) {
  const access = useAccess();
  const canManage = access.can("enrollments.manage");
  const [adding, setAdding] = useState(false);
  const [action, setAction] = useState<Action | null>(null);

  return (
    <section className="panel groups-section" aria-label="Estudiantes del grupo">
      <header className="groups-section__header">
        <h2>Estudiantes</h2>
        {canManage && group.status === "active" && (
          <Button variant="secondary" onClick={() => setAdding(true)}>
            <UserPlus size={16} /> Inscribir estudiante
          </Button>
        )}
      </header>
      {group.members.length === 0 && (
        <p className="muted">Inscribe a los estudiantes del grado para empezar.</p>
      )}
      <ul className="groups-list">
        {group.members.map(member => {
          const result = resultLabels[member.result] ?? resultLabels.pending;
          return (
            <li key={member.member_id} className={member.status !== "enrolled" ? "is-muted" : ""}>
              <Avatar name={member.student_name} size="sm" />
              <div>
                <strong>{member.student_name}</strong>
                <small>
                  {member.enrollment_number} · desde {formatDate(member.joined_on)}
                </small>
              </div>
              {member.financial_hold && <Chip tone="warning">Bloqueo financiero</Chip>}
              {member.status !== "enrolled" ? (
                <Chip>{memberStatus[member.status] ?? member.status}</Chip>
              ) : (
                member.result !== "pending" && <Chip tone={result.tone}>{result.label}</Chip>
              )}
              {canManage && member.status === "enrolled" && (
                <div className="groups-actions">
                  <Button
                    variant="ghost"
                    aria-label={`Trasladar a ${member.student_name}`}
                    onClick={() => setAction({ kind: "transfer", member })}
                  >
                    <ArrowRightLeft size={16} />
                  </Button>
                  <Button
                    variant="ghost"
                    aria-label={`Retirar a ${member.student_name}`}
                    onClick={() => setAction({ kind: "withdraw", member })}
                  >
                    <UserMinus size={16} />
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {adding && <AddMemberDialog group={group} onClose={() => setAdding(false)} />}
      {action && (
        <MemberActionDialog group={group} action={action} onClose={() => setAction(null)} />
      )}
    </section>
  );
}

function AddMemberDialog({ group, onClose }: { group: ClassGroupDetail; onClose: () => void }) {
  const client = useQueryClient();
  const canOverride = useAccess().can("finance.manage");
  const [term, setTerm] = useState("");
  const [studentId, setStudentId] = useState<number | null>(null);
  const [override, setOverride] = useState("");
  const [failure, setFailure] = useState<string | null>(null);
  const students = useQuery({
    queryKey: ["group-candidates", group.career_id, term],
    queryFn: () =>
      api
        .get<
          StudentRow[]
        >("/students/", { params: { career_id: group.career_id, active: true, q: term, limit: 20 } })
        .then(r => r.data),
  });
  const chosen = students.data?.find(item => item.student_id === studentId);
  const add = useMutation({
    mutationFn: () =>
      api.post(`/class-groups/${group.class_group_id}/members`, {
        student_id: studentId,
        override_reason: override.trim() || null,
      }),
    onSuccess: () => {
      toast.success("Estudiante inscrito en el grupo y sus materias");
      client.invalidateQueries({ queryKey: groupKey(group.class_group_id) });
      client.invalidateQueries({ queryKey: ["class-groups"] });
      onClose();
    },
    onError: error => setFailure(apiMessage(error)),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    add.mutate();
  };
  return (
    <Modal
      title="Inscribir estudiante"
      description={`Estudiantes activos de ${group.career_name}`}
      onClose={onClose}
    >
      <form className="groups-form" onSubmit={submit}>
        <label className="form-field">
          <span>Buscar</span>
          <input
            value={term}
            placeholder="Nombre o matrícula"
            onChange={event => setTerm(event.target.value)}
          />
        </label>
        <ul className="groups-pick" aria-label="Estudiantes encontrados">
          {students.data?.map(item => (
            <li key={item.student_id}>
              <label>
                <input
                  type="radio"
                  name="student"
                  checked={studentId === item.student_id}
                  onChange={() => setStudentId(item.student_id)}
                />
                {item.first_name} {item.last_name} · {item.enrollment_number}
                {item.financial_hold && <Chip tone="warning">Bloqueo financiero</Chip>}
              </label>
            </li>
          ))}
        </ul>
        {chosen?.financial_hold && (
          <p className="muted">
            {canOverride
              ? "Tiene un bloqueo financiero: escribe el motivo de la excepción para inscribirlo."
              : "Tiene un bloqueo financiero: solo finanzas puede autorizar una excepción."}
          </p>
        )}
        {chosen?.financial_hold && canOverride && (
          <label className="form-field">
            <span>Motivo de la excepción financiera</span>
            <input maxLength={250} value={override} onChange={e => setOverride(e.target.value)} />
          </label>
        )}
        {failure && (
          <p className="form-error" role="alert">
            {failure}
          </p>
        )}
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={!studentId || add.isPending}>
            {add.isPending ? "Inscribiendo…" : "Inscribir"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function MemberActionDialog({
  group,
  action,
  onClose,
}: {
  group: ClassGroupDetail;
  action: Action;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [reason, setReason] = useState("");
  const [target, setTarget] = useState("");
  const [failure, setFailure] = useState<string | null>(null);
  const transfer = action.kind === "transfer";
  const siblings = useQuery({
    queryKey: ["class-groups", group.school_year_id, "siblings", group.career_id],
    queryFn: () =>
      api
        .get<ClassGroup[]>("/class-groups/", {
          params: {
            school_year_id: group.school_year_id,
            career_id: group.career_id,
            limit: 100,
          },
        })
        .then(r => r.data.filter(item => item.class_group_id !== group.class_group_id)),
    enabled: transfer,
  });
  const save = useMutation({
    mutationFn: () =>
      api.post(
        `/class-groups/${group.class_group_id}/members/${action.member.member_id}/${action.kind}`,
        transfer ? { reason, target_group_id: Number(target) } : { reason },
      ),
    onSuccess: () => {
      toast.success(transfer ? "Estudiante trasladado" : "Estudiante retirado del grupo");
      client.invalidateQueries({ queryKey: groupKey(group.class_group_id) });
      client.invalidateQueries({ queryKey: ["class-groups"] });
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
      title={`${transfer ? "Trasladar" : "Retirar"} a ${action.member.student_name}`}
      description={
        transfer
          ? "Pasa a otro grupo del mismo grado y año; sus materias abiertas cambian de grupo."
          : "Se retiran sus materias de los períodos abiertos. Las notas cerradas se conservan."
      }
      onClose={onClose}
    >
      <form className="groups-form" onSubmit={submit}>
        {transfer && (
          <label className="form-field">
            <span>Grupo de destino</span>
            <select required value={target} onChange={event => setTarget(event.target.value)}>
              <option value="">Selecciona un grupo</option>
              {siblings.data?.map(item => (
                <option key={item.class_group_id} value={item.class_group_id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="form-field">
          <span>Motivo</span>
          <input
            required
            minLength={3}
            maxLength={250}
            value={reason}
            onChange={event => setReason(event.target.value)}
          />
        </label>
        {failure && (
          <p className="form-error" role="alert">
            {failure}
          </p>
        )}
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            type="submit"
            variant={transfer ? "primary" : "danger"}
            disabled={save.isPending || reason.trim().length < 3 || (transfer && !target)}
          >
            {transfer ? "Trasladar" : "Retirar"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
