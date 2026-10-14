import { BookOpenCheck, Building2, CalendarRange, FileSpreadsheet, KeyRound, Layers3, Shield, UserCog } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import "./institution-settings.css";

export function SettingsPage() {
  return <div className="page settings-hub"><header className="page-header"><div><span className="kicker">Administración</span><h1>Configuración</h1><p>Reglas institucionales, seguridad y catálogos, agrupados por responsabilidad.</p></div></header>
    <section className="settings-group"><h2>Reglas académicas</h2><p className="muted">Los cambios sensibles se revisan antes de aplicarse y conservan trazabilidad.</p><div className="settings-grid">
      <Setting to="/settings/institution" icon={<Building2 />} title="Institución y matrícula" text="Identidad, numeración, créditos y nota aprobatoria para nuevas selecciones." />
      <Setting to="/periods" icon={<CalendarRange />} title="Períodos académicos" text="Fechas, selección y cierre verificado, con reapertura controlada." />
      <Setting to="/curriculum" icon={<BookOpenCheck />} title="Pensum académico" text="Materias, créditos, versiones, prerrequisitos y correquisitos." />
      <Setting to="/careers" icon={<Layers3 />} title="Carreras" text="Oferta académica y organización de los programas." />
    </div></section>
    <section className="settings-group"><h2>Seguridad y accesos</h2><div className="settings-grid">
      <Setting to="/settings/access" icon={<Shield />} title="Permisos por rol" text="Revisar concesiones y retiros, justificar cambios y consultar el historial." />
      <Setting to="/roles" icon={<Shield />} title="Roles" text="Catálogo de perfiles; las autorizaciones se gestionan en Permisos por rol." />
      <Setting to="/users" icon={<UserCog />} title="Usuarios" text="Cuentas vinculadas con estudiantes, docentes y tutores." />
      <Setting to="/account" icon={<KeyRound />} title="Mi seguridad" text="Cambiar contraseña y revisar la sesión personal." />
    </div></section>
    <section className="settings-group"><h2>Datos y supervisión</h2><div className="settings-grid">
      <Setting to="/settings/bulk" icon={<FileSpreadsheet />} title="Importar y exportar" text="Carga y descarga de estudiantes en CSV." />
      <Setting to="/institutional-control" icon={<Shield />} title="Control institucional" text="Indicadores, casos de seguimiento y admisiones; separado de la configuración de accesos." />
    </div></section>
  </div>;
}
function Setting({ to, icon, title, text }: { to: string; icon: ReactNode; title: string; text: string }) { return <Link className="setting-card" to={to}><span>{icon}</span><div><h3>{title}</h3><p>{text}</p></div></Link>; }
