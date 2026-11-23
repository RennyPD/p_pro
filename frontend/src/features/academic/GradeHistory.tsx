import { confirmAction } from "../../lib/confirm";
import { useMutation, useQuery } from "@tanstack/react-query";
import { formatDateTime } from "../../lib/format";
import { toast } from "sonner";
import { Button, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import "./assessments.css";
import { type Grade, type Change, labels } from "./assessmentsShared";

export function GradeHistory({
  grade,
  student,
  closed,
  reason,
  onClose,
  refresh,
}: {
  grade: Grade;
  student: string;
  closed: boolean;
  reason: string;
  onClose: () => void;
  refresh: () => void;
}) {
  const user = useAuthStore(state => state.user);
  const history = useQuery<Change[]>({
    queryKey: ["grade-history", grade.grade_id, user?.user_id],
    queryFn: () => api.get("/grades/" + grade.grade_id + "/history").then(r => r.data),
  });
  const annul = useMutation({
    mutationFn: () => api.delete("/grades/" + grade.grade_id, { data: { reason } }),
    onSuccess: () => {
      refresh();
      onClose();
      toast.success("Nota anulada, historial conservado");
    },
    onError: error => toast.error(apiMessage(error)),
  });
  return (
    <Modal title={"Historial de " + student} onClose={onClose}>
      <p>
        Nota actual: {grade.grade_value} · {labels[grade.status]}
      </p>
      {history.isLoading ? (
        <Spinner />
      ) : history.error ? (
        <p role="alert">{apiMessage(history.error)}</p>
      ) : (
        history.data?.map(change => (
          <article className="assessment-template" key={change.grade_change_id}>
            <strong>
              {labels[change.action] ?? change.action} · {change.previous_value ?? "—"} →{" "}
              {change.new_value}
            </strong>
            <small>
              {change.changed_by_name} · {formatDateTime(change.changed_at)}
            </small>
            <p>{change.reason}</p>
            <small>
              {labels[change.previous_status ?? ""] ?? "Sin nota"} →{" "}
              {labels[change.new_status ?? ""] ?? ""}
            </small>
          </article>
        ))
      )}
      <p className="muted">
        Para anular, escribe el motivo en el libro de notas. La nota no se borra físicamente.
      </p>
      <Button
        variant="danger"
        disabled={
          closed || grade.status === "voided" || reason.trim().length < 2 || annul.isPending
        }
        onClick={async () =>
          (await confirmAction("¿Anular esta nota y conservar su historial?")) && annul.mutate()
        }
      >
        Anular nota
      </Button>
    </Modal>
  );
}
