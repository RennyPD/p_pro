import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";
import "./users.css";

type Preferences = ApiSchema<"EmailPreferences">;
const OPTIONS: { key: keyof Preferences; label: string; help: string }[] = [
  { key: "email_announcements", label: "Comunicados", help: "Avisos de la institución" },
  { key: "email_grades", label: "Notas publicadas", help: "Cuando el docente publica una nota" },
  {
    key: "email_due_reminders",
    label: "Vencimientos de pago",
    help: "3 días antes y 1 día después si sigue pendiente",
  },
];

/** «Avisos por correo»: each change is saved at once. */
export function EmailPreferencesCard() {
  const client = useQueryClient();
  const [saving, setSaving] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["email-preferences"],
    queryFn: () => api.get<Preferences>("/auth/email-preferences").then(response => response.data),
  });

  async function toggle(key: keyof Preferences, value: boolean) {
    if (!query.data) return;
    setSaving(key);
    try {
      const response = await api.put<Preferences>("/auth/email-preferences", {
        ...query.data,
        [key]: value,
      });
      client.setQueryData(["email-preferences"], response.data);
      toast.success(value ? "Aviso activado" : "Aviso desactivado");
    } catch (error) {
      toast.error(apiMessage(error));
    } finally {
      setSaving(null);
    }
  }

  return (
    <section className="account-card" aria-label="Avisos por correo">
      <span className="account-icon">
        <Mail />
      </span>
      <div>
        <h2>Avisos por correo</h2>
        <p>Los correos de seguridad (recuperar contraseña, invitaciones) siempre se envían.</p>
        {query.isPending ? (
          <Spinner />
        ) : query.isError ? (
          <p className="form-error">{apiMessage(query.error)}</p>
        ) : (
          <div className="email-preferences">
            {OPTIONS.map(option => (
              <label key={option.key}>
                <input
                  type="checkbox"
                  checked={query.data[option.key] ?? true}
                  disabled={saving !== null}
                  onChange={event => void toggle(option.key, event.target.checked)}
                />
                <span>
                  <b>{option.label}</b>
                  <small>{option.help}</small>
                </span>
              </label>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
