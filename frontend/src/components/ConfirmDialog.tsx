import { useEffect, useId, useRef, useState } from "react";
import { Button } from "./ui";
import { registerConfirmHost, type ConfirmRequest } from "../lib/confirm";
import "./confirm-dialog.css";

export function ConfirmHost() {
  const [queue, setQueue] = useState<ConfirmRequest[]>([]);

  useEffect(() => {
    return registerConfirmHost(request => setQueue(items => [...items, request]));
  }, []);

  const current = queue[0];
  if (!current) return null;

  const answer = (value: boolean) => {
    current.resolve(value);
    setQueue(items => items.slice(1));
  };
  return <ConfirmDialog key={queue.length} request={current} onAnswer={answer} />;
}

function ConfirmDialog({
  request,
  onAnswer,
}: {
  request: ConfirmRequest;
  onAnswer: (value: boolean) => void;
}) {
  const titleId = useId();
  const messageId = useId();
  const dialog = useRef<HTMLElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const answer = useRef(onAnswer);

  useEffect(() => {
    answer.current = onAnswer;
  }, [onAnswer]);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    cancel.current?.focus();
    // Capture phase on window: runs before any underlying modal's handlers.
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        answer.current(false);
        return;
      }
      if (event.key !== "Tab") return;
      event.stopPropagation();
      const buttons = Array.from(dialog.current?.querySelectorAll<HTMLElement>("button") ?? []);
      const first = buttons[0];
      const last = buttons.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    window.addEventListener("keydown", handleKey, true);
    return () => {
      window.removeEventListener("keydown", handleKey, true);
      previous?.focus();
    };
  }, []);

  return (
    <div
      className="modal-backdrop confirm-backdrop"
      role="presentation"
      onMouseDown={event => event.target === event.currentTarget && onAnswer(false)}
    >
      <section
        ref={dialog}
        className="modal confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
      >
        <h2 id={titleId}>{request.title ?? "Confirmar acción"}</h2>
        <p id={messageId}>{request.message}</p>
        <div className="form-actions">
          <Button ref={cancel} type="button" variant="secondary" onClick={() => onAnswer(false)}>
            {request.cancelLabel ?? "Cancelar"}
          </Button>
          <Button
            type="button"
            variant={request.tone === "danger" ? "danger" : "primary"}
            onClick={() => onAnswer(true)}
          >
            {request.confirmLabel ?? "Confirmar"}
          </Button>
        </div>
      </section>
    </div>
  );
}
