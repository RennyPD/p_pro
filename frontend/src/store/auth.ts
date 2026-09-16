import { create } from "zustand";
import type { User } from "../types";

interface AuthState { token:string|null; user:User|null; hydrated:boolean; setSession:(token:string,user:User)=>void; setUser:(user:User)=>void; clearSession:()=>void; hydrate:()=>void }
export const useAuthStore = create<AuthState>((set)=>({
  token:sessionStorage.getItem("nexo_access_token"), user:null, hydrated:false,
  setSession:(token,user)=>{sessionStorage.setItem("nexo_access_token",token);set({token,user});},
  setUser:(user)=>set({user}),
  clearSession:()=>{sessionStorage.removeItem("nexo_access_token");set({token:null,user:null});},
  hydrate:()=>set({hydrated:true}),
}));
