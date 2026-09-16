import { X } from "lucide-react";
import type { ButtonHTMLAttributes, PropsWithChildren, ReactNode } from "react";
import clsx from "clsx";

export function Button({className,variant="primary",...props}:ButtonHTMLAttributes<HTMLButtonElement>&{variant?:"primary"|"secondary"|"ghost"|"danger"}){return <button className={clsx("button",`button--${variant}`,className)} {...props}/>;}
export function Badge({children,tone="neutral"}:PropsWithChildren<{tone?:"neutral"|"success"|"warning"|"danger"|"info"}>){return <span className={`badge badge--${tone}`}>{children}</span>;}
export function EmptyState({icon,title,description,action}:{icon:ReactNode;title:string;description:string;action?:ReactNode}){return <div className="empty-state"><div className="empty-state__icon">{icon}</div><h3>{title}</h3><p>{description}</p>{action}</div>;}
export function Spinner({label="Cargando"}:{label?:string}){return <div className="spinner-wrap" role="status"><span className="spinner"/><span>{label}</span></div>;}
export function Modal({title,description,onClose,children}:{title:string;description?:string;onClose:()=>void;children:ReactNode}){return <div className="modal-backdrop" role="presentation" onMouseDown={(event)=>event.target===event.currentTarget&&onClose()}><section className="modal" role="dialog" aria-modal="true" aria-label={title}><header className="modal__header"><div><span className="eyebrow">Formulario</span><h2>{title}</h2>{description&&<p>{description}</p>}</div><button className="icon-button" onClick={onClose} aria-label="Cerrar"><X size={20}/></button></header>{children}</section></div>;}
