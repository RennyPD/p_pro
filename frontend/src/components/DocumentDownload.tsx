import { Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { Button } from "./ui";

export function DocumentDownload({
  path,
  filename,
  label,
}: {
  path: string;
  filename: string;
  label: string;
}) {
  const [busy, setBusy] = useState(false);
  async function download() {
    setBusy(true);
    try {
      const response = await api.get<Blob>(path, { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      toast.error(`No se pudo descargar ${filename}. Comprueba tu sesión e inténtalo de nuevo.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button type="button" variant="secondary" disabled={busy} onClick={() => void download()}>
      <Download size={16} /> {busy ? "Descargando…" : label}
    </Button>
  );
}
