import { useEffect } from "react";
import { useAuthStore } from "../store/auth";
import { renewSession, tokenNeedsRefresh } from "./api";

const RECENT_ACTIVITY = 5 * 60_000;

/** Renew while the person is using the page, not endlessly in abandoned tabs. */
export function useSessionRenewal() {
  useEffect(() => {
    let lastActivity = Date.now();
    let lastCheck = 0;
    const check = () => {
      const now = Date.now();
      if (
        document.visibilityState === "hidden" ||
        now - lastActivity > RECENT_ACTIVITY ||
        now - lastCheck < 10_000
      )
        return;
      const { token } = useAuthStore.getState();
      if (!token || !tokenNeedsRefresh(token)) return;
      lastCheck = now;
      void renewSession().catch(() => {});
    };
    const activity = () => {
      lastActivity = Date.now();
      check();
    };
    const events = ["pointerdown", "pointermove", "keydown", "scroll", "focus"] as const;
    events.forEach(event => window.addEventListener(event, activity, { passive: true }));
    document.addEventListener("visibilitychange", activity);
    const timer = window.setInterval(check, 30_000);
    const unsubscribe = useAuthStore.subscribe((state, previous) => {
      if (state.token && !previous.token) activity();
    });
    check();
    return () => {
      window.clearInterval(timer);
      unsubscribe();
      events.forEach(event => window.removeEventListener(event, activity));
      document.removeEventListener("visibilitychange", activity);
    };
  }, []);
}
