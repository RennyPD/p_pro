import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Ruler, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button, EmptyState, Spinner } from "../../components/ui";
import { Chip } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import { confirmAction } from "../../lib/confirm";
import { GradingScaleEditor, type ScaleDraft } from "./GradingScaleEditor";
import "./grading-scales.css";

type Scale = ApiSchema<"GradingScaleOut">;
type Preset = ApiSchema<"GradingScalePreset">;

const kindLabels: Record<string, string> = {
  numeric: "Numérica",
  letter: "Letras",
  conceptual: "Conceptual",
};

const toDraft = (scale: Scale | Preset["scale"]): ScaleDraft => ({
  name: scale.name,
  kind: scale.kind,
  passing_value: String(scale.passing_value),
  decimals: String(scale.decimals ?? 0),
  completivo_average_weight: String(scale.completivo_average_weight ?? 50),
  extraordinario_average_weight: String(scale.extraordinario_average_weight ?? 30),
  bands: (scale.bands ?? []).map(band => ({
    label: band.label,
    description: band.description ?? "",
    min_value: String(band.min_value),
    max_value: String(band.max_value),
    stored_value: String(band.stored_value),
    points: band.points === null || band.points === undefined ? "" : String(band.points),
  })),
});

/** Grading scales per program (Fase 3 D): grades stay 0–100, scales translate them. */
export function GradingScalesPage() {
  const client = useQueryClient();
  const [editing, setEditing] = useState<{ id: number | null; draft: ScaleDraft } | null>(null);
  const scales = useQuery({
    queryKey: ["grading-scales"],
    queryFn: () => api.get<Scale[]>("/grading-scales/").then(r => r.data),
  });
  const presets = useQuery({
    queryKey: ["grading-scales", "presets"],
    queryFn: () => api.get<Preset[]>("/grading-scales/presets").then(r => r.data),
  });
  const refresh = () => {
    client.invalidateQueries({ queryKey: ["grading-scales"] });
    client.invalidateQueries({ queryKey: ["lookup"] });
  };
  const makeDefault = useMutation({
    mutationFn: (scale: Scale) => api.post(`/grading-scales/${scale.grading_scale_id}/default`),
    onSuccess: (_, scale) => {
      toast.success(`${scale.name} es ahora la escala predeterminada`);
      refresh();
    },
    onError: error => toast.error(apiMessage(error)),
  });
  const remove = useMutation({
    mutationFn: (scale: Scale) => api.delete(`/grading-scales/${scale.grading_scale_id}`),
    onSuccess: () => {
      toast.success("Escala eliminada");
      refresh();
    },
    onError: error => toast.error(apiMessage(error)),
  });

  return (
    <div className="page scales-page">
      <header className="page-header">
        <div>
          <span className="kicker">Configuración · Reglas académicas</span>
          <h1>Escalas de calificación</h1>
          <p className="muted">
            Las notas se guardan de 0 a 100; cada programa las muestra con su escala y aprueba con
            su nota mínima.
          </p>
        </div>
        <div className="scales-new">
          {presets.data?.map(preset => (
            <Button
              key={preset.key}
              variant="secondary"
              onClick={() => setEditing({ id: null, draft: toDraft(preset.scale) })}
            >
              <Plus size={16} /> {kindLabels[preset.scale.kind]}
            </Button>
          ))}
        </div>
      </header>
      {scales.isPending && <Spinner />}
      {scales.data?.length === 0 && (
        <EmptyState
          icon={<Ruler />}
          title="Sin escalas configuradas"
          description="Todos los programas usan la nota aprobatoria de la institución. Crea una escala desde una plantilla."
        />
      )}
      <ul className="scales-list">
        {scales.data?.map(scale => (
          <li key={scale.grading_scale_id} className="panel scale-card">
            <div className="scale-card__head">
              <div>
                <strong>{scale.name}</strong>
                <small>
                  Aprueba con {scale.passing_value} · {scale.program_count}{" "}
                  {scale.program_count === 1 ? "programa" : "programas"}
                </small>
              </div>
              <div className="scale-card__chips">
                <Chip>{kindLabels[scale.kind] ?? scale.kind}</Chip>
                {scale.is_default && <Chip tone="success">Predeterminada</Chip>}
              </div>
            </div>
            {scale.bands.length > 0 && (
              <ol className="scale-bands" aria-label={`Rangos de ${scale.name}`}>
                {scale.bands.map(band => (
                  <li
                    key={band.label}
                    className={band.min_value >= scale.passing_value ? "is-passing" : undefined}
                  >
                    <b>{band.label}</b>
                    <small>
                      {band.min_value}–{band.max_value}
                      {band.points !== null && band.points !== undefined
                        ? ` · ${band.points} pts`
                        : ""}
                    </small>
                  </li>
                ))}
              </ol>
            )}
            <small className="muted">
              Completivo: {scale.completivo_average_weight} % promedio +{" "}
              {100 - scale.completivo_average_weight} % examen · Extraordinario:{" "}
              {scale.extraordinario_average_weight} % promedio +{" "}
              {100 - scale.extraordinario_average_weight} % examen
            </small>
            <div className="scale-card__actions">
              <Button
                variant="secondary"
                onClick={() => setEditing({ id: scale.grading_scale_id, draft: toDraft(scale) })}
              >
                Editar
              </Button>
              {!scale.is_default && (
                <Button
                  variant="ghost"
                  disabled={makeDefault.isPending}
                  onClick={() => makeDefault.mutate(scale)}
                >
                  <Star size={16} /> Hacer predeterminada
                </Button>
              )}
              {!scale.is_default && scale.program_count === 0 && (
                <Button
                  variant="ghost"
                  aria-label={`Eliminar ${scale.name}`}
                  onClick={async () => {
                    if (await confirmAction(`¿Eliminar la escala ${scale.name}?`))
                      remove.mutate(scale);
                  }}
                >
                  <Trash2 size={16} />
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      {editing && (
        <GradingScaleEditor
          scaleId={editing.id}
          initial={editing.draft}
          onClose={() => setEditing(null)}
          onSaved={refresh}
        />
      )}
    </div>
  );
}
