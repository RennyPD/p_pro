import { zodResolver } from "@hookform/resolvers/zod";
import { KeyRound } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";

const schema=z.object({current_password:z.string().min(8),new_password:z.string().min(10,"Usa al menos 10 caracteres"),confirm:z.string()}).refine(v=>v.new_password===v.confirm,{path:["confirm"],message:"Las contraseñas no coinciden"});
type Values=z.infer<typeof schema>;
export function AccountPage(){const{register,handleSubmit,reset,formState:{errors,isSubmitting}}=useForm<Values>({resolver:zodResolver(schema)});async function submit({confirm:_,...values}:Values){try{await api.post("/auth/change-password",values);toast.success("Contraseña actualizada");reset();}catch(error){toast.error(apiMessage(error));}}return <div className="page"><header className="page-header"><div><span className="kicker">Seguridad</span><h1>Mi cuenta</h1><p>Mantén tus credenciales privadas y actualizadas.</p></div></header><section className="account-card"><span className="account-icon"><KeyRound/></span><form onSubmit={handleSubmit(submit)}><label className="form-field"><span>Contraseña actual</span><input type="password" {...register("current_password")}/>{errors.current_password&&<small>{errors.current_password.message}</small>}</label><label className="form-field"><span>Nueva contraseña</span><input type="password" {...register("new_password")}/>{errors.new_password&&<small>{errors.new_password.message}</small>}</label><label className="form-field"><span>Confirmar contraseña</span><input type="password" {...register("confirm")}/>{errors.confirm&&<small>{errors.confirm.message}</small>}</label><Button disabled={isSubmitting}>{isSubmitting?"Actualizando…":"Actualizar contraseña"}</Button></form></section></div>}
