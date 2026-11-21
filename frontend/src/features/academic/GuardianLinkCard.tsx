import { useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Unlink } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Badge, Button, Modal } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { confirmAction } from "../../lib/confirm";

export type GuardianLink = ApiSchema<"GuardianLinkOut">;
type Access = Pick<
  GuardianLink,
  | "can_view_academic"
  | "can_view_attendance"
  | "can_view_finance"
  | "can_view_tasks"
  | "financial_responsible"
>;

const AREAS: { key: keyof Access; label: string; help: string }[] = [
  {
    key: "can_view_academic",
    label: "Notas y desempeño",
    help: "Calificaciones, horario y alertas",
  },
  { key: "can_view_attendance", label: "Asistencia", help: "Detalle por día y asignatura" },
  { key: "can_view_tasks", label: "Tareas", help: "Entregas y calificaciones de tareas" },
  { key: "can_view_finance", label: "Finanzas", help: "Balance, vencimientos y movimientos" },
];

function accessOf(link: GuardianLink): Access {
  return {
    can_view_academic: link.can_view_academic ?? true,
    can_view_attendance: link.can_view_attendance ?? true,
    can_view_finance: link.can_view_finance ?? true,
    can_view_tasks: link.can_view_tasks ?? true,
    financial_responsible: link.financial_responsible ?? false,
  };
}

/** One guardian of the student; staff with students.manage edit what the guardian sees. */
export function GuardianLinkCard({
  link,
  studentId,
  canManage,
}: {
  link: GuardianLink;
  studentId: number;
  canManage: boolean;
}) {
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const access = accessOf(link);
  const hidden = AREAS.filter(area => !access[area.key]);

  async function refresh() {
    await client.invalidateQueries({ queryKey: ["student-guardians", studentId] });
  }

  async function unlink() {
    const question = `¿Desvincular a ${link.guardian_name}? Dejará de ver la información del estudiante.`;
    if (!(await confirmAction(question))) return;
    try {
      await api.delete(`/community/guardian-links/${link.student_guardian_id}`);
      toast.success("Tutor desvinculado");
      await refresh();
    } catch (error) {
      toast.error(apiMessage(error));
    }
  }

  return (
    <article className="dossier-guardian">
      <strong>{link.guardian_name}</strong>
      <span>{link.relationship}</span>
      <a href={`mailto:${link.guardian_email}`}>{link.guardian_email}</a>
      <div>
        {link.primary_contact && <Badge tone="info">Contacto principal</Badge>}
        {link.emergency_contact && <Badge tone="warning">Emergencia</Badge>}
        {link.authorized_pickup && <Badge tone="success">Retiro autorizado</Badge>}
        {access.financial_responsible && <Badge tone="info">Responsable de pago</Badge>}
        {hidden.length === 0 ? (
          <Badge tone="success">Ve toda la información</Badge>
        ) : (
          <Badge tone="warning">
            Sin acceso a: {hidden.map(area => area.label.toLowerCase()).join(", ")}
          </Badge>
        )}
      </div>
      {canManage && (
        <div className="form-actions">
          <Button variant="secondary" onClick={() => setEditing(true)}>
            <ShieldCheck size={16} /> Accesos
          </Button>
          <Button variant="ghost" onClick={() => void unlink()}>
            <Unlink size={16} /> Desvincular
          </Button>
        </div>
      )}
      {editing && (
        <AccessEditor
          link={link}
          initial={access}
          onClose={() => setEditing(false)}
          onSaved={refresh}
        />
      )}
    </article>
  );
}

function AccessEditor({
  link,
  initial,
  onClose,
  onSaved,
}: {
  link: GuardianLink;
  initial: Access;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<Access>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const changed = (Object.keys(draft) as (keyof Access)[]).some(key => draft[key] !== initial[key]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.patch(`/community/guardian-links/${link.student_guardian_id}`, draft);
      toast.success("Accesos del tutor guardados");
      await onSaved();
      onClose();
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`Accesos de ${link.guardian_name}`}
      description="Por defecto el tutor ve toda la información del estudiante. Desmarca un área solo cuando haya un motivo, por ejemplo una restricción de custodia."
      onClose={onClose}
    >
      <form className="resource-form" onSubmit={save}>
        <fieldset className="guardian-access">
          <legend>Qué puede ver</legend>
          {AREAS.map(area => (
            <label key={area.key}>
              <input
                type="checkbox"
                disabled={busy}
                checked={draft[area.key]}
                onChange={event => setDraft({ ...draft, [area.key]: event.target.checked })}
              />
              <span>
                <b>{area.label}</b>
                <small>{area.help}</small>
              </span>
            </label>
          ))}
        </fieldset>
        <label className="guardian-access__single">
          <input
            type="checkbox"
            disabled={busy}
            checked={draft.financial_responsible}
            onChange={event => setDraft({ ...draft, financial_responsible: event.target.checked })}
          />
          <span>
            <b>Responsable de pago</b>
            <small>Persona que paga las obligaciones del estudiante</small>
          </span>
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <Button type="button" variant="secondary" disabled={busy} onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={busy || !changed}>{busy ? "Guardando…" : "Guardar accesos"}</Button>
        </div>
      </form>
    </Modal>
  );
}
