import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { fetchAllOptions } from "../../lib/options";

type Draft = {
  first_name: string;
  last_name: string;
  email: string;
  telephone: string;
  career_id: string;
  checklist: string;
  notes: string;
};

export function AdmissionCreateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [draft, setDraft] = useState<Draft>({
    first_name: "",
    last_name: "",
    email: "",
    telephone: "",
    career_id: "",
    checklist: "",
    notes: "",
  });
  const programs = useQuery<Array<{ career_id: number; name: string; status: string }>>({
    queryKey: ["admission-programs"],
    queryFn: ({ signal }) =>
      fetchAllOptions<{ career_id: number; name: string; status: string }>(
        "/careers/",
        "career_id",
        { status: "active" },
        signal,
      ),
  });
  const save = useMutation({
    mutationFn: () =>
      api.post("/operations/admissions", {
        ...draft,
        first_name: draft.first_name.trim(),
        last_name: draft.last_name.trim(),
        career_id: Number(draft.career_id),
      }),
    onSuccess: onCreated,
  });
  const change = (key: keyof Draft, value: string) => setDraft(s => ({ ...s, [key]: value }));
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!save.isPending) save.mutate();
  }
  return (
    <Modal
      title="Nueva solicitud de admisión"
      description="Registrar una solicitud no crea todavía una cuenta ni una matrícula."
      onClose={() => {
        if (!save.isPending) onClose();
      }}
    >
      <form className="resource-form" onSubmit={submit}>
        <label className="form-field">
          <span>Nombres</span>
          <input
            required
            maxLength={100}
            value={draft.first_name}
            onChange={e => change("first_name", e.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Apellidos</span>
          <input
            required
            maxLength={100}
            value={draft.last_name}
            onChange={e => change("last_name", e.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Correo del aspirante</span>
          <input
            type="email"
            required
            value={draft.email}
            onChange={e => change("email", e.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Teléfono del aspirante</span>
          <input
            type="tel"
            required
            maxLength={30}
            value={draft.telephone}
            onChange={e => change("telephone", e.target.value)}
          />
        </label>
        <label className="form-field settings-wide">
          <span>Programa solicitado</span>
          <select
            required
            disabled={programs.isLoading || Boolean(programs.error)}
            value={draft.career_id}
            onChange={e => change("career_id", e.target.value)}
          >
            <option value="">Selecciona un programa</option>
            {programs.data?.map(p => (
              <option key={p.career_id} value={p.career_id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {programs.isLoading && <Spinner />}
        {programs.error && <p role="alert">{apiMessage(programs.error)}</p>}
        <label className="form-field settings-wide">
          <span>Documentación recibida</span>
          <textarea
            maxLength={5000}
            value={draft.checklist}
            onChange={e => change("checklist", e.target.value)}
          />
        </label>
        <label className="form-field settings-wide">
          <span>Observaciones de admisión</span>
          <textarea
            maxLength={5000}
            value={draft.notes}
            onChange={e => change("notes", e.target.value)}
          />
        </label>
        {save.error && (
          <p className="form-error" role="alert">
            {apiMessage(save.error)}
          </p>
        )}
        <div className="form-actions">
          <Button type="button" variant="secondary" disabled={save.isPending} onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={
              save.isPending ||
              !draft.first_name.trim() ||
              !draft.last_name.trim() ||
              !draft.career_id ||
              Boolean(programs.error)
            }
          >
            {save.isPending ? "Registrando…" : "Registrar solicitud"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
