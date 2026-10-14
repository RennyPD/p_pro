import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { Modal } from "./ui";

afterEach(()=>{cleanup();vi.restoreAllMocks();});

it("labels dialogs, locks background scrolling and restores focus on Escape",()=>{
  function Example(){const[open,setOpen]=useState(false);return <><button onClick={()=>setOpen(true)}>Crear</button>{open&&<Modal title="Nueva sección" description="Datos académicos" onClose={()=>setOpen(false)}><input aria-label="Nombre"/></Modal>}</>;}
  render(<Example/>);
  const trigger=screen.getByRole("button",{name:"Crear"});trigger.focus();fireEvent.click(trigger);
  expect(screen.getByRole("dialog",{name:"Nueva sección"})).toHaveFocus();
  expect(screen.getByRole("dialog")).toHaveAccessibleDescription("Datos académicos");
  expect(document.body.style.overflow).toBe("hidden");
  fireEvent.keyDown(document,{key:"Escape"});
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();expect(document.body.style.overflow).not.toBe("hidden");
});

it("keeps keyboard focus inside the dialog and does not close for interior clicks",()=>{
  vi.spyOn(HTMLElement.prototype,"getClientRects").mockReturnValue([{width:10,height:10}] as unknown as DOMRectList);
  const close=vi.fn();
  render(<Modal title="Formulario" onClose={close}><input aria-label="Nombre"/><button>Guardar</button></Modal>);
  const first=screen.getByRole("button",{name:"Cerrar"}),last=screen.getByRole("button",{name:"Guardar"});
  last.focus();fireEvent.keyDown(document,{key:"Tab"});expect(first).toHaveFocus();
  fireEvent.keyDown(document,{key:"Tab",shiftKey:true});expect(last).toHaveFocus();
  fireEvent.mouseDown(screen.getByRole("dialog"));expect(close).not.toHaveBeenCalled();
  fireEvent.mouseDown(screen.getByRole("dialog").parentElement!);expect(close).toHaveBeenCalledOnce();
});
