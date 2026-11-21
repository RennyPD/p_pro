import { CalendarDays } from "lucide-react";
import { displayToIso, isoToDisplay } from "../lib/dateText";
import {
  forwardRef,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type InputHTMLAttributes,
} from "react";

/** Inserts the slashes while typing: "18112026" → "18/11/2026". */
const mask = (text: string) => {
  const digits = text.replace(/\D/g, "").slice(0, 8);
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join("/");
};

type Props = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "value" | "defaultValue" | "onChange"
> & {
  value?: string | null;
  defaultValue?: string | null;
  /** Receives "YYYY-MM-DD", or "" when cleared. Incomplete text is not reported. */
  onValueChange?: (iso: string) => void;
  /** Kept for react-hook-form's register(): emits a synthetic event with the ISO value. */
  onChange?: (event: { target: { name?: string; value: string } }) => void;
};

/**
 * Date field that always reads "dd/mm/aaaa", whatever the browser language is.
 * The calendar button opens the browser's native picker; the submitted value
 * (state, FormData or react-hook-form) is always ISO "YYYY-MM-DD".
 */
export const DateInput = forwardRef<HTMLInputElement, Props>(function DateInput(
  {
    value,
    defaultValue,
    onValueChange,
    onChange,
    name,
    min,
    max,
    required,
    disabled,
    className,
    onBlur,
    ...rest
  },
  ref,
) {
  const controlled = value !== undefined;
  const [iso, setIso] = useState(controlled ? (value ?? "") : (defaultValue ?? ""));
  const [text, setText] = useState(isoToDisplay(controlled ? value : defaultValue));
  const [invalid, setInvalid] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!controlled) return;
    setIso(value ?? "");
    setText(current => (displayToIso(current) === (value ?? "") ? current : isoToDisplay(value)));
  }, [controlled, value]);

  // A controlled parent may refuse a change (e.g. "discard unsaved changes?" → cancel).
  useEffect(() => {
    if (!controlled) return;
    const parsed = displayToIso(text);
    if (parsed && parsed !== (value ?? "")) setText(isoToDisplay(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-check after typing or picking
  }, [text, iso]);

  function emit(next: string) {
    setIso(next);
    onValueChange?.(next);
    onChange?.({ target: { name, value: next } });
  }
  function typed(event: ChangeEvent<HTMLInputElement>) {
    const next = mask(event.target.value);
    setText(next);
    const parsed = displayToIso(next);
    const outOfRange = parsed && ((min && parsed < String(min)) || (max && parsed > String(max)));
    setInvalid(Boolean(next.length === 10 && (!parsed || outOfRange)));
    if (!next) emit("");
    else if (parsed && !outOfRange) emit(parsed);
  }
  function picked(event: ChangeEvent<HTMLInputElement>) {
    setText(isoToDisplay(event.target.value));
    setInvalid(false);
    emit(event.target.value);
  }
  function openPicker() {
    const input = picker.current;
    if (!input) return;
    try {
      input.showPicker();
    } catch {
      input.focus();
      input.click();
    }
  }

  return (
    <span className={`date-input ${invalid ? "date-input--invalid" : ""} ${className ?? ""}`}>
      <input
        {...rest}
        ref={ref}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        placeholder="dd/mm/aaaa"
        maxLength={10}
        value={text}
        onChange={typed}
        onBlur={onBlur}
        required={required}
        disabled={disabled}
        aria-invalid={invalid || undefined}
        title={invalid ? "Escribe una fecha válida con el formato dd/mm/aaaa" : rest.title}
      />
      <button
        type="button"
        className="date-input__picker"
        onClick={openPicker}
        disabled={disabled}
        aria-label="Abrir calendario"
        tabIndex={-1}
      >
        <CalendarDays size={17} />
      </button>
      <input
        ref={picker}
        className="date-input__native"
        type="date"
        tabIndex={-1}
        aria-hidden="true"
        value={iso}
        min={min}
        max={max}
        onChange={picked}
        disabled={disabled}
      />
      {name && <input type="hidden" name={name} value={iso} />}
    </span>
  );
});
