import { useMutation } from "@tanstack/react-query";
import { DateInput } from "../../components/DateInput";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./assessments.css";
import { type Assessment } from "./assessmentsShared";

export function AssessmentEditor({ item, refresh }: { item: Assessment; refresh: () => void }) {
  const [name, setName] = useState(item.name);
  const [date, setDate] = useState(item.due_date ?? "");
  const update = useMutation({
    mutationFn: () =>
      api.patch("/assessments/" + item.assessment_id, { name, due_date: date || null }),
    onSuccess: () => {
      refresh();
      toast.success("Datos actualizados");
    },
    onError: error => toast.error(apiMessage(error)),
  });
  return (
    <form
      className="panel assessment-plan"
      onSubmit={event => {
        event.preventDefault();
        update.mutate();
      }}
    >
      <h3>Datos de {item.name}</h3>
      <label className="form-field">
        <span>Nombre</span>
        <input
          required
          minLength={2}
          maxLength={100}
          disabled={item.closed}
          value={name}
          onChange={event => setName(event.target.value)}
        />
      </label>
      <label className="form-field">
        <span>Fecha límite</span>
        <DateInput disabled={item.closed} value={date} onValueChange={event => setDate(event)} />
      </label>
      <Button disabled={item.closed || update.isPending}>Guardar datos</Button>
    </form>
  );
}
