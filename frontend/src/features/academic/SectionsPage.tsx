import { confirmAction } from "../../lib/confirm";
import { freeRoomsLabel, useClassroomAvailability } from "../../lib/classroomAvailability";
import { formatTime } from "../../lib/format";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  CalendarDays,
  CheckCircle2,
  Clock3,
  DoorOpen,
  MapPin,
  Pencil,
  Plus,
  Send,
  Trash2,
  Users,
} from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { DocumentDownload } from "../../components/DocumentDownload";
import { Badge, Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { resources } from "../../config/resources";
import { api, apiMessage } from "../../lib/api";
import { weekDays } from "../../lib/schedule";
import { useDraftGuard } from "../../lib/useDraftGuard";
import { useAuthStore } from "../../store/auth";
import type { EntityRecord, ResourceConfig } from "../../types";
import { ResourcePage } from "../resources/ResourcePage";

const modLabels = { in_person: "Presencial", hybrid: "Híbrida", virtual: "Virtual" };
type Room = {
  classroom_id: number;
  name: string;
  capacity: number;
  location: string;
  active: boolean;
};
type Meeting = {
  meeting_id: number;
  day_of_week: string;
  start_time: string;
  end_time: string;
  classroom_id: number | null;
  classroom_name: string | null;
  modality: keyof typeof modLabels;
  virtual_url: string;
};
const sectionConfig: ResourceConfig = {
  ...resources.sections,
  description: "Prepara la oferta, revisa el horario y publica la sección cuando esté lista.",
  defaultValues: { status: "draft", capacity: 30, minimum_capacity: 1, modality: "in_person" },
  columns: [
    ...resources.sections.columns,
    { key: "period_name", label: "Período", render: name => name || "Sin asignar" },
    {
      key: "status",
      label: "Estado",
      render: value =>
        ({
          draft: "Borrador",
          published: "Publicada",
          active: "Activa",
          closed: "Cerrada",
          cancelled: "Cancelada",
        })[String(value)] || String(value),
    },
  ],
  fields: [
    ...resources.sections.fields,
    {
      name: "period_name",
      type: "lookup",
      label: "Período académico",
      required: true,
      lookup: {
        endpoint: "/periods/",
        valueKey: "name",
        labelKeys: ["name"],
        secondaryKey: "academic_year",
        placeholder: "Buscar período",
      },
    },
    { name: "minimum_capacity", type: "number", label: "Cupo mínimo", required: true },
    { name: "status", type: "hidden", label: "Estado" },
  ],
};

export function SectionsPage() {
  const admin = useAuthStore(state => state.user?.role_name === "admin");
  const client = useQueryClient();
  const [meetings, setMeetings] = useState<EntityRecord | null>(null);
  const [rooms, setRooms] = useState(false);
  const [publication, setPublication] = useState<EntityRecord | null>(null);
  const [publishError, setPublishError] = useState("");
  const [publishing, setPublishing] = useState(false);

  async function publish() {
    if (!publication) return;
    setPublishing(true);
    setPublishError("");
    try {
      await api.patch(`/sections/${publication.section_id}`, { status: "published" });
      void client.invalidateQueries({ queryKey: ["sections"] });
      void client.invalidateQueries({ queryKey: ["course-catalog"] });
      toast.success(`Sección ${publication.code} publicada`);
      setPublication(null);
    } catch (error) {
      setPublishError(apiMessage(error));
    } finally {
      setPublishing(false);
    }
  }

  return (
    <>
      <ResourcePage
        config={sectionConfig}
        toolbarContent={
          admin && (
            <Button variant="secondary" onClick={() => setRooms(true)}>
              <DoorOpen size={16} /> Aulas
            </Button>
          )
        }
        rowActions={row => (
          <>
            <button
              type="button"
              aria-label={`Ver bloques de ${row.code}`}
              title="Bloques de horario"
              onClick={() => setMeetings(row)}
            >
              <CalendarDays size={17} />
            </button>
            {admin && row.status === "draft" && (
              <button
                type="button"
                aria-label={`Publicar ${row.code}`}
                onClick={() => {
                  setPublishError("");
                  setPublication(row);
                }}
                title="Publicar sección"
              >
                <Send size={16} />
              </button>
            )}
          </>
        )}
      />
      {meetings && <MeetingDialog section={meetings} onClose={() => setMeetings(null)} />}
      {rooms && <RoomDialog onClose={() => setRooms(false)} />}
      {publication && (
        <Modal
          title={`Publicar ${publication.code}`}
          onClose={() => {
            if (!publishing) setPublication(null);
          }}
        >
          <p>
            {publication.subject_name} · {publication.teacher_name} ·{" "}
            {publication.period_name || "Sin período asignado"}
          </p>
          <p>
            Cupo mínimo {publication.minimum_capacity} · Capacidad {publication.capacity}. Se
            comprobarán el período, las aulas y los choques de horario.
          </p>
          {publishError && (
            <p role="alert" className="form-error">
              {publishError}
            </p>
          )}
          <div className="form-actions">
            <Button variant="secondary" disabled={publishing} onClick={() => setPublication(null)}>
              Cancelar
            </Button>
            <Button disabled={publishing} onClick={() => void publish()}>
              {publishing ? "Publicando…" : "Confirmar publicación"}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function MeetingDialog({ section, onClose }: { section: EntityRecord; onClose: () => void }) {
  const client = useQueryClient();
  const roomLabel = useId();
  const [editing, setEditing] = useState<Meeting | "new" | null>(null);
  const [room, setRoom] = useState<number | null>(null);
  const [slot, setSlot] = useState({ day: "", start: "", end: "", modality: "in_person" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  useDraftGuard(dirty, busy);
  const editable = !["closed", "cancelled"].includes(String(section.status));
  const prefix = "/scheduling/meetings";
  const key = ["section-meetings", section.section_id];
  const blocks = useQuery({
    queryKey: key,
    queryFn: () =>
      api
        .get<Meeting[]>(`/scheduling/sections/${section.section_id}/meetings`)
        .then(response => response.data),
  });
  const existing = editing === "new" ? null : editing;
  function start(value: Meeting | "new") {
    setEditing(value);
    setRoom(value === "new" ? null : value.classroom_id);
    setSlot(
      value === "new"
        ? { day: weekDays[0], start: "", end: "", modality: "in_person" }
        : {
            day: value.day_of_week,
            start: value.start_time.slice(0, 5),
            end: value.end_time.slice(0, 5),
            modality: value.modality,
          },
    );
    setDirty(false);
    setError("");
  }

  async function close() {
    if (busy || (dirty && !(await confirmAction("¿Descartar cambios del bloque?")))) return;
    if (editing) {
      setEditing(null);
      setDirty(false);
      setError("");
    } else onClose();
  }

  async function change(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      setDirty(false);
      setEditing(null);
      await client.invalidateQueries({ queryKey: key });
      for (const queryKey of [
        "my-schedule",
        "course-catalog",
        "teacher-workload",
        "guardian-overview",
      ]) {
        void client.invalidateQueries({ queryKey: [queryKey] });
      }
    } catch (failure) {
      setError(`Sección ${section.code}. ${apiMessage(failure)}`);
    } finally {
      setBusy(false);
    }
  }

  const availability = useClassroomAvailability({
    days: slot.day ? [slot.day] : [],
    start: slot.start,
    end: slot.end,
    capacity: Number(section.capacity) || 1,
    period: String(section.period_name ?? ""),
    sectionId: Number(section.section_id),
    enabled: Boolean(editing) && slot.modality !== "virtual",
  });
  const chosen = availability.rooms.find(item => item.classroom_id === room);
  const roomProblem =
    slot.modality !== "virtual" && chosen && chosen.status !== "available"
      ? `${chosen.name}: ${chosen.detail}`
      : "";

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (roomProblem) return;
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const payload = { ...values, section_id: section.section_id, classroom_id: room };
    void change(() =>
      existing ? api.put(`${prefix}/${existing.meeting_id}`, payload) : api.post(prefix, payload),
    );
  }

  return (
    <Modal title={`Horario de ${section.code}`} onClose={close}>
      {blocks.isLoading ? (
        <Spinner label="Cargando bloques" />
      ) : blocks.error ? (
        <p role="alert">{apiMessage(blocks.error)}</p>
      ) : (
        !editing && (
          <>
            <div className="room-toolbar">
              <DocumentDownload
                path={`/documents/sections/${section.section_id}/roster.pdf`}
                filename={`lista-${section.code}.pdf`}
                label="Lista de estudiantes (PDF)"
              />
              {editable && (
                <Button disabled={busy} onClick={() => start("new")}>
                  <Plus size={16} /> Agregar bloque
                </Button>
              )}
            </div>
            {!blocks.data?.length ? (
              <p className="schedule-fallback">
                Aún no hay bloques. Se usa el horario general de la sección:{" "}
                <b>
                  {Array.isArray(section.days_of_week)
                    ? section.days_of_week.join(", ")
                    : section.days_of_week}{" "}
                  · {formatTime(String(section.start_time))}–{formatTime(String(section.end_time))}
                </b>
                . Al agregar bloques, reemplazarán ese horario.
              </p>
            ) : (
              <ul className="room-list">
                {blocks.data.map(block => (
                  <li key={block.meeting_id}>
                    <span className="room-list__icon room-list__icon--day" aria-hidden="true">
                      {block.day_of_week.slice(0, 3)}
                    </span>
                    <div className="room-list__name">
                      <strong>{block.day_of_week}</strong>
                      <small>
                        <Clock3 size={13} /> {formatTime(block.start_time)}–
                        {formatTime(block.end_time)}
                      </small>
                    </div>
                    <span className="room-list__capacity">
                      <DoorOpen size={14} /> {block.classroom_name || section.room}
                    </span>
                    <Badge tone={block.modality === "virtual" ? "info" : "neutral"}>
                      {modLabels[block.modality]}
                    </Badge>
                    {editable ? (
                      <div className="row-actions">
                        <button
                          type="button"
                          disabled={busy}
                          title="Editar bloque"
                          aria-label={`Editar bloque del ${block.day_of_week}`}
                          onClick={() => start(block)}
                        >
                          <Pencil />
                        </button>
                        <button
                          type="button"
                          className="danger"
                          disabled={busy}
                          title="Eliminar bloque"
                          aria-label={`Eliminar bloque del ${block.day_of_week}`}
                          onClick={async () => {
                            if (
                              await confirmAction(
                                `¿Eliminar el bloque del ${block.day_of_week} de ${section.code}?`,
                              )
                            )
                              void change(() => api.delete(`${prefix}/${block.meeting_id}`));
                          }}
                        >
                          <Trash2 />
                        </button>
                      </div>
                    ) : (
                      <span />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )
      )}
      {editing && (
        <form className="resource-form" onSubmit={save} onChange={() => setDirty(true)}>
          <label className="form-field">
            <span>Día</span>
            <select
              name="day_of_week"
              defaultValue={existing?.day_of_week}
              required
              onChange={event => setSlot(current => ({ ...current, day: event.target.value }))}
            >
              {weekDays.map(day => (
                <option key={day}>{day}</option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Inicio</span>
            <input
              name="start_time"
              type="time"
              required
              defaultValue={existing?.start_time.slice(0, 5)}
              onChange={event => setSlot(current => ({ ...current, start: event.target.value }))}
            />
          </label>
          <label className="form-field">
            <span>Fin</span>
            <input
              name="end_time"
              type="time"
              required
              defaultValue={existing?.end_time.slice(0, 5)}
              onChange={event => setSlot(current => ({ ...current, end: event.target.value }))}
            />
          </label>
          <label className="form-field">
            <span>Modalidad</span>
            <select
              name="modality"
              defaultValue={existing?.modality}
              onChange={event => setSlot(current => ({ ...current, modality: event.target.value }))}
            >
              {Object.entries(modLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span id={roomLabel}>Aula del bloque</span>
            <select
              aria-labelledby={roomLabel}
              value={room ?? ""}
              disabled={slot.modality === "virtual" || !availability.ready}
              onChange={event => {
                setRoom(event.target.value ? Number(event.target.value) : null);
                setDirty(true);
              }}
            >
              <option value="">Aula de la sección ({String(section.room || "Por asignar")})</option>
              {availability.rooms.map(item => (
                <option
                  key={item.classroom_id}
                  value={item.classroom_id}
                  disabled={item.status !== "available" && item.classroom_id !== room}
                >
                  {item.name} · {item.capacity} plazas
                  {item.status === "available" ? " · Disponible" : ` · ${item.detail}`}
                </option>
              ))}
            </select>
            {slot.modality === "virtual" ? (
              <small className="room-hint">Bloque virtual: no necesita aula.</small>
            ) : !availability.ready ? (
              <small className="room-hint">Elige día y horario para ver las aulas libres.</small>
            ) : roomProblem ? (
              <small className="room-hint room-hint--warning" role="alert">
                <AlertTriangle size={14} /> {roomProblem}. No se podrá guardar.
              </small>
            ) : chosen ? (
              <small className="room-hint room-hint--ok">
                <CheckCircle2 size={14} /> Disponible en ese horario
              </small>
            ) : (
              <small className="room-hint">{freeRoomsLabel(availability.rooms)}</small>
            )}
          </label>
          <label className="form-field">
            <span>Enlace de clase virtual</span>
            <input
              name="virtual_url"
              type="url"
              maxLength={500}
              defaultValue={existing?.virtual_url}
            />
          </label>
          <div className="form-actions">
            <Button type="button" variant="secondary" disabled={busy} onClick={close}>
              Cancelar
            </Button>
            <Button disabled={busy || Boolean(roomProblem)}>
              {busy ? "Guardando…" : "Guardar bloque"}
            </Button>
          </div>
        </form>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </Modal>
  );
}

function RoomDialog({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const [editing, setEditing] = useState<Room | "new" | null>(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  useDraftGuard(dirty, busy);
  const [error, setError] = useState("");
  const key = ["classrooms"];
  const prefix = "/scheduling/classrooms";
  const rooms = useQuery({
    queryKey: key,
    queryFn: () => api.get<Room[]>(prefix).then(response => response.data),
  });
  const existing = editing === "new" ? null : editing;

  async function close() {
    if (busy || (dirty && !(await confirmAction("¿Descartar los cambios del aula?")))) return;
    if (editing) {
      setEditing(null);
      setDirty(false);
      setError("");
    } else onClose();
  }

  async function change(action: () => Promise<unknown>) {
    setError("");
    setBusy(true);
    try {
      await action();
      setEditing(null);
      setDirty(false);
      await client.invalidateQueries({ queryKey: key });
      void client.invalidateQueries({ queryKey: ["lookup", prefix] });
    } catch (failure) {
      setError(apiMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const data = {
      name: String(values.get("name")).trim(),
      location: values.get("location"),
      capacity: Number(values.get("capacity")),
      active: values.has("active"),
    };
    void change(() =>
      existing ? api.put(`${prefix}/${existing.classroom_id}`, data) : api.post(prefix, data),
    );
  }

  return (
    <Modal title="Aulas" onClose={close}>
      {rooms.isLoading ? (
        <Spinner label="Cargando aulas" />
      ) : rooms.error ? (
        <p role="alert">{apiMessage(rooms.error)}</p>
      ) : (
        !editing && (
          <>
            <div className="room-toolbar">
              <p className="muted">
                {rooms.data?.filter(room => room.active).length ?? 0} activas de{" "}
                {rooms.data?.length ?? 0} aulas
              </p>
              <Button
                disabled={busy}
                onClick={() => {
                  setError("");
                  setEditing("new");
                }}
              >
                <Plus size={16} /> Nueva aula
              </Button>
            </div>
            {!rooms.data?.length ? (
              <EmptyState
                icon={<DoorOpen />}
                title="Aún no hay aulas"
                description="Registra las aulas para asignarlas a los bloques de horario."
              />
            ) : (
              <ul className="room-list">
                {[...(rooms.data ?? [])]
                  .sort(
                    (x, y) =>
                      Number(y.active) - Number(x.active) || x.name.localeCompare(y.name, "es"),
                  )
                  .map(room => (
                    <li
                      key={room.classroom_id}
                      className={room.active ? "" : "room-list__item--retired"}
                    >
                      <span className="room-list__icon" aria-hidden="true">
                        <DoorOpen size={18} />
                      </span>
                      <div className="room-list__name">
                        <strong>{room.name}</strong>
                        <small>
                          <MapPin size={13} /> {room.location || "Sin ubicación"}
                        </small>
                      </div>
                      <span className="room-list__capacity">
                        <Users size={14} /> {room.capacity} plazas
                      </span>
                      <Badge tone={room.active ? "success" : "neutral"}>
                        {room.active ? "Activa" : "Retirada"}
                      </Badge>
                      <div className="row-actions">
                        <button
                          type="button"
                          disabled={busy}
                          title="Editar aula"
                          aria-label={`Editar ${room.name}`}
                          onClick={() => {
                            setError("");
                            setEditing(room);
                          }}
                        >
                          <Pencil />
                        </button>
                        {room.active && (
                          <button
                            type="button"
                            className="danger"
                            disabled={busy}
                            title="Retirar aula"
                            aria-label={`Retirar ${room.name}`}
                            onClick={async () => {
                              if (await confirmAction(`¿Retirar el aula ${room.name}?`))
                                void change(() => api.delete(`${prefix}/${room.classroom_id}`));
                            }}
                          >
                            <Archive />
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
              </ul>
            )}
          </>
        )
      )}
      {editing && (
        <form className="resource-form" onSubmit={save} onChange={() => setDirty(true)}>
          <label className="form-field">
            <span>Nombre del aula</span>
            <input name="name" required maxLength={100} defaultValue={existing?.name} />
          </label>
          <label className="form-field">
            <span>Capacidad</span>
            <input
              name="capacity"
              required
              type="number"
              min="1"
              max="1000"
              defaultValue={existing?.capacity ?? 30}
            />
          </label>
          <label className="form-field">
            <span>Ubicación</span>
            <input name="location" maxLength={200} defaultValue={existing?.location} />
          </label>
          <label className="check-field">
            <input type="checkbox" name="active" defaultChecked={existing?.active ?? true} /> Aula
            activa
          </label>
          <div className="form-actions">
            <Button type="button" variant="secondary" disabled={busy} onClick={close}>
              Cancelar
            </Button>
            <Button disabled={busy}>{busy ? "Guardando…" : "Guardar aula"}</Button>
          </div>
        </form>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </Modal>
  );
}
