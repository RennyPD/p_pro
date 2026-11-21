import { Check, ChevronDown, Search, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

export type SearchOption = { value: string; label: string; hint?: string };

const normalize = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase();

/**
 * One field to search and choose from a local list (no separate search box that
 * silently filters another select). Typing filters; Enter or click chooses.
 */
export function SearchSelect({
  label,
  options,
  value,
  onChange,
  placeholder = "Escribe para buscar",
  disabled,
  emptyText = "Sin coincidencias",
  required,
}: {
  label: string;
  options: SearchOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  emptyText?: string;
  required?: boolean;
}) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const selected = options.find(option => option.value === value);
  const matches = options.filter(option =>
    normalize(`${option.label} ${option.hint ?? ""}`).includes(normalize(query.trim())),
  );

  useEffect(() => {
    if (!open) return;
    const outside = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", outside);
    return () => document.removeEventListener("mousedown", outside);
  }, [open]);

  function choose(option: SearchOption) {
    onChange(option.value);
    setQuery("");
    setOpen(false);
  }
  function keys(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive(index => Math.min(index + 1, matches.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive(index => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && open && matches[active]) {
      event.preventDefault();
      choose(matches[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  return (
    <div className="form-field search-select" ref={root}>
      <label htmlFor={id}>{label}</label>
      <div className={`search-select__control${disabled ? " is-disabled" : ""}`}>
        <Search size={16} aria-hidden="true" />
        <input
          id={id}
          ref={input}
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={open && matches[active] ? `${id}-${active}` : undefined}
          aria-required={required || undefined}
          disabled={disabled}
          placeholder={selected ? selected.label : placeholder}
          value={open ? query : (selected?.label ?? "")}
          onFocus={() => {
            setOpen(true);
            setActive(0);
          }}
          onChange={event => {
            setQuery(event.target.value);
            setOpen(true);
            setActive(0);
          }}
          onKeyDown={keys}
        />
        {selected && !disabled ? (
          <button
            type="button"
            className="search-select__clear"
            aria-label={`Quitar ${label.toLocaleLowerCase()}`}
            onClick={() => {
              onChange("");
              input.current?.focus();
            }}
          >
            <X size={15} />
          </button>
        ) : (
          <ChevronDown size={16} aria-hidden="true" />
        )}
      </div>
      {open && !disabled && (
        <ul id={`${id}-list`} role="listbox" aria-label={label} className="search-select__list">
          {matches.length ? (
            matches.map((option, index) => (
              <li
                key={option.value}
                id={`${id}-${index}`}
                role="option"
                aria-selected={option.value === value}
                className={index === active ? "is-active" : ""}
                onMouseDown={event => {
                  event.preventDefault();
                  choose(option);
                }}
                onMouseEnter={() => setActive(index)}
              >
                <span>
                  {option.label}
                  {option.hint && <small>{option.hint}</small>}
                </span>
                {option.value === value && <Check size={15} />}
              </li>
            ))
          ) : (
            <li className="search-select__empty">{emptyText}</li>
          )}
        </ul>
      )}
    </div>
  );
}
