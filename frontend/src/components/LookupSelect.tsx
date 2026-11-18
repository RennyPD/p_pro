import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { fetchAllOptions } from "../lib/options";
import { useAuthStore } from "../store/auth";
import type { EntityRecord, LookupConfig } from "../types";

const PAGE_SIZE = 8;
const text = (value: unknown) =>
  value == null ? "" : Array.isArray(value) ? value.join(", ") : String(value);
const normalize = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase()
    .trim();

export function LookupSelect({
  config,
  value,
  onChange,
  labelId,
  required,
}: {
  config: LookupConfig;
  value: number | string | null | undefined;
  onChange: (value: number | string | null) => void;
  labelId: string;
  required?: boolean;
}) {
  const user = useAuthStore(s => s.user);
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const pagination = useRef<HTMLElement>(null);
  const optionList = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const {
    data = [],
    isPending,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["lookup", config.endpoint, config.valueKey, user?.user_id, user?.role_name],
    queryFn: ({ signal }) =>
      fetchAllOptions<EntityRecord>(config.endpoint, config.valueKey, {}, signal),
  });
  const label = (item: EntityRecord) =>
    config.labelKeys
      .map(key => text(item[key]))
      .filter(Boolean)
      .join(" · ");
  const selected = data.find(item => String(item[config.valueKey]) === String(value));
  const filtered = data.filter(item =>
    normalize(
      `${label(item)} ${config.secondaryKey ? text(item[config.secondaryKey]) : ""}`,
    ).includes(normalize(query)),
  );
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const options = filtered.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  const hasValue = value !== undefined && value !== null && value !== "";

  useEffect(() => {
    if (!open) return;
    search.current?.focus();
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  function close() {
    setOpen(false);
    trigger.current?.focus();
  }
  function changePage(nextPage: number) {
    // Keep focus inside the selector before the clicked button becomes disabled.
    // Otherwise Chromium can emit a blur with no related target and close it.
    pagination.current?.focus({ preventScroll: true });
    if (optionList.current) optionList.current.scrollTop = 0;
    setPage(nextPage);
  }
  return (
    <div
      ref={root}
      className="lookup-field"
      onBlur={event => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
      onKeyDown={event => {
        if (event.key === "Escape" && open) {
          event.preventDefault();
          event.stopPropagation();
          close();
        }
      }}
    >
      <div className="lookup-control">
        <button
          ref={trigger}
          type="button"
          className="lookup-trigger"
          aria-labelledby={`${labelId} ${id}-value`}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-controls={open ? `${id}-panel` : undefined}
          onClick={() => {
            if (!open) {
              setQuery("");
              setPage(Math.max(0, Math.floor(data.indexOf(selected!) / PAGE_SIZE)));
            }
            setOpen(previous => !previous);
          }}
        >
          <span id={`${id}-value`} className={selected ? "" : "muted"}>
            {selected
              ? label(selected)
              : isPending
                ? "Cargando opciones…"
                : hasValue
                  ? `Selección actual: ${value} (no disponible en este catálogo)`
                  : (config.placeholder ?? "Selecciona una opción")}
          </span>
          <ChevronDown aria-hidden="true" />
        </button>
        {hasValue && (
          <button
            type="button"
            className="lookup-clear"
            aria-label="Limpiar selección"
            disabled={required}
            title={
              required
                ? "Este campo es obligatorio; selecciona otra opción para cambiarlo"
                : "Limpiar selección"
            }
            onClick={() => {
              onChange(null);
              trigger.current?.focus();
            }}
          >
            <X aria-hidden="true" />
          </button>
        )}
      </div>
      {open && (
        <div id={`${id}-panel`} role="dialog" aria-labelledby={labelId} className="lookup-popover">
          <div className="lookup-search">
            <Search aria-hidden="true" />
            <input
              ref={search}
              type="search"
              aria-label="Buscar opciones"
              placeholder="Escribe para buscar…"
              value={query}
              onChange={event => {
                setQuery(event.target.value);
                setPage(0);
              }}
              onKeyDown={event => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  root.current?.querySelector<HTMLButtonElement>(".lookup-options button")?.focus();
                }
              }}
            />
          </div>
          <div className="lookup-summary" role="status">
            {isPending
              ? "Cargando el catálogo completo…"
              : isError
                ? "Catálogo no disponible"
                : filtered.length
                  ? `Mostrando ${currentPage * PAGE_SIZE + 1}–${Math.min((currentPage + 1) * PAGE_SIZE, filtered.length)} de ${filtered.length} opciones${query.trim() ? ` · ${data.length} en total` : ""}`
                  : query.trim()
                    ? `Sin coincidencias · ${data.length} opciones en total`
                    : "No hay opciones disponibles"}
          </div>
          <div
            ref={optionList}
            className={`lookup-options${filtered.length > PAGE_SIZE ? " lookup-options--paginated" : ""}`}
            onKeyDown={event => {
              if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
              event.preventDefault();
              const buttons = [
                ...event.currentTarget.querySelectorAll<HTMLButtonElement>("button"),
              ];
              const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
              buttons[
                (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length
              ]?.focus();
            }}
          >
            {isError ? (
              <div className="lookup-empty">
                <p>No se pudieron cargar las opciones. No se está mostrando una lista parcial.</p>
                <button type="button" onClick={() => refetch()}>
                  Reintentar
                </button>
              </div>
            ) : isPending ? (
              <p>Espera un momento…</p>
            ) : options.length === 0 ? (
              <p>
                {query.trim()
                  ? "Prueba otro nombre o código."
                  : "No hay registros disponibles para este campo y sus filtros."}
              </p>
            ) : (
              options.map(item => {
                const itemValue = item[config.valueKey] as number | string;
                const active = String(itemValue) === String(value);
                return (
                  <button
                    type="button"
                    aria-pressed={active}
                    className={active ? "is-selected" : ""}
                    key={String(itemValue)}
                    onClick={() => {
                      onChange(itemValue);
                      close();
                    }}
                  >
                    <span>
                      <strong>{label(item)}</strong>
                      {config.secondaryKey && item[config.secondaryKey] != null && (
                        <small>{text(item[config.secondaryKey])}</small>
                      )}
                    </span>
                    {active && <Check aria-hidden="true" />}
                  </button>
                );
              })
            )}
          </div>
          {!isPending && !isError && filtered.length > PAGE_SIZE && (
            <nav
              ref={pagination}
              tabIndex={-1}
              className="lookup-pagination"
              aria-label="Páginas de opciones"
            >
              <button
                type="button"
                aria-label="Opciones anteriores"
                disabled={currentPage === 0}
                onClick={() => changePage(currentPage - 1)}
              >
                <ChevronLeft aria-hidden="true" />
                Anterior
              </button>
              <span>
                {currentPage + 1} / {totalPages}
              </span>
              <button
                type="button"
                aria-label="Opciones siguientes"
                disabled={currentPage === totalPages - 1}
                onClick={() => changePage(currentPage + 1)}
              >
                Siguiente
                <ChevronRight aria-hidden="true" />
              </button>
            </nav>
          )}
        </div>
      )}
    </div>
  );
}
