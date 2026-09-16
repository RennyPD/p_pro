import axios, { AxiosError } from "axios";
import { useAuthStore } from "../store/auth";

export const api=axios.create({baseURL:import.meta.env.VITE_API_URL||"http://127.0.0.1:8000",withCredentials:true,headers:{"Content-Type":"application/json"}});
api.interceptors.request.use((config)=>{const token=useAuthStore.getState().token;if(token)config.headers.Authorization=`Bearer ${token}`;return config;});
api.interceptors.response.use((response)=>response,async(error:AxiosError)=>{
  const request=error.config as (typeof error.config&{_retried?:boolean});
  if(error.response?.status===401&&request&&!request._retried&&!request.url?.includes("/auth/login")){
    request._retried=true;
    try{const{data}=await axios.post(`${api.defaults.baseURL}/auth/refresh`,{},{withCredentials:true});useAuthStore.getState().setSession(data.access_token,data.user);request.headers.Authorization=`Bearer ${data.access_token}`;return api(request);}catch{useAuthStore.getState().clearSession();}
  }
  return Promise.reject(error);
});
export function apiMessage(error:unknown):string{if(axios.isAxiosError(error)){const detail=error.response?.data?.detail;if(Array.isArray(detail))return detail.map((item)=>item.msg).join(". ");if(typeof detail==="string")return detail;}return"No pudimos completar la operación. Inténtalo de nuevo.";}
