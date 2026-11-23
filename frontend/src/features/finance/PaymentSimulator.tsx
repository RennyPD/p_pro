import { useState } from "react";
import { toast } from "sonner";
import { Button } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import "./finance.css";

/** Test tool: never creates payments or receipts. */
export function PaymentSimulator({ studentId }: { studentId: number }) {
  const base = `/finance/students/${studentId}`;
  const [outcome, setOutcome] = useState("approved");
  const [simulation, setSimulation] = useState<string>();
  const [simAmount, setSimAmount] = useState("100");
  const [simBusy, setSimBusy] = useState(false);
  return (
    <details className="panel finance-simulator">
      <summary>Simulador de pagos · sin dinero real</summary>
      <p>
        Herramienta de pruebas: no crea pagos, recibos ni reduce balances. No solicita datos de
        tarjeta.
      </p>
      <form
        className="finance-form finance-transfer-form"
        onSubmit={async e => {
          e.preventDefault();
          setSimBusy(true);
          try {
            const r = await api.post(base + "/simulate", { amount: simAmount, outcome });
            setSimulation(
              `SIMULACIÓN: ${r.data.outcome === "approved" ? "aprobada" : r.data.outcome === "declined" ? "rechazada" : "cancelada"}. Balance sin cambios.`,
            );
          } catch (err) {
            toast.error(apiMessage(err));
          } finally {
            setSimBusy(false);
          }
        }}
      >
        <label className="form-field">
          <span>Monto simulado RD$</span>
          <input
            required
            type="number"
            min=".01"
            step=".01"
            value={simAmount}
            onChange={e => setSimAmount(e.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Resultado simulado</span>
          <select value={outcome} onChange={e => setOutcome(e.target.value)}>
            <option value="approved">Aprobado</option>
            <option value="declined">Rechazado</option>
            <option value="cancelled">Cancelado</option>
          </select>
        </label>
        <Button disabled={simBusy} variant="secondary">
          Ejecutar simulación
        </Button>
        {simulation && <p role="status">{simulation}</p>}
      </form>
    </details>
  );
}
