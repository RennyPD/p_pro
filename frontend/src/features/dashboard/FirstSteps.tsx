import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import "./first-steps.css";

type Checklist = ApiSchema<"OnboardingChecklist">;

/** «Primeros pasos»: what a new institution still has to set up (Fase 4 B). */
export function FirstSteps() {
  const checklist = useQuery({
    queryKey: ["onboarding-checklist"],
    queryFn: () => api.get<Checklist>("/onboarding/checklist").then(r => r.data),
  });
  const data = checklist.data;
  if (!data || data.completed >= data.total) return null;
  return (
    <section className="panel first-steps" aria-labelledby="first-steps-title">
      <header>
        <h2 id="first-steps-title">Primeros pasos</h2>
        <span className="muted">
          {data.completed} de {data.total} completados
        </span>
      </header>
      <progress value={data.completed} max={data.total} aria-label="Progreso de la configuración" />
      <ol>
        {data.steps.map(step => (
          <li key={step.key} className={step.done ? "first-steps__done" : undefined}>
            {step.done ? <CheckCircle2 aria-hidden /> : <Circle aria-hidden />}
            <div>
              {step.done ? <strong>{step.label}</strong> : <Link to={step.to}>{step.label}</Link>}
              <p className="muted">{step.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
