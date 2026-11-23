import {
  BookOpenCheck,
  Building2,
  CalendarRange,
  FileSpreadsheet,
  KeyRound,
  Layers3,
  Ruler,
  Shield,
  UserCog,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAccess } from "../../lib/permissions";
import "./institution-settings.css";

export function SettingsPage() {
  return (
    <div className="page settings-hub">
      <header className="page-header">
        <div>
          <span className="kicker">Administración</span>
          <h1>Configuración</h1>
          <p>Reglas institucionales, seguridad y catálogos, agrupados por responsabilidad.</p>
        </div>
      </header>
      <section className="settings-group">
        <h2>Reglas académicas</h2>
        <p className="muted">
          Los cambios sensibles se revisan antes de aplicarse y conservan trazabilidad.
        </p>
        <div className="settings-grid">
          <Setting
            to="/settings/institution"
            permission="settings.manage"
            icon={<Building2 />}
            title="Institución y matrícula"
            text="Identidad, numeración, créditos y nota aprobatoria para nuevas selecciones."
          />
          <Setting
            to="/settings/grading-scales"
            permission="settings.manage"
            icon={<Ruler />}
            title="Escalas de calificación"
            text="Numérica, letras o conceptual por programa, con nota mínima y recuperación."
          />
          <Setting
            to="/periods"
            permission="settings.manage"
            icon={<CalendarRange />}
            title="Períodos académicos"
            text="Fechas, selección y cierre verificado, con reapertura controlada."
          />
          <Setting
            to="/curriculum"
            permission="programs.manage"
            icon={<BookOpenCheck />}
            title="Pensum académico"
            text="Materias, créditos, versiones, prerrequisitos y correquisitos."
          />
          <Setting
            to="/careers"
            permission="programs.manage"
            icon={<Layers3 />}
            title="Carreras"
            text="Oferta académica y organización de los programas."
          />
        </div>
      </section>
      <section className="settings-group">
        <h2>Seguridad y accesos</h2>
        <div className="settings-grid">
          <Setting
            to="/roles"
            permission="roles.manage"
            icon={<Shield />}
            title="Roles y permisos"
            text="Crear roles por puesto, elegir su ámbito de datos y activar sus permisos."
          />
          <Setting
            to="/users"
            permission="users.manage"
            icon={<UserCog />}
            title="Usuarios"
            text="Cuentas vinculadas con estudiantes, docentes y tutores."
          />
          <Setting
            to="/account"
            icon={<KeyRound />}
            title="Mi seguridad"
            text="Cambiar contraseña y revisar la sesión personal."
          />
        </div>
      </section>
      <section className="settings-group">
        <h2>Datos y supervisión</h2>
        <div className="settings-grid">
          <Setting
            to="/settings/bulk"
            permission="students.manage"
            icon={<FileSpreadsheet />}
            title="Importar y exportar"
            text="Carga y descarga de estudiantes en CSV."
          />
          <Setting
            to="/settings/audit"
            permission="audit.view"
            icon={<Shield />}
            title="Auditoría administrativa"
            text="Filtra eventos por actor, acción, recurso y fecha."
          />
          <Setting
            to="/institutional-control"
            permission="reports.view"
            icon={<Shield />}
            title="Control institucional"
            text="Indicadores, casos de seguimiento y admisiones; separado de la configuración de accesos."
          />
        </div>
      </section>
    </div>
  );
}
function Setting({
  to,
  permission,
  icon,
  title,
  text,
}: {
  to: string;
  permission?: string;
  icon: ReactNode;
  title: string;
  text: string;
}) {
  const access = useAccess();
  if (permission && !access.can(permission)) return null;
  return (
    <Link className="setting-card" to={to}>
      <span>{icon}</span>
      <div>
        <h3>{title}</h3>
        <p>{text}</p>
      </div>
    </Link>
  );
}
