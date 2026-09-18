import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { DashboardPage } from "./DashboardPage";

const summary={active_period:"2026-2027",alerts:[],metrics:[]};
const teacher={user_id:2,username:"profesor.01",email:"teacher@example.com",role_id:2,role_name:"teacher" as const,student_id:null,teacher_id:1};
const student={user_id:8,username:"estudiante.001",email:"student@example.com",role_id:3,role_name:"student" as const,student_id:1,teacher_id:null};

describe("DashboardPage session isolation",()=>{
  afterEach(()=>vi.restoreAllMocks());
  it("does not reuse a teacher schedule when a student with the same profile id signs in",async()=>{
    const get=vi.spyOn(api,"get").mockImplementation(async(url)=>({data:url==="/dashboard/summary"?summary:[]} as never));
    const client=new QueryClient({defaultOptions:{queries:{staleTime:30_000,retry:false}}});
    useAuthStore.setState({user:teacher,token:"teacher-token"});
    const first=render(<QueryClientProvider client={client}><MemoryRouter><DashboardPage/></MemoryRouter></QueryClientProvider>);
    await waitFor(()=>expect(get).toHaveBeenCalledWith("/academic/teachers/1/schedule"));
    first.unmount();

    useAuthStore.setState({user:student,token:"student-token"});
    render(<QueryClientProvider client={client}><MemoryRouter><DashboardPage/></MemoryRouter></QueryClientProvider>);
    await waitFor(()=>expect(get).toHaveBeenCalledWith("/academic/students/1/schedule"));
  });
});
