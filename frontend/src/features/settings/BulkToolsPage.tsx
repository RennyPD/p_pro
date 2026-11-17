import { useQueryClient } from "@tanstack/react-query";
import { Download, FileSpreadsheet } from "lucide-react";
import { useState } from "react";
import { Button } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";

type ImportRow = { line: number; status: "valid" | "created" | "unchanged" | "rejected"; detail?: string };
type ImportResult = { rows: ImportRow[]; created: number };
const rowLabels = { valid: "Lista para importar", created: "Importada", unchanged: "Ya registrada", rejected: "Requiere revisión" };

export function BulkToolsPage() {
  const client = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.post<ImportResult>("/bulk/students/import", await file.arrayBuffer(), {
        headers: { "Content-Type": "text/csv" },
        params: { dry_run: dryRun },
      });
      if (dryRun) {
        setPreview(response.data);
        setResult(null);
      } else {
        setResult(response.data);
        setPreview(null);
        void client.invalidateQueries({ queryKey: ["students"] });
        void client.invalidateQueries({ queryKey: ["lookup", "/students/"] });
      }
    } catch (failure) {
      setError(`${file.name}. ${apiMessage(failure)}`);
    } finally {
      setBusy(false);
    }
  }

  async function download(kind: "template" | "export") {
    setError("");
    try {
      const response = await api.get<Blob>(`/bulk/students/${kind}`, { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = kind === "template" ? "plantilla-estudiantes.csv" : "estudiantes.csv";
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) {
      setError(apiMessage(failure));
    }
  }

  const valid = preview?.rows.filter(row => row.status === "valid").length ?? 0;
  const rows = result?.rows ?? preview?.rows;
  return (
    <div className="page">
      <header className="page-header"><h1>Importación y exportación</h1></header>
      <section className="settings-grid">
        <article className="panel bulk-card">
          <h2>Importar estudiantes</h2>
          <p>Usa el código de la carrera en <code>career_code</code>. Deja la matrícula vacía para que se genere automáticamente.</p>
          <Button variant="secondary" onClick={() => void download("template")}><Download /> Descargar plantilla</Button>
          <label className="file-picker">
            <FileSpreadsheet /><span>{file?.name ?? "Seleccionar archivo CSV"}</span>
            <input type="file" accept=".csv,text/csv" disabled={busy} onChange={event => {
              setFile(event.target.files?.[0] ?? null);
              setPreview(null);
              setResult(null);
              setError("");
            }} />
          </label>
          <div className="form-actions">
            <Button variant="secondary" disabled={!file || busy} onClick={() => void send(true)}>{busy ? "Procesando…" : "Validar archivo"}</Button>
            {preview && <Button disabled={!valid || busy} onClick={() => void send(false)}>Importar {valid} {valid === 1 ? "fila" : "filas"}</Button>}
          </div>
        </article>
        <article className="panel bulk-card">
          <h2>Exportar estudiantes</h2>
          <p>Descarga matrículas, nombres, contactos y carrera en formato CSV.</p>
          <Button variant="secondary" onClick={() => void download("export")}><Download /> Descargar CSV</Button>
        </article>
      </section>
      {error && <p className="form-error" role="alert">{error}</p>}
      {rows && <section className="panel">
        <h2>{result ? "Resultado de la importación" : "Revisión antes de importar"}</h2>
        <p role="status">{result ? `Filas importadas: ${result.created}.` : `Filas listas: ${valid}.`}</p>
        {rows.length ? <div className="table-scroll"><table>
          <thead><tr><th>Fila</th><th>Estado</th><th>Detalle</th></tr></thead>
          <tbody>{rows.map(row => <tr key={row.line}><td>{row.line}</td><td>{rowLabels[row.status]}</td><td>{row.detail ?? "—"}</td></tr>)}</tbody>
        </table></div> : <p>El archivo solo contiene encabezados.</p>}
      </section>}
    </div>
  );
}
