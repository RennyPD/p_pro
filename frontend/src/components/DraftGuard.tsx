import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { useBlocker } from "react-router-dom";
import { toast } from "sonner";
import { DraftContext, type DraftState } from "../lib/useDraftGuard";

export function DraftGuard({ children }: { children: ReactNode }) {
  const drafts = useRef(new Map<string, DraftState>());
  const register = useCallback((key: string, state?: DraftState) => {
    if (state) drafts.current.set(key, state);
    else drafts.current.delete(key);
  }, []);
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    drafts.current.size > 0 && (
      currentLocation.pathname !== nextLocation.pathname ||
      currentLocation.search !== nextLocation.search ||
      currentLocation.hash !== nextLocation.hash
    )
  );

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if ([...drafts.current.values()].includes("saving")) {
      toast.info("Espera a que termine el guardado antes de salir.");
      blocker.reset();
    } else if (window.confirm("Hay cambios sin guardar. ¿Salir y descartar el borrador?")) {
      blocker.proceed();
    } else {
      blocker.reset();
    }
  }, [blocker]);

  useEffect(() => {
    function beforeUnload(event: BeforeUnloadEvent) {
      if (!drafts.current.size) return;
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, []);

  return <DraftContext.Provider value={register}>{children}</DraftContext.Provider>;
}
