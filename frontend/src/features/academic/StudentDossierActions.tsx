import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { DocumentDownload } from "../../components/DocumentDownload";
import { LookupSelect } from "../../components/LookupSelect";
import { Button, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useDraftGuard } from "../../lib/useDraftGuard";
import { useAuthStore } from "../../store/auth";
import type { LookupConfig } from "../../types";

const guardianLookup: LookupConfig = {
  endpoint: "/community/guardians", valueKey: "guardian_id",
  labelKeys: ["first_name", "last_name"], secondaryKey: "email", placeholder: "Buscar tutor",
};
const limit = 5 * 1024 * 1024;
const documentTypes: Record<string, string> = { identification: "Documento de identidad", transcript: "Récord de notas", birth_certificate: "Acta de nacimiento", photo: "Fotografía", medical: "Certificado médico", diploma: "Título de bachillerato", certificate: "Certificado" };
/** Seeded/legacy documents use English codes; manual uploads already carry a readable type. */
const documentTypeLabel = (type: string) => documentTypes[type] ?? type;
type StudentDocument = { student_document_id: number; filename: string; document_type: string; expires_on: string | null };
type CareerImpact = { current_career: string; target_career: string; effective_date: string; active_selections: number; cart_outside_plan: number };
const careerLookup: LookupConfig = {
  endpoint: "/careers/", valueKey: "career_id", labelKeys: ["code", "name"], placeholder: "Buscar carrera",
};

export function CareerChangeDialog({ studentId, careerId, onClose }: { studentId: string; careerId: number; onClose: () => void }) {
  const label = useId();
  const client = useQueryClient();
  const [target, setTarget] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = `/governance/students/${studentId}/career-change`;
  const preview = useQuery({
    queryKey: ["career-change-preview", studentId, careerId, target],
    queryFn: () => api.get<CareerImpact>(`${path}/preview`, { params: { career_id: target } }).then(response => response.data),
    enabled: Boolean(target && target !== careerId),
  });
  useDraftGuard(Boolean(target || reason), busy);
  function close() {
    if (!busy && ((!target && !reason) || window.confirm("¿Descartar la solicitud de traslado?"))) onClose();
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preview.data || !target) return;
    setBusy(true);
    setError("");
    try {
      await api.post(path, { new_career_id: target, expected_career_id: careerId, reason: reason.trim() });
      for (const key of ["student-profile", "students", "student-transcript", "course-catalog", "course-selection-cart"]) {
        void client.invalidateQueries({ queryKey: [key] });
      }
      toast.success("Traslado de carrera registrado");
      onClose();
    } catch (failure) { setError(apiMessage(failure)); }
    finally { setBusy(false); }
  }
  return <Modal title="Traslado de carrera inmediato" onClose={close}>
    <form className="resource-form" onSubmit={submit}>
      <div className="form-field"><span id={label}>Carrera de destino</span><LookupSelect config={careerLookup} labelId={label} required value={target} onChange={value => {
        setTarget(Number(value)); setError("");
      }} /></div>
      {target === careerId && <p role="alert">Selecciona una carrera distinta de la actual.</p>}
      {preview.isFetching && <Spinner label="Calculando impacto" />}
      {preview.error && <p role="alert">{apiMessage(preview.error)}</p>}
      {preview.data && <div className="period-effect">
        <strong>{preview.data.current_career} → {preview.data.target_career}</strong>
        <p>Fecha efectiva {preview.data.effective_date}.</p>
        <p>{preview.data.active_selections} selecciones activas en el expediente. {preview.data.cart_outside_plan} secciones del carrito quedan fuera del plan destino.</p>
      </div>}
      <label className="form-field"><span>Motivo del traslado</span><textarea required rows={3} value={reason} onChange={event => setReason(event.target.value)} /></label>
      {error && <p role="alert" className="form-error">{error}</p>}
      <div className="form-actions">
        <Button type="button" variant="secondary" disabled={busy} onClick={close}>Cancelar</Button>
        <Button disabled={!preview.data || preview.isFetching || busy || reason.trim().length < 3}>{busy ? "Registrando…" : "Confirmar traslado"}</Button>
      </div>
    </form>
  </Modal>;
}

