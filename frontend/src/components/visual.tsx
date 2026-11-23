/**
 * Shared visual system (Fase 2): compact metric, chip, tabs, progress, avatar
 * and section. Mobile first, design tokens only, accessible by default.
 */
import clsx from "clsx";
import { ChevronRight } from "lucide-react";
import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { initials } from "../lib/text";
import "./visual.css";

export type VisualTone = "default" | "danger" | "warning" | "success" | "info";

/** A figure with its label; links somewhere when there is something to do about it. */
export function Metric({
  label,
  value,
  note,
  tone = "default",
  icon,
  to,
  onClick,
}: {
  label: string;
  value: ReactNode;
  note?: string;
  tone?: VisualTone;
  icon?: ReactNode;
  to?: string;
  onClick?: () => void;
}) {
  const body = (
    <>
      <span className="vs-metric__label">
        {icon}
        {label}
      </span>
      <strong className={`vs-metric__value vs-tone--${tone}`}>{value}</strong>
      {note && <small className="vs-metric__note">{note}</small>}
      {(to || onClick) && <ChevronRight className="vs-metric__go" aria-hidden="true" />}
    </>
  );
  if (to)
    return (
      <Link className="vs-metric vs-metric--action" to={to}>
        {body}
      </Link>
    );
  if (onClick)
    return (
      <button type="button" className="vs-metric vs-metric--action" onClick={onClick}>
        {body}
      </button>
    );
  return <div className="vs-metric">{body}</div>;
}

/** Two columns on a phone, as many as fit on wider screens. */
export function MetricRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="vs-metric-row" aria-label={label}>
      {children}
    </section>
  );
}

export function Chip({
  children,
  tone = "default",
  icon,
}: {
  children: ReactNode;
  tone?: VisualTone;
  icon?: ReactNode;
}) {
  return (
    <span className={`vs-chip vs-chip--${tone}`}>
      {icon}
      {children}
    </span>
  );
}

export type TabItem<K extends string> = { key: K; label: string; icon?: ReactNode; count?: number };

/** Accessible tabs: arrow keys move between tabs, the selected one is announced. */
export function Tabs<K extends string>({
  items,
  value,
  onChange,
  label,
  panelId,
}: {
  items: TabItem<K>[];
  value: K;
  onChange: (key: K) => void;
  label: string;
  panelId?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  function move(event: KeyboardEvent, index: number) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + items.length) % items.length;
    refs.current[next]?.focus();
    onChange(items[next].key);
  }
  return (
    <div className="vs-tabs" role="tablist" aria-label={label}>
      {items.map((item, index) => {
        const selected = item.key === value;
        return (
          <button
            key={item.key}
            ref={element => {
              refs.current[index] = element;
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={panelId}
            tabIndex={selected ? 0 : -1}
            className={clsx("vs-tab", selected && "is-active")}
            onClick={() => onChange(item.key)}
            onKeyDown={event => move(event, index)}
          >
            {item.icon}
            <span>{item.label}</span>
            {item.count !== undefined && item.count > 0 && (
              <span className="vs-tab__count">{item.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function Progress({
  value,
  label,
  tone = "info",
}: {
  value: number | null | undefined;
  label: string;
  tone?: VisualTone;
}) {
  const width = Math.max(0, Math.min(100, value ?? 0));
  return (
    <span
      className={`vs-progress vs-progress--${tone}`}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(width)}
    >
      <span style={{ width: `${width}%` }} />
    </span>
  );
}

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  return (
    <span className={`vs-avatar vs-avatar--${size}`} aria-hidden="true">
      {initials(name)}
    </span>
  );
}

/** Panel with a heading, an optional kicker and an action on the right. */
export function Section({
  title,
  kicker,
  icon,
  action,
  children,
  className,
}: {
  title: string;
  kicker?: string;
  icon?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("panel vs-section", className)} aria-label={title}>
      <header className="vs-section__header">
        <div>
          {kicker && <span className="kicker">{kicker}</span>}
          <h2>
            {icon}
            {title}
          </h2>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}
