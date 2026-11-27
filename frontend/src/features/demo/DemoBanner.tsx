import { Link } from "react-router-dom";
import { DEMO_FLAG } from "./DemoPage";
import "./demo.css";

function inDemo() {
  try {
    return sessionStorage.getItem(DEMO_FLAG) === "1";
  } catch {
    return false;
  }
}

/** Reminds visitors that they are in the shared demo (Fase 5 G2). */
export function DemoBanner() {
  if (!inDemo()) return null;
  return (
    <div className="demo-banner" role="note">
      Estás en la demo: los datos son ficticios y se restauran cada noche.{" "}
      <Link to="/demo">Cambiar de rol</Link>
    </div>
  );
}
