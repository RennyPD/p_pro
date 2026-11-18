import { confirmAction } from "../../lib/confirm";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, DoorOpen } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { DocumentDownload } from "../../components/DocumentDownload";
import { LookupSelect } from "../../components/LookupSelect";
import { Button, Modal, Spinner } from "../../components/ui";
import { resources } from "../../config/resources";
import { api, apiMessage } from "../../lib/api";
import { weekDays } from "../../lib/schedule";
import { useDraftGuard } from "../../lib/useDraftGuard";
import { useAuthStore } from "../../store/auth";
import type { EntityRecord, LookupConfig, ResourceConfig } from "../../types";
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
const roomLookup: LookupConfig = {
  endpoint: "/scheduling/classrooms",
  valueKey: "classroom_id",
  labelKeys: ["name"],
  secondaryKey: "location",
  placeholder: "Buscar aula",
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
              >
                Publicar
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

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const payload = { ...values, section_id: section.section_id, classroom_id: room };
    void change(() =>
      existing ? api.put(`${prefix}/${existing.meeting_id}`, payload) : api.post(prefix, payload),
    );
  }

  return (
    <Modal title={`Horario de ${section.code}`} onClose={close}>
      {!editing && (
        <DocumentDownload
          path={`/documents/sections/${section.section_id}/roster.pdf`}
          filename={`lista-${section.code}.pdf`}
          label="Descargar lista PDF"
        />
      )}
      {blocks.isLoading ? (
        <Spinner label="Cargando bloques" />
      ) : blocks.error ? (
        <p role="alert">{apiMessage(blocks.error)}</p>
      ) : (
        !editing && (
          <>
            {!blocks.data?.length && (
              <p>
                Horario de respaldo:{" "}
                {Array.isArray(section.days_of_week)
                  ? section.days_of_week.join(", ")
                  : section.days_of_week}{" "}
                · {String(section.start_time).slice(0, 5)}–{String(section.end_time).slice(0, 5)}.
                Al agregar bloques, estos reemplazarán ese horario.
              </p>
            )}
            {blocks.data?.map(block => (
              <article className="panel" key={block.meeting_id}>
                <strong>
                  {block.day_of_week} · {block.start_time.slice(0, 5)}–{block.end_time.slice(0, 5)}
                </strong>
                <p>
                  {block.classroom_name || section.room} · {modLabels[block.modality]}
                </p>
                {editable && (
                  <div className="form-actions">
                    <Button variant="secondary" disabled={busy} onClick={() => start(block)}>
                      Editar bloque
                    </Button>
                    <Button
                      variant="danger"
                      disabled={busy}
                      onClick={async () => {
                        if (
                          await confirmAction(
                            `¿Eliminar el bloque del ${block.day_of_week} de ${section.code}?`,
                          )
                        )
                          void change(() => api.delete(`${prefix}/${block.meeting_id}`));
                      }}
                    >
                      Eliminar bloque
                    </Button>
                  </div>
                )}
              </article>
            ))}
            {editable && (
              <Button disabled={busy} onClick={() => start("new")}>
                Agregar bloque
              </Button>
            )}
          </>
        )
      )}
      {editing && (
        <form className="resource-form" onSubmit={save} onChange={() => setDirty(true)}>
          <label className="form-field">
            <span>Día</span>
            <select name="day_of_week" defaultValue={existing?.day_of_week} required>
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
            />
          </label>
          <label className="form-field">
            <span>Fin</span>
            <input
              name="end_time"
              type="time"
              required
              defaultValue={existing?.end_time.slice(0, 5)}
            />
          </label>
          <label className="form-field">
            <span>Modalidad</span>
            <select name="modality" defaultValue={existing?.modality}>
              {Object.entries(modLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <div className="form-field">
            <span id={roomLabel}>Aula del bloque</span>
            <LookupSelect
              config={roomLookup}
              labelId={roomLabel}
              value={room}
              onChange={value => {
                setRoom(value === null ? null : Number(value));
                setDirty(true);
              }}
            />
          </div>
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
            <Button disabled={busy}>{busy ? "Guardando…" : "Guardar bloque"}</Button>
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
            {!rooms.data?.length && <p>Aún no hay aulas registradas.</p>}
            {rooms.data?.map(room => (
              <article className="panel" key={room.classroom_id}>
                <strong>{room.name}</strong>
                <p>
                  {room.capacity} plazas · {room.active ? "Activa" : "Retirada"}
                  {room.location ? ` · ${room.location}` : ""}
                </p>
                <div className="form-actions">
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => {
                      setError("");
                      setEditing(room);
                    }}
                  >
                    Editar aula
                  </Button>
                  {room.active && (
                    <Button
                      variant="danger"
                      disabled={busy}
                      onClick={async () => {
                        if (await confirmAction(`¿Retirar el aula ${room.name}?`))
                          void change(() => api.delete(`${prefix}/${room.classroom_id}`));
                      }}
                    >
                      Retirar aula
                    </Button>
                  )}
                </div>
              </article>
            ))}
            <Button
              disabled={busy}
              onClick={() => {
                setError("");
                setEditing("new");
              }}
            >
              Nueva aula
            </Button>
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
