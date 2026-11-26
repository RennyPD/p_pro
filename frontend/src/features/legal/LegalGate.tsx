import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Modal } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { LegalText } from "./LegalText";
import "./legal.css";

type Summary = { kind: string; title: string; version: string; slug: string };

/**
 * The institution's administrator accepts the terms and the data processing
 * agreement (Fase 5 G3), again when their version changes. Others are not asked.
 */
export function LegalGate() {
  const client = useQueryClient();
  const [checked, setChecked] = useState(false);
  const pending = useQuery({
    queryKey: ["legal", "pending"],
    queryFn: () => api.get<{ documents: Summary[] }>("/legal/pending").then(r => r.data),
    staleTime: 10 * 60_000,
  });
  const documents = pending.data?.documents ?? [];
  const texts = useQuery({
    queryKey: ["legal", "texts", documents.map(d => `${d.slug}@${d.version}`).join(",")],
    queryFn: () =>
      Promise.all(
        documents.map(d =>
          api.get<Summary & { text: string }>(`/public/legal/${d.slug}`).then(r => r.data),
        ),
      ),
    enabled: documents.length > 0,
  });
  const accept = useMutation({
    mutationFn: () => api.post("/legal/accept", { kinds: documents.map(d => d.kind) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["legal", "pending"] }),
  });
  if (!documents.length) return null;
  return (
    <Modal
      title="Documentos de Nexo para tu institución"
      description="Como administración de la institución, revisa y acepta estos documentos para continuar."
      onClose={() => {}}
    >
      <div className="legal-gate">
        {texts.data?.map(document => (
          <details key={document.kind} className="legal-gate__document">
            <summary>
              {document.title} · versión {document.version}
            </summary>
            <LegalText text={document.text} />
          </details>
        ))}
        <label className="legal-gate__check">
          <input
            type="checkbox"
            checked={checked}
            onChange={event => setChecked(event.target.checked)}
          />
          Acepto {documents.map(d => d.title.toLowerCase()).join(" y ")} en nombre de la
          institución.
        </label>
        {accept.error && (
          <p className="form-error" role="alert">
            {apiMessage(accept.error)}
          </p>
        )}
        <div className="form-actions">
          <Button disabled={!checked || accept.isPending} onClick={() => accept.mutate()}>
            Aceptar y continuar
          </Button>
        </div>
      </div>
    </Modal>
  );
}
