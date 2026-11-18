import { Award, CalendarClock, Inbox, NotebookPen } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "../../components/ui";
import { dueLabel } from "../../lib/dueLabel";
import "./task-card.css";

export type TaskTone = "neutral" | "success" | "warning" | "danger" | "info";

export type TaskCardData = {
  title: string;
  instructions: string;
  subjectName: string;
  sectionCode: string;
  teacherName: string;
  dueAt: Date;
  maxScore: number;
  graded: boolean;
  status: string;
  tone: TaskTone;
  submissionCount?: number | null;
};

const shortDate = new Intl.DateTimeFormat("es-DO", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
});

function initials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase())
    .join("");
}

export function TaskCard({ task, actions }: { task: TaskCardData; actions: ReactNode }) {
  const overdue = task.dueAt.getTime() < Date.now();
  return (
    <article className="task-card" data-tone={task.tone}>
      <header className="task-card__header">
        <div className="task-card__course">
          <span className="task-card__subject" title={task.subjectName}>
            {task.subjectName}
          </span>
          <span className="task-card__section">{task.sectionCode}</span>
        </div>
        <Badge tone={task.tone}>{task.status}</Badge>
      </header>

      <h2 className="task-card__title">{task.title}</h2>
      {task.instructions && <p className="task-card__summary">{task.instructions}</p>}

      <ul className="task-card__meta">
        <li
          className={overdue ? "is-overdue" : undefined}
          title={task.dueAt.toLocaleString("es-DO")}
        >
          <CalendarClock size={16} aria-hidden />
          <span>
            <strong>{dueLabel(task.dueAt)}</strong>
            <small>{shortDate.format(task.dueAt)}</small>
          </span>
        </li>
        <li>
          {task.graded ? <Award size={16} aria-hidden /> : <NotebookPen size={16} aria-hidden />}
          <span>
            <strong>{task.graded ? `${task.maxScore} pts` : "Práctica"}</strong>
            <small>{task.graded ? "Cuenta para la nota" : "No afecta la nota"}</small>
          </span>
        </li>
      </ul>

      <footer className="task-card__footer">
        <span className="task-card__teacher">
          <span className="task-card__avatar" aria-hidden>
            {initials(task.teacherName)}
          </span>
          {task.teacherName}
        </span>
        {task.submissionCount != null && (
          <span className="task-card__count">
            <Inbox size={15} aria-hidden />
            {task.submissionCount} {task.submissionCount === 1 ? "entrega" : "entregas"}
          </span>
        )}
      </footer>

      <div className="task-card__actions">{actions}</div>
    </article>
  );
}
