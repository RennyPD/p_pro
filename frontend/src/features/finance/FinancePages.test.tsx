import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { FinancePage } from "./FinancePages";

describe("FinancePage",()=>{afterEach(()=>vi.restoreAllMocks());it("shows a student's internal balance and history",async()=>{useAuthStore.setState({user:{user_id:3,username:"demo.estudiante",email:"student@example.com",role_id:3,role_name:"student",student_id:7,teacher_id:null}});vi.spyOn(api,"get").mockResolvedValue({data:{student_id:7,enrollment_number:"EST-2026-0001",student_name:"Daniel Santos",cutoff_day:15,due_day:30,total_charges:15000,total_payments:5000,balance:10000,overdue_balance:10000,transactions:[{transaction_id:1,type:"charge",description:"Matrícula",amount:15000,date:"2026-09-01T08:00:00",due_date:"2026-09-15"}]}} as never);render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><FinancePage/></MemoryRouter></QueryClientProvider>);expect(await screen.findByRole("heading",{name:"Daniel Santos"})).toBeInTheDocument();expect(screen.getByText("Balance pendiente")).toBeInTheDocument();expect(screen.getByText("Matrícula")).toBeInTheDocument();});});
