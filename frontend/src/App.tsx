import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { resources } from "./config/resources";
import { MyAttendancePage, MyGradesPage, MyProgressPage, MySchedulePage, SectionWorkspacePage, StudentProfilePage } from "./features/academic/AcademicPages";
import { LoginPage } from "./features/auth/LoginPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { ResourcePage } from "./features/resources/ResourcePage";
import { AccountPage } from "./features/settings/AccountPage";
import { InstitutionSettingsPage } from "./features/settings/InstitutionSettingsPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { api } from "./lib/api";
import { useAuthStore } from "./store/auth";
import type { Role, User } from "./types";

function SessionGate(){const{token,user,setUser,clearSession,hydrate}=useAuthStore();const query=useQuery({queryKey:["session"],queryFn:()=>api.get<User>("/auth/me").then(r=>r.data),enabled:Boolean(token&&!user),retry:false});useEffect(()=>{if(query.data)setUser(query.data);if(query.isError)clearSession();if(!token||query.isSuccess||query.isError||user)hydrate();},[query.data,query.isError,query.isSuccess,token,user,setUser,clearSession,hydrate]);if(token&&!user&&!query.isError)return <div className="app-loader"><span className="brand-symbol">N</span><p>Preparando tu espacio…</p></div>;return <Outlet/>}
function Protected(){const{token,user,hydrated}=useAuthStore();if(!hydrated)return null;if(!token||!user)return <Navigate to="/login" replace/>;return <AppShell/>}
function RoleRoute({roles}:{roles:Role[]}){const role=useAuthStore(s=>s.user?.role_name);return role&&roles.includes(role)?<Outlet/>:<Navigate to="/" replace/>}
export default function App(){return <Routes><Route element={<SessionGate/>}><Route path="/login" element={<LoginPage/>}/><Route element={<Protected/>}><Route index element={<DashboardPage/>}/><Route path="account" element={<AccountPage/>}/><Route path="my-grades" element={<MyGradesPage/>}/><Route path="my-schedule" element={<MySchedulePage/>}/><Route path="my-attendance" element={<MyAttendancePage/>}/><Route path="my-progress" element={<MyProgressPage/>}/><Route element={<RoleRoute roles={["admin","teacher"]}/>}>{["students","sections","enrollments","grades","attendances"].map(key=><Route key={key} path={key} element={<ResourcePage config={resources[key]}/>}/>)}<Route path="students/:studentId" element={<StudentProfilePage/>}/><Route path="sections/:sectionId" element={<SectionWorkspacePage/>}/></Route><Route element={<RoleRoute roles={["admin"]}/>}>{["teachers","subjects","careers","roles","users","periods","curriculum"].map(key=><Route key={key} path={key} element={<ResourcePage config={resources[key]}/>}/>) }<Route path="settings" element={<SettingsPage/>}/><Route path="settings/institution" element={<InstitutionSettingsPage/>}/></Route><Route path="*" element={<Navigate to="/" replace/>}/></Route></Route></Routes>}
