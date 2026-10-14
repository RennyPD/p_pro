import { X } from "lucide-react";
import { useEffect, useId, useRef, type ButtonHTMLAttributes, type PropsWithChildren, type ReactNode } from "react";
import clsx from "clsx";

export function Button({className,variant="primary",...props}:ButtonHTMLAttributes<HTMLButtonElement>&{variant?:"primary"|"secondary"|"ghost"|"danger"}){return <button className={clsx("button",`button--${variant}`,className)} {...props}/>;}
export function Badge({children,tone="neutral"}:PropsWithChildren<{tone?:"neutral"|"success"|"warning"|"danger"|"info"}>){return <span className={`badge badge--${tone}`}>{children}</span>;}
export function EmptyState({icon,title,description,action}:{icon:ReactNode;title:string;description:string;action?:ReactNode}){return <div className="empty-state"><div className="empty-state__icon">{icon}</div><h3>{title}</h3><p>{description}</p>{action}</div>;}
export function Spinner({label="Cargando"}:{label?:string}){return <div className="spinner-wrap" role="status"><span className="spinner"/><span>{label}</span></div>;}
export function Modal({title,description,onClose,children}:{title:string;description?:string;onClose:()=>void;children:ReactNode}){
  const titleId=useId(), descriptionId=useId();
  const dialog=useRef<HTMLElement>(null);
  const close=useRef(onClose);
  useEffect(()=>{close.current=onClose;},[onClose]);
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement|null;
    const overflow=document.body.style.overflow;
    document.body.style.overflow="hidden";
    dialog.current?.focus();
    const handleKey=(event:KeyboardEvent)=>{
      if(event.key==="Escape"){event.preventDefault();close.current();}
      if(event.key!=="Tab")return;
      const focusable=Array.from(dialog.current?.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex="0"]')??[]).filter(el=>!el.closest('[hidden],[inert]')&&el.getClientRects().length>0);
      const first=focusable[0],last=focusable.at(-1);
      if(!first){event.preventDefault();dialog.current?.focus();return;}
      if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current)){event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===dialog.current)){event.preventDefault();first.focus();}
    };
    document.addEventListener("keydown",handleKey);
    return()=>{document.body.style.overflow=overflow;document.removeEventListener("keydown",handleKey);previous?.focus();};
  },[]);
  return <div className="modal-backdrop" role="presentation" onMouseDown={event=>event.target===event.currentTarget&&onClose()}><section ref={dialog} tabIndex={-1} className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={description?descriptionId:undefined}><header className="modal__header"><div><h2 id={titleId}>{title}</h2>{description&&<p id={descriptionId}>{description}</p>}</div><button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar"><X size={20}/></button></header><div className="modal__body">{children}</div></section></div>;
}
