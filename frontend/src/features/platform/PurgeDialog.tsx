import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Modal } from "../../components/ui";
import { apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { platformApi } from "../../lib/platformApi";

type Institution = ApiSchema<"InstitutionOut">;

/** Irreversible deletion of an institution's data, 90 days after it stopped (Fase 5 G4). */
export function PurgeDialog({
  institution,
  onClose,
}: {
  institution: Institution;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [code, setCode] = useState("");
  const [reason, setReason] = useState("");
  const purge = useMutation({
    mutationFn: () =>
      platformApi.post(`/platform/institutions/${institution.institution_id}/purge`, {
        code,
        reason,
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["platform"] });
      onClose();
    },
  });
  return (
    <Modal
      title={`Eliminar los datos de ${institution.name}`}
      description="Se borran para siempre todos sus registros y archivos. No se puede deshacer."
      onClose={onClose}
    >
      <form
        className="platform-form"
        onSubmit={event => {
          event.preventDefault();
          purge.mutate();
        }}
      >
        <label className="form-field">
          <span>Escribe el código «{institution.code}» para confirmar</span>
          <input value={code} onChange={event => setCode(event.target.value)} autoComplete="off" />
        </label>
        <label className="form-field">
          <span>Motivo</span>
          <textarea
            value={reason}
            onChange={event => setReason(event.target.value)}
            minLength={5}
          />
        </label>
        {purge.error && (
          <div className="form-error" role="alert">
            {apiMessage(purge.error)}
          </div>
        )}
        <div className="form-actions">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="danger"
            disabled={
              purge.isPending || code.trim() !== institution.code || reason.trim().length < 5
            }
          >
            Eliminar definitivamente
          </Button>
        </div>
      </form>
    </Modal>
  );
}
