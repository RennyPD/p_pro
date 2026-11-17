import { createContext, useContext, useEffect, useId } from "react";

export type DraftState = "dirty" | "saving";
export const DraftContext = createContext<((key: string, state?: DraftState) => void) | null>(null);

export function useDraftGuard(dirty: boolean, saving = false) {
  const register = useContext(DraftContext);
  const key = useId();
  useEffect(() => {
    if (!register || (!dirty && !saving)) return;
    register(key, saving ? "saving" : "dirty");
    return () => register(key);
  }, [register, key, dirty, saving]);
}
