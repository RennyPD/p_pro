import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Controller, useWatch, type Control, type FieldValues } from "react-hook-form";
import { api } from "../lib/api";
import type { ApiSchema } from "../lib/apiTypes";
import { useAuthStore } from "../store/auth";

type Availability = ApiSchema<"ClassroomAvailability">;
const UNASSIGNED = "Por asignar";

const days = (value: unknown) =>
  (Array.isArray(value) ? value.map(String) : String(value ?? "").split(","))
    .map(day => day.trim())
    .filter(Boolean);

/**
 * Room field of the section form: lists the registered classrooms and, once days
 * and times are set, whether each one is free for this section. Choosing a busy,
 * too small or retired room shows why and blocks saving.
 */
export function ClassroomPicker({
  name,
  label,
  control,
}: {
  name: string;
  label: string;
  control: Control<FieldValues>;
}) {
  const userId = useAuthStore(state => state.user?.user_id);
  const [dayList, start, end, capacity, period, modality, sectionId, status] = useWatch({
    control,
    name: [
      "days_of_week",
      "start_time",
      "end_time",
      "capacity",
      "period_name",
      "modality",
      "section_id",
      "status",
    ],
  });
  const selectedDays = days(dayList);
  const ready = selectedDays.length > 0 && Boolean(start) && Boolean(end) && start < end;
  const params = {
    days: selectedDays.join(","),
    start_time: String(start ?? "").slice(0, 5),
    end_time: String(end ?? "").slice(0, 5),
    capacity: Number(capacity) || 1,
    period_name: period || "",
    section_id: sectionId || undefined,
  };
  const availability = useQuery({
    queryKey: ["classroom-availability", userId, params],
    queryFn: () =>
      api
        .get<Availability[]>("/scheduling/classrooms/availability", { params })
        .then(response => response.data),
    enabled: ready && modality !== "virtual",
  });
  const rooms = availability.data ?? [];
  const find = (value: string) =>
    rooms.find(room => room.name.toLocaleLowerCase() === value.trim().toLocaleLowerCase());
  const publishing = status === "published" || status === "active";

  if (modality === "virtual")
    return (
      <div className="form-field">
        <span>{label}</span>
        <p className="room-hint">Sección virtual: no necesita aula.</p>
      </div>
    );

  return (
    <Controller
      name={name}
      control={control}
      rules={{
        validate: value => {
          const text = String(value ?? "").trim();
          if (!text || text === UNASSIGNED)
            return publishing ? "Asigna un aula disponible para publicar la sección" : true;
          if (!ready || availability.isFetching) return true;
          const room = find(text);
          if (!room) return `${text} no está registrada. Elige un aula de la lista`;
          return room.status === "available" || `${room.name}: ${room.detail}`;
        },
      }}
      render={({ field, fieldState }) => {
        const value = String(field.value ?? "").trim();
        const room = value && value !== UNASSIGNED ? find(value) : undefined;
        const legacy = value && value !== UNASSIGNED && ready && !availability.isFetching && !room;
        return (
          <label className="form-field">
            <span>{label}</span>
            <select
              aria-label={label}
              value={value && value !== UNASSIGNED ? value : ""}
              onChange={event => field.onChange(event.target.value || UNASSIGNED)}
              onBlur={field.onBlur}
              disabled={!ready || availability.isLoading}
            >
              <option value="">
                {publishing ? "Selecciona un aula" : "Por asignar (borrador)"}
              </option>
              {legacy && <option value={value}>{value} (no registrada)</option>}
              {rooms.map(item => (
                <option
                  key={item.classroom_id}
                  value={item.name}
                  disabled={item.status !== "available" && item.name !== value}
                >
                  {item.name} · {item.capacity} plazas
                  {item.status === "available" ? " · Disponible" : ` · ${item.detail}`}
                </option>
              ))}
            </select>
            {!ready ? (
              <small className="room-hint">Elige días y horario para ver las aulas libres.</small>
            ) : availability.isError ? (
              <small className="room-hint room-hint--warning">
                <AlertTriangle size={14} /> No pudimos comprobar la disponibilidad.
              </small>
            ) : fieldState.error?.message ? (
              <small className="room-hint room-hint--warning" role="alert">
                <AlertTriangle size={14} /> {fieldState.error.message}
              </small>
            ) : room && room.status !== "available" ? (
              <small className="room-hint room-hint--warning" role="alert">
                <AlertTriangle size={14} /> {room.name}: {room.detail}. No se podrá guardar.
              </small>
            ) : room ? (
              <small className="room-hint room-hint--ok">
                <CheckCircle2 size={14} /> Disponible en ese horario
              </small>
            ) : (
              <small className="room-hint">
                {(() => {
                  const free = rooms.filter(item => item.status === "available").length;
                  return free === 1
                    ? "1 aula libre en ese horario"
                    : `${free} aulas libres en ese horario`;
                })()}
              </small>
            )}
          </label>
        );
      }}
    />
  );
}
