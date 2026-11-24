// Error tracking without personal data (Fase 4 C). Loaded only when
// VITE_SENTRY_DSN is set, as a separate chunk, so the app does not grow.
// Events keep the error, the page path and the release; never URLs with
// queries, request bodies, breadcrumbs (clicks, console, network) or the user.
import type { ErrorEvent } from "@sentry/react";

const EMAIL = /[\w.+-]+@[\w-]+(\.[\w-]+)+/g;
const LONG_NUMBER = /\d[\d -]{6,}\d/g;
const TOKEN = /\b(bearer|token|password|secret)\b[=: ]+\S+/gi;

export function mask(text: string) {
  return text
    .replace(EMAIL, "[correo]")
    .replace(TOKEN, (_match, word: string) => `${word} [oculto]`)
    .replace(LONG_NUMBER, "[número]");
}

export function scrub(event: ErrorEvent): ErrorEvent {
  const url = event.request?.url?.split("?")[0]?.split("#")[0];
  event.request = url ? { url } : undefined;
  delete event.user;
  delete event.breadcrumbs;
  delete event.extra;
  if (event.message) event.message = mask(event.message);
  for (const exception of event.exception?.values ?? []) {
    if (exception.value) exception.value = mask(exception.value);
  }
  return event;
}

export async function initErrorTracking(dsn = import.meta.env.VITE_SENTRY_DSN) {
  if (!dsn) return false;
  const Sentry = await import("@sentry/react");
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    release: import.meta.env.VITE_RELEASE,
    sendDefaultPii: false,
    maxBreadcrumbs: 0,
    defaultIntegrations: false,
    integrations: [
      Sentry.globalHandlersIntegration(),
      Sentry.linkedErrorsIntegration(),
      Sentry.dedupeIntegration(),
    ],
    beforeSend: scrub,
  });
  return true;
}
