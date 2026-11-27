import { useMutation, useQuery } from "@tanstack/react-query";
import { BookOpen, GraduationCap, Home, School } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Button, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import type { TokenResponse } from "../../types";
import "./demo.css";

type DemoInfo = { enabled: boolean; roles: { role: string; label: string }[] };

const ROLES: Record<string, { icon: typeof School; text: string }> = {
  admin: {
    icon: School,
    text: "Estudiantes, oferta académica, finanzas, comprobantes y reportes.",
  },
  teacher: { icon: BookOpen, text: "Secciones, calificaciones, asistencia y tareas." },
  student: { icon: GraduationCap, text: "Horario, notas, selección de asignaturas y cuenta." },
  guardian: { icon: Home, text: "Seguimiento de los hijos: notas, asistencia, tareas y pagos." },
};

export const DEMO_FLAG = "nexo_demo";

/** One-click entry to the public demo (Fase 5 G2). */
export function DemoPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore(state => state.setSession);
  const info = useQuery({
    queryKey: ["public-demo"],
    queryFn: () => api.get<DemoInfo>("/public/demo").then(r => r.data),
    retry: false,
  });
  const enter = useMutation({
    mutationFn: (role: string) =>
      api.post<TokenResponse>("/public/demo/login", { role }).then(r => r.data),
    onSuccess: data => {
      try {
        sessionStorage.setItem(DEMO_FLAG, "1");
      } catch {
        // Private mode: the demo still works, only the notice is missing.
      }
      setSession(data.access_token, data.user);
      navigate("/");
    },
  });
  return (
    <main className="demo-page">
      <header>
        <span className="kicker">Demo de Nexo</span>
        <h1>Elige cómo quieres entrar</h1>
        <p>
          Una institución de ejemplo con escuela y universidad. Puedes cambiar lo que quieras: los
          datos se restauran cada noche. No se envían correos ni se cobra nada.
        </p>
      </header>
      {info.isPending ? (
        <Spinner label="Preparando la demo" />
      ) : !info.data?.enabled ? (
        <p className="muted">La demo no está disponible en este momento.</p>
      ) : (
        <div className="demo-roles">
          {info.data.roles.map(item => {
            const role = ROLES[item.role];
            const Icon = role?.icon ?? School;
            return (
              <article key={item.role} className="panel demo-role">
                <Icon aria-hidden />
                <h2>{item.label}</h2>
                <p>{role?.text}</p>
                <Button disabled={enter.isPending} onClick={() => enter.mutate(item.role)}>
                  Entrar como {item.label.toLowerCase()}
                </Button>
              </article>
            );
          })}
        </div>
      )}
      {enter.error && (
        <p className="form-error" role="alert">
          {apiMessage(enter.error)}
        </p>
      )}
      <p>
        <Link to="/registro">Crear la cuenta de mi institución</Link>
      </p>
    </main>
  );
}
