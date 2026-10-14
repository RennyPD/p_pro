import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { ResourceConfig } from "../../types";
import { ResourceForm } from "./ResourcePage";

afterEach(cleanup);

it("shows long field instructions outside the input and associates them with the control",()=>{
  const hint="Se genera automáticamente si queda vacía";
  const config:ResourceConfig={key:"sample",title:"Prueba",singular:"registro",endpoint:"/sample/",idField:"id",description:"Prueba",searchPlaceholder:"Buscar",columns:[],fields:[{name:"code",label:"Código",placeholder:hint}]};
  render(<QueryClientProvider client={new QueryClient()}><ResourceForm config={config} record={null} onClose={()=>{}}/></QueryClientProvider>);
  const input=screen.getByRole("textbox");
  expect(input).not.toHaveAttribute("placeholder");
  expect(input).toHaveAccessibleDescription(hint);
  expect(screen.getByText(hint)).toHaveClass("field-hint");
});
