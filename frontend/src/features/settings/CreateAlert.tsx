import { confirmAction } from "../../lib/confirm";
import { useId, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { LookupSelect } from "../../components/LookupSelect";
import { useDraftGuard } from "../../lib/useDraftGuard";
import { Button, Modal } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./institutional-control.css";
import "./alert-history.css";
import { alertLabels, severityNames, studentLookup } from "./institutionalControlShared";

export function CreateAlert({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const lookupLabel = useId();
  const [student, setStudent] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useDraftGuard(dirty, busy);
  async function close() {
    if (!busy && (!dirty || (await confirmAction("¿Descartar los datos del caso?")))) onClose();
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!student) return;
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api.post("/operations/alerts", {
        ...data,
        student_id: student,
        reason: String(data.reason).trim(),
      });
      toast.success("Caso registrado");
      onCreated();
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Nuevo caso de seguimiento" onClose={close}>
      <form className="resource-form" onSubmit={create} onChange={() => setDirty(true)}>
        <div className="form-field">
          <span id={lookupLabel}>Estudiante</span>
          <LookupSelect
            config={studentLookup}
            labelId={lookupLabel}
            required
            value={student}
            onChange={value => {
              setStudent(Number(value));
              setDirty(true);
            }}
          />
        </div>
        <label className="form-field">
          <span>Categoría</span>
          <select name="category">
            {Object.entries(alertLabels).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Prioridad</span>
          <select name="severity" defaultValue="medium">
            {Object.entries(severityNames).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Motivo</span>
          <textarea name="reason" required minLength={2} rows={3} />
        </label>
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <div className="form-actions">
          <Button type="button" variant="secondary" disabled={busy} onClick={close}>
            Cancelar
          </Button>
          <Button disabled={!student || busy}>{busy ? "Registrando…" : "Registrar caso"}</Button>
        </div>
      </form>
    </Modal>
  );
}
