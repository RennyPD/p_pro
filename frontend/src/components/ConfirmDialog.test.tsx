import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { confirmAction } from "../lib/confirm";
import { ConfirmHost } from "./ConfirmDialog";
import { Modal } from "./ui";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("resolves true when the user confirms and never opens the native dialog", async () => {
  const native = vi.spyOn(window, "confirm");
  render(<ConfirmHost />);
  let answer: Promise<boolean> | undefined;
  act(() => {
    answer = confirmAction("¿Eliminar el aula?", { confirmLabel: "Eliminar", tone: "danger" });
  });
  const dialog = await screen.findByRole("alertdialog", { name: "Confirmar acción" });
  expect(dialog).toHaveTextContent("¿Eliminar el aula?");
  expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Eliminar" }));
  await expect(answer).resolves.toBe(true);
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(native).not.toHaveBeenCalled();
});

it("resolves false on cancel", async () => {
  render(<ConfirmHost />);
  let answer: Promise<boolean> | undefined;
  act(() => {
    answer = confirmAction("¿Descartar?");
  });
  fireEvent.click(await screen.findByRole("button", { name: "Cancelar" }));
  await expect(answer).resolves.toBe(false);
});

it("closes only itself with Escape when opened over a modal", async () => {
  const closeModal = vi.fn();
  render(
    <>
      <Modal title="Editar" onClose={closeModal}>
        <p>Formulario</p>
      </Modal>
      <ConfirmHost />
    </>,
  );
  let answer: Promise<boolean> | undefined;
  act(() => {
    answer = confirmAction("¿Descartar los cambios?");
  });
  await screen.findByRole("alertdialog");
  fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });
  await expect(answer).resolves.toBe(false);
  expect(closeModal).not.toHaveBeenCalled();
  expect(screen.getByRole("dialog", { name: "Editar" })).toBeInTheDocument();
});

it("falls back to the browser dialog when no host is mounted", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  await expect(confirmAction("¿Continuar?")).resolves.toBe(true);
});
