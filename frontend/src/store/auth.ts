import { create } from "zustand";
import type { User } from "../types";

interface AuthState { token:string|null; user:User|null; hydrated:boolean; sessionGeneration:number; setSession:(token:string,user:User)=>void; setUser:(user:User)=>void; clearSession:()=>void; hydrate:()=>void }
export const useAuthStore = create<AuthState>((set,get)=>({
  token:sessionStorage.getItem("nexo_access_token"), user:null, hydrated:false, sessionGeneration:0,
  setSession:(token,user)=>{const previous=get();sessionStorage.setItem("nexo_access_token",token);set({token,user,sessionGeneration:previous.sessionGeneration+(!previous.token||(previous.user&&previous.user.user_id!==user.user_id)?1:0)});},
  setUser:(user)=>set({user}),
  clearSession:()=>{sessionStorage.removeItem("nexo_access_token");set(state=>({token:null,user:null,sessionGeneration:state.sessionGeneration+1}));},
  hydrate:()=>set({hydrated:true}),
}));