export function GuardianDialog({ studentId, onClose }: { studentId: string; onClose: () => void }) {
  const lookupId = useId();
  const client = useQueryClient();
  const [mode, setMode] = useState("existing");
  const [guardian, setGuardian] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useDraftGuard(dirty, busy);
  function close() {
    if (!busy && (!dirty || window.confirm("¿Descartar los datos del vínculo?"))) onClose();
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "existing" && !guardian) return;
    const fields = new FormData(event.currentTarget);
    const newGuardian = Object.fromEntries(
      ["first_name", "last_name", "email", "telephone", "address"].map(key => [key, String(fields.get(key) ?? "").trim()]),
    );
    setBusy(true);
    setError("");
    try {
      await api.post(`/community/students/${studentId}/guardians`, {
        guardian_id: mode === "existing" ? guardian : null,
        new_guardian: mode === "new" ? newGuardian : null,
        relationship: String(fields.get("relationship")).trim(),
        primary_contact: fields.has("primary_contact"),
        emergency_contact: fields.has("emergency_contact"),
        authorized_pickup: fields.has("authorized_pickup"),
      });
      void client.invalidateQueries({ queryKey: ["student-guardians", studentId] });
      void client.invalidateQueries({ queryKey: ["lookup", "/community/guardians"] });
      void client.invalidateQueries({ queryKey: ["guardian-overview"] });
      toast.success("Tutor vinculado");
      onClose();
    } catch (failure) { setError(apiMessage(failure)); }
    finally { setBusy(false); }
  }
  return <Modal title="Vincular tutor" onClose={close}>
    <form className="resource-form" onSubmit={submit} onChange={() => setDirty(true)}>
      <label className="form-field"><span>Origen del vínculo</span><select value={mode} disabled={busy} onChange={event => setMode(event.target.value)}>
        <option value="existing">Tutor existente</option><option value="new">Registrar un tutor</option>
      </select></label>
      {mode === "existing" ? <div className="form-field"><span id={lookupId}>Tutor</span>
        <LookupSelect config={guardianLookup} labelId={lookupId} value={guardian} required onChange={value => {
          setGuardian(Number(value));
          setDirty(true);
        }} />
      </div> : <>
        <label className="form-field"><span>Nombres</span><input name="first_name" required maxLength={100} /></label>
        <label className="form-field"><span>Apellidos</span><input name="last_name" required maxLength={100} /></label>
        <label className="form-field"><span>Correo</span><input name="email" type="email" required maxLength={255} /></label>
        <label className="form-field"><span>Teléfono</span><input name="telephone" type="tel" required maxLength={30} /></label>
        <label className="form-field"><span>Dirección</span><input name="address" maxLength={255} /></label>
      </>}
      <label className="form-field"><span>Relación con el estudiante</span><input name="relationship" required minLength={2} maxLength={50} /></label>
      <label className="check-field"><input name="primary_contact" type="checkbox" /> Contacto principal</label>
      <label className="check-field"><input name="emergency_contact" type="checkbox" /> Contacto de emergencia</label>
      <label className="check-field"><input name="authorized_pickup" type="checkbox" /> Retiro autorizado</label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="form-actions">
        <Button type="button" variant="secondary" disabled={busy} onClick={close}>Cancelar</Button>
        <Button disabled={busy || (mode === "existing" && !guardian)}>{busy ? "Guardando…" : "Guardar vínculo"}</Button>
      </div>
    </form>
  </Modal>;
}

export function StudentDocuments({ studentId, canUpload = false }: { studentId: string; canUpload?: boolean }) {
  const client = useQueryClient();
  const uid = useAuthStore(state => state.user?.user_id);
  const [upload, setUpload] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = `/operations/students/${studentId}/documents`;
  const key = ["student-documents", studentId, uid];
  const documents = useQuery({ queryKey: key, queryFn: () => api.get<StudentDocument[]>(path).then(response => response.data) });
  useDraftGuard(dirty, busy);
  function close() {
    if (busy || (dirty && !window.confirm("¿Descartar la carga del documento?"))) return;
    setUpload(false);
    setDirty(false);
    setError("");
    setFile(null);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    if (file.size > limit) { setError("El archivo supera 5 MB. Selecciona un archivo más pequeño."); return; }
    const fields = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api.post(path, {
        filename: file.name, mime_type: file.type,
        document_type: String(fields.get("document_type")).trim(),
        expires_on: fields.get("expires_on") || null,
        content_base64: await fileAsBase64(file),
      });
      void client.invalidateQueries({ queryKey: key });
      setUpload(false);
      setDirty(false);
      setFile(null);
      toast.success("Documento incorporado al expediente");
    } catch (failure) { setError(apiMessage(failure)); }
    finally { setBusy(false); }
  }
  return <section className="panel dossier-panel">
    <div className="panel-heading"><h2>Archivo del expediente</h2>{canUpload && <Button onClick={() => setUpload(true)}>Agregar documento</Button>}</div>
    {documents.isLoading ? <Spinner label="Cargando documentos" /> : documents.error ? (
      <p role="alert" className="form-error">{apiMessage(documents.error)}</p>
    ) : documents.data?.length ? <ul className="document-list">{documents.data.map(document => <li key={document.student_document_id}>
      <div><strong>{documentTypeLabel(document.document_type)}</strong><small>{document.filename}{document.expires_on ? ` · vence el ${document.expires_on}` : ""}</small></div>
      <DocumentDownload path={`/operations/documents/${document.student_document_id}/download`} filename={document.filename} label="Descargar" />
    </li>)}</ul> : <p>Aún no hay documentos en este expediente.</p>}
    {upload && <Modal title="Agregar documento al expediente" onClose={close}>
      <form className="resource-form" onSubmit={submit} onChange={() => setDirty(true)}>
        <label className="form-field"><span>Tipo de documento</span><input name="document_type" required maxLength={50} placeholder="Ej. Certificado de bachillerato" /></label>
        <label className="form-field"><span>Vencimiento, si aplica</span><input name="expires_on" type="date" /></label>
        <label className="form-field"><span>Archivo PDF, PNG o JPEG de hasta 5 MB</span><input type="file" required accept="application/pdf,image/png,image/jpeg" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
        {error && <p role="alert" className="form-error">{error}</p>}
        <div className="form-actions">
          <Button type="button" variant="secondary" disabled={busy} onClick={close}>Cancelar</Button>
          <Button disabled={busy || !file}>{busy ? "Subiendo…" : "Guardar documento"}</Button>
        </div>
      </form>
    </Modal>}
  </section>;
}

function fileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.readAsDataURL(file);
  });
}
