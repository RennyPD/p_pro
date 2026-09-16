import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "../../store/auth";
import { LoginPage } from "./LoginPage";

describe("LoginPage",()=>{beforeEach(()=>useAuthStore.getState().clearSession());it("presents a clear institutional sign-in form",()=>{render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><LoginPage/></MemoryRouter></QueryClientProvider>);expect(screen.getByRole("heading",{name:"Qué bueno verte"})).toBeInTheDocument();expect(screen.getByLabelText("Usuario o correo")).toBeInTheDocument();expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();expect(screen.getByRole("button",{name:"Entrar a Nexo"})).toBeInTheDocument();});});
