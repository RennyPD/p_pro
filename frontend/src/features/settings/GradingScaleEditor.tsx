import { useMutation } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button, Modal } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";

type BandDraft = {
  label: string;
  description: string;
  min_value: string;
  max_value: string;
  stored_value: string;
  points: string;
};
export type ScaleDraft = {
  name: string;
  kind: string;
  passing_value: string;
  decimals: string;
  completivo_average_weight: string;
  extraordinario_average_weight: string;
  bands: BandDraft[];
};

const emptyBand: BandDraft = {
  label: "",
  description: "",
  min_value: "",
  max_value: "",
  stored_value: "",
  points: "",
};

/** Label a 0–100 value would get with the bands being edited (preview). */
function previewLabel(draft: ScaleDraft, value: number) {
  if (draft.kind === "numeric" || draft.bands.length === 0)
    return value.toFixed(Number(draft.decimals) || 0);
  const sorted = [...draft.bands].sort((a, b) => Number(a.min_value) - Number(b.min_value));
  let chosen = "—";
  for (const band of sorted) if (value >= Number(band.min_value)) chosen = band.label || "—";
  return chosen;
}

export function GradingScaleEditor({
  scaleId,
  initial,
  onClose,
  onSaved,
}: {
  scaleId: number | null;
  initial: ScaleDraft;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [sample, setSample] = useState("85");
  const [failure, setFailure] = useState<string | null>(null);
  const set = (key: keyof ScaleDraft, value: string) =>
    setDraft(current => ({ ...current, [key]: value }));
  const setBand = (index: number, key: keyof BandDraft, value: string) =>
    setDraft(current => ({
      ...current,
      bands: current.bands.map((band, i) => (i === index ? { ...band, [key]: value } : band)),
    }));
  const save = useMutation({
    mutationFn: () => {
      const payload = {
        name: draft.name,
        kind: draft.kind,
        passing_value: Number(draft.passing_value),
        decimals: Number(draft.decimals),
        completivo_average_weight: Number(draft.completivo_average_weight),
        extraordinario_average_weight: Number(draft.extraordinario_average_weight),
        bands: draft.bands.map(band => ({
          label: band.label,
          description: band.description || null,
          min_value: Number(band.min_value),
          max_value: Number(band.max_value),
          stored_value: Number(band.stored_value),
          points: band.points === "" ? null : Number(band.points),
        })),
      };
      return scaleId
        ? api.put(`/grading-scales/${scaleId}`, payload)
        : api.post("/grading-scales/", payload);
    },
    onSuccess: () => {
      toast.success(scaleId ? "Escala actualizada" : "Escala creada");
      onSaved();
      onClose();
    },
    onError: error => setFailure(apiMessage(error)),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const number = (key: keyof ScaleDraft, label: string, max = 100) => (
    <label className="form-field">
      <span>{label}</span>
      <input
        required
        type="number"
        min={0}
        max={max}
        step="0.01"
        value={draft[key] as string}
        onChange={event => set(key, event.target.value)}
      />
    </label>
  );
  const sampleValue = Math.min(100, Math.max(0, Number(sample) || 0));

  return (
    <Modal
      title={scaleId ? "Editar escala" : "Nueva escala"}
      description="Los cambios aplican a las selecciones nuevas; las existentes conservan su nota mínima."
      onClose={onClose}
    >
      <form className="scale-form" onSubmit={submit}>
        <div className="scale-form__row">
          <label className="form-field">
            <span>Nombre</span>
            <input
              required
              minLength={2}
              maxLength={80}
              value={draft.name}
              onChange={event => set("name", event.target.value)}
            />
          </label>
          <label className="form-field">
            <span>Tipo</span>
            <select value={draft.kind} onChange={event => set("kind", event.target.value)}>
              <option value="numeric">Numérica</option>
              <option value="letter">Letras</option>
              <option value="conceptual">Conceptual</option>
            </select>
          </label>
        </div>
        <div className="scale-form__row">
          {number("passing_value", "Nota mínima (0–100)")}
          {number("decimals", "Decimales", 2)}
        </div>
        <div className="scale-form__row">
          {number("completivo_average_weight", "Completivo: % del promedio")}
          {number("extraordinario_average_weight", "Extraordinario: % del promedio")}
        </div>
        <fieldset className="scale-form__bands">
          <legend>Rangos {draft.kind === "numeric" && "(opcionales)"}</legend>
          {draft.bands.length > 0 && (
            <div className="scale-band-row scale-band-row--head" aria-hidden="true">
              <span>Etiqueta</span>
              <span>Desde</span>
              <span>Hasta</span>
              <span>Se guarda</span>
              <span>Puntos</span>
              <span />
            </div>
          )}
          {draft.bands.map((band, index) => (
            <div key={index} className="scale-band-row">
              <input
                aria-label={`Etiqueta del rango ${index + 1}`}
                required
                maxLength={40}
                value={band.label}
                onChange={event => setBand(index, "label", event.target.value)}
              />
              {(["min_value", "max_value", "stored_value", "points"] as const).map(key => (
                <input
                  key={key}
                  aria-label={`${
                    {
                      min_value: "Desde",
                      max_value: "Hasta",
                      stored_value: "Valor guardado",
                      points: "Puntos",
                    }[key]
                  } del rango ${index + 1}`}
                  type="number"
                  min={0}
                  max={key === "points" ? 10 : 100}
                  step="0.01"
                  required={key !== "points"}
                  value={band[key]}
                  onChange={event => setBand(index, key, event.target.value)}
                />
              ))}
              <Button
                type="button"
                variant="ghost"
                aria-label={`Quitar el rango ${index + 1}`}
                onClick={() =>
                  setDraft(current => ({
                    ...current,
                    bands: current.bands.filter((_, i) => i !== index),
                  }))
                }
              >
                <Trash2 size={16} />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              setDraft(current => ({ ...current, bands: [...current.bands, emptyBand] }))
            }
          >
            <Plus size={16} /> Añadir rango
          </Button>
          <p className="muted">
            Los rangos van de 0 a 100 sin huecos; cada uno termina donde empieza el siguiente.
          </p>
        </fieldset>
        <div className="scale-preview">
          <label className="form-field">
            <span>Vista previa: nota de 0 a 100</span>
            <input
              type="number"
              min={0}
              max={100}
              value={sample}
              onChange={event => setSample(event.target.value)}
            />
          </label>
          <output aria-live="polite">
            Se muestra <b>{previewLabel(draft, sampleValue)}</b> y{" "}
            {sampleValue >= Number(draft.passing_value) ? "aprueba" : "no aprueba"}
          </output>
        </div>
        {failure && (
          <p className="form-error" role="alert">
            {failure}
          </p>
        )}
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Guardando…" : "Guardar escala"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
