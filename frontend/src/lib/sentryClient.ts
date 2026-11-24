// Only what error tracking uses, so the lazy chunk leaves out Replay,
// Feedback and tracing (Fase 4 C).
export {
  dedupeIntegration,
  globalHandlersIntegration,
  init,
  linkedErrorsIntegration,
} from "@sentry/react";
