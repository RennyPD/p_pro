import { useEffect, useState } from "react";
import { api } from "./api";

function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function submit(event) {
    event.preventDefault(); setLoading(true); setError("");
    try {
      const result = await api("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
      localStorage.setItem("p_pro_token", result.access_token); onLogin(result.user);
    } catch (reason) { setError(reason.message); } finally { setLoading(false); }
  }
  return <main className="login-shell"><section className="brand-panel"><span className="eyebrow">p_pro · plataforma educativa</span><h1>La vida académica, en un solo lugar.</h1><p>Consulta horarios, notas, secciones y asistencia con acceso seguro para cada rol.</p><div className="brand-mark">p<span>+</span></div></section><section className="login-panel"><form className="login-card" onSubmit={submit}><span className="eyebrow dark">Acceso seguro</span><h2>Bienvenido</h2><p>Ingresa con tu usuario o correo institucional.</p><label>Usuario o correo<input value={username} onChange={(e) => setUsername(e.target.value)} required /></label><label>Contraseña<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>{error && <div className="error">{error}</div>}<button disabled={loading}>{loading ? "Ingresando…" : "Ingresar"}</button></form></section></main>;
}

function Dashboard({ user, onLogout }) {
  const [items, setItems] = useState([]); const [title, setTitle] = useState("Resumen académico");
  async function load(path, nextTitle) { setTitle(nextTitle); try { setItems(await api(path)); } catch (error) { setItems([{ error: error.message }]); } }
  const studentId = user.student_id; const teacherId = user.teacher_id;
  return <div className="app-shell"><aside><div className="logo">p<span>+</span></div><nav><button onClick={() => { setTitle("Resumen académico"); setItems([]); }}>Inicio</button>{studentId && <><button onClick={() => load(`/academic/students/${studentId}/grades`, "Mis calificaciones")}>Mis notas</button><button onClick={() => load(`/academic/students/${studentId}/schedule`, "Mi horario")}>Mi horario</button><button onClick={() => load("/attendances/", "Mi asistencia")}>Asistencia</button></>}{teacherId && <><button onClick={() => load(`/academic/teachers/${teacherId}/schedule`, "Secciones asignadas")}>Mi horario</button><button onClick={() => load("/enrollments/", "Mis estudiantes")}>Estudiantes</button></>}{!studentId && !teacherId && <><button onClick={() => load("/students/?limit=50", "Estudiantes")}>Estudiantes</button><button onClick={() => load("/teachers/?limit=50", "Docentes")}>Docentes</button><button onClick={() => load("/sections/?limit=50", "Secciones")}>Secciones</button></>}</nav><button className="logout" onClick={onLogout}>Cerrar sesión</button></aside><main className="dashboard"><header><div><span className="eyebrow dark">Panel académico</span><h1>{title}</h1></div><div className="avatar">{user.username.slice(0, 2).toUpperCase()}</div></header>{!items.length ? <section className="welcome-card"><p>Hola,</p><h2>{user.username}</h2><p>Selecciona una opción del menú para consultar la información disponible para tu perfil.</p></section> : <section className="data-grid">{items.map((item, index) => <article key={item.grade_id || item.section_id || item.attendance_id || index}>{Object.entries(item).map(([key, value]) => <div className="field" key={key}><span>{key.replaceAll("_", " ")}</span><strong>{Array.isArray(value) ? value.join(", ") : String(value)}</strong></div>)}</article>)}</section>}</main></div>;
}

export default function App() {
  const [user, setUser] = useState(null);
  useEffect(() => { if (localStorage.getItem("p_pro_token")) api("/auth/me").then(setUser).catch(() => localStorage.removeItem("p_pro_token")); }, []);
  function logout() { localStorage.removeItem("p_pro_token"); setUser(null); }
  return user ? <Dashboard user={user} onLogout={logout} /> : <Login onLogin={setUser} />;
}
