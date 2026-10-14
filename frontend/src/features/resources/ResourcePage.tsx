import { flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ChevronLeft, ChevronRight, Edit3, Eye, Plus, Search, Trash2, X } from "lucide-react";
import { Fragment, useId, useMemo, useState, type ReactNode } from "react";
import { Controller, useForm, type Control } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button, EmptyState, Modal, Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import type { EntityRecord, FieldConfig, LookupConfig, ResourceConfig } from "../../types";
import "./resource-fields.css";
import "./resource-table.css";

const PAGE_SIZE=10;
const WEEK_DAYS=["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"];
type FormValues=Record<string,unknown>;

export function ResourcePage({config,rowActions,toolbarContent,queryParams={}}:{config:ResourceConfig;rowActions?:(row:EntityRecord)=>ReactNode;toolbarContent?:ReactNode;queryParams?:Record<string,string|number>}){
  const user=useAuthStore(s=>s.user);
  const navigate=useNavigate();
  const client=useQueryClient();
  const[search,setSearch]=useState("");
  const[page,setPage]=useState(0);
  const[editing,setEditing]=useState<EntityRecord|null|undefined>();
  const canWrite=user?.role_name==="admin"||(user?.role_name==="teacher"&&["grades","attendances"].includes(config.key));
  const{data=[],isLoading,isFetching,error}=useQuery({
    queryKey:[config.key,user?.user_id,user?.role_name,page,search,queryParams],
    queryFn:async()=>{const params:Record<string,string|number>={...queryParams,skip:page*PAGE_SIZE,limit:PAGE_SIZE};if(search){if(config.key==="grades")params.grade_type=search;else if(config.key==="enrollments")params.period=search;else if(config.key==="attendances")params.enrollment_id=Number(search)||0;else params.q=search;}return api.get(config.endpoint,{params}).then(r=>r.data as EntityRecord[]);},
    placeholderData:keepPreviousData,
  });
  const remove=useMutation({mutationFn:(row:EntityRecord)=>api.delete(`${config.endpoint}${row[config.idField]}`),onSuccess:()=>{toast.success(`${capitalize(config.singular)} eliminado correctamente`);client.invalidateQueries({queryKey:[config.key]});},onError:(e)=>toast.error(apiMessage(e))});
  const hasWorkspace=["students","sections","careers","subjects"].includes(config.key);
  const columns=useMemo(()=>[...config.columns.map(c=>({accessorKey:c.key,header:c.label,cell:({row,getValue}:{row:{original:EntityRecord};getValue:()=>unknown})=>c.render?c.render(getValue() as never,row.original):display(getValue())})),...((canWrite||hasWorkspace)?[{id:"actions",header:"",cell:({row}:{row:{original:EntityRecord}})=><div className="row-actions">{canWrite&&rowActions?.(row.original)}{hasWorkspace&&<button onClick={()=>navigate(`/${config.key}/${row.original[config.idField]}`)} aria-label={`Abrir ${config.singular}`}><Eye/></button>}{canWrite&&<button onClick={()=>setEditing(row.original)} aria-label={`Editar ${config.singular}`}><Edit3/></button>}{canWrite&&config.allowDelete!==false&&<button className="danger" onClick={()=>confirm(`¿Eliminar este ${config.singular}?`)&&remove.mutate(row.original)} aria-label={`Eliminar ${config.singular}`}><Trash2/></button>}</div>}]:[])],[config,canWrite,hasWorkspace,navigate,remove,rowActions]);
  const table=useReactTable({data,columns,getCoreRowModel:getCoreRowModel()});
  const columnClass=(id:string,index:number)=>id==="actions"?"table-actions":index>=4?"table-detail":"table-primary";
  const columnLabel=(id:string)=>config.columns.find(column=>column.key===id)?.label??"Acciones";
  return <div className="page"><header className="page-header"><div><span className="kicker">Gestión académica</span><h1>{config.title}</h1><details className="header-help"><summary>Acerca de esta vista</summary><p>{config.description}</p></details></div>{canWrite&&<Button onClick={()=>setEditing(null)}><Plus size={18}/> Nuevo {config.singular}</Button>}</header><section className="resource-toolbar"><div className="search-box"><Search/><input value={search} onChange={e=>{setSearch(e.target.value);setPage(0)}} placeholder={config.searchPlaceholder}/>{isFetching&&<span className="mini-spinner"/>}</div>{toolbarContent}<span className="result-note">Página {page+1}</span></section><section className="table-panel resource-table-panel">{isLoading?<Spinner label={`Cargando ${config.title.toLowerCase()}`}/>:error?<EmptyState icon={<Search/>} title="No pudimos cargar los datos" description={apiMessage(error)}/>:data.length===0?<EmptyState icon={<Search/>} title={`Aún no hay ${config.title.toLowerCase()}`} description={search?"Prueba con otro término de búsqueda.":`Crea el primer ${config.singular} para comenzar.`} action={canWrite&&!search?<Button onClick={()=>setEditing(null)}><Plus size={17}/> Crear ahora</Button>:undefined}/>:<div className="table-scroll resource-table-scroll"><table className="resource-table"><thead>{table.getHeaderGroups().map(group=><tr key={group.id}>{group.headers.map((header,index)=><th className={columnClass(header.column.id,index)} key={header.id}>{flexRender(header.column.columnDef.header,header.getContext())}</th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.map(row=><tr key={row.id}>{row.getVisibleCells().map((cell,index)=><td className={columnClass(cell.column.id,index)} data-label={columnLabel(cell.column.id)} key={cell.id}>{flexRender(cell.column.columnDef.cell,cell.getContext())}</td>)}</tr>)}</tbody></table></div>}</section><footer className="pagination"><Button variant="secondary" disabled={page===0} onClick={()=>setPage(p=>p-1)}><ChevronLeft/> Anterior</Button><Button variant="secondary" disabled={data.length<PAGE_SIZE} onClick={()=>setPage(p=>p+1)}>Siguiente <ChevronRight/></Button></footer>{editing!==undefined&&<ResourceForm config={config} record={editing} onClose={()=>setEditing(undefined)}/>}</div>;
}

export function ResourceForm({config,record,onClose,initialValues}:{config:ResourceConfig;record:EntityRecord|null;onClose:()=>void;initialValues?:EntityRecord}){
  const client=useQueryClient();
  const defaults=record??initialValues??config.defaultValues??Object.fromEntries(config.fields.filter(f=>f.type==="checkbox").map(f=>[f.name,!f.name.endsWith("_hold")]));
  const{register,control,handleSubmit,formState:{isSubmitting}}=useForm<FormValues>({defaultValues:defaults});
  const mutation=useMutation({
    mutationFn:(values:FormValues)=>{const entries=Object.entries(values).map(([key,value])=>{const field=config.fields.find(item=>item.name===key);const clearable=["students","teachers","careers","curriculum"].includes(config.key)&&field&&!field.required&&field.type!=="checkbox"&&key!=="enrollment_number";return [key,clearable&&(value===""||value===undefined)?null:value] as const;});const payload=Object.fromEntries(entries.filter(([key,value])=>config.fields.some(field=>field.name===key)&&(value!==""&&value!==undefined&&(value!==null||["students","teachers","careers","curriculum"].includes(config.key)))).map(([key,value])=>[key,config.fields.find(field=>field.name===key)?.type==="number"&&value!==null?Number(value):value]));return record?api.patch(`${config.endpoint}${record[config.idField]}`,payload):api.post(config.endpoint,payload);},
    onSuccess:()=>{toast.success(record?"Cambios guardados":"Registro creado");client.invalidateQueries({queryKey:[config.key]});if(config.key==="students")client.invalidateQueries({queryKey:["student-profile"]});if(config.key==="teachers"){client.invalidateQueries({queryKey:["teacher-profile"]});client.invalidateQueries({queryKey:["teacher-departments"]});}if(config.key==="careers"){client.invalidateQueries({queryKey:["career"]});client.invalidateQueries({queryKey:["career-catalog-options"]});}if(["careers","curriculum"].includes(config.key)){client.invalidateQueries({queryKey:["career-curriculum"]});client.invalidateQueries({queryKey:["career-overview"]});}onClose();},
    onError:error=>toast.error(apiMessage(error)),
  });
  return <Modal title={record?`Editar ${config.singular}`:`Nuevo ${config.singular}`} description="Completa los datos esenciales. Podrás ajustarlos más adelante." onClose={onClose}><form className="resource-form" onSubmit={handleSubmit(values=>mutation.mutateAsync(values))}>{config.fields.map((field,index)=><Fragment key={field.name}>{field.section&&field.section!==config.fields[index-1]?.section&&<h3 className="form-section-heading">{field.section}</h3>}<FormField field={field} control={control} register={register}/></Fragment>) }<div className="form-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={isSubmitting||mutation.isPending}>{mutation.isPending?"Guardando…":"Guardar"}</Button></div></form></Modal>;
}

function FormField({field,control,register}:{field:FieldConfig;control:Control<FormValues>;register:ReturnType<typeof useForm<FormValues>>["register"]}){
  const hintId=useId();
  const hint=field.placeholder && field.placeholder.length>32 ? field.placeholder : undefined;
  if(field.type==="hidden")return <input type="hidden" {...register(field.name)}/>;
  if(field.type==="textarea")return <label className="form-field career-long-field"><FieldLabel field={field}/><textarea rows={4} placeholder={field.placeholder} {...register(field.name,{required:field.required})}/></label>;
  if(field.type==="checkbox")return <label className="check-field"><input type="checkbox" {...register(field.name)}/><span>{field.label}</span></label>;
  if(field.type==="lookup"&&field.lookup)return <label className="form-field"><FieldLabel field={field}/><Controller name={field.name} control={control} rules={{required:field.required}} render={({field:input})=><LookupField config={field.lookup!} value={input.value as number|string|null|undefined} onChange={input.onChange}/>} /></label>;
  if(field.type==="days")return <fieldset className="form-field day-field"><legend><FieldLabel field={field}/></legend><Controller name={field.name} control={control} rules={{required:field.required}} render={({field:input})=><DayPicker value={normalizeDays(input.value)} onChange={input.onChange}/>} /></fieldset>;
  if(field.type==="select")return <label className="form-field"><FieldLabel field={field}/><select {...register(field.name,{required:field.required})}><option value="">Selecciona una opción</option>{field.options?.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}</select></label>;
  return <label className="form-field"><FieldLabel field={field}/><input type={field.type??"text"} aria-describedby={hint?hintId:undefined} placeholder={hint?undefined:field.placeholder} step={field.name==="grade_value"?"0.01":field.name==="credits"?"any":undefined} {...register(field.name,{required:field.required})}/>{hint&&<span id={hintId} className="field-hint">{hint}</span>}</label>;
}

function FieldLabel({field}:{field:FieldConfig}){return <span>{field.label}{field.required&&<b> *</b>}</span>}

function LookupField({config,value,onChange}:{config:LookupConfig;value:number|string|null|undefined;onChange:(value:number|string|null)=>void}){
  const user=useAuthStore(s=>s.user);
  const[open,setOpen]=useState(false);
  const[query,setQuery]=useState("");
  const{data=[],isLoading,isError}=useQuery({queryKey:["lookup",config.endpoint,user?.user_id,user?.role_name],queryFn:()=>api.get(config.endpoint,{params:{limit:100}}).then(response=>response.data as EntityRecord[])});
  const selected=data.find(item=>String(item[config.valueKey])===String(value));
  const filtered=data.filter(item=>lookupText(item,config).toLocaleLowerCase().includes(query.toLocaleLowerCase())).slice(0,8);
  return <div className="lookup-field">
    <button type="button" className="lookup-trigger" aria-expanded={open} onClick={()=>setOpen(current=>!current)}><span className={selected?"":"muted"}>{selected?lookupText(selected,config):isLoading?"Cargando opciones…":config.placeholder??"Selecciona una opción"}</span><ChevronDown/></button>
    {value!==undefined&&value!==null&&value!==""&&<button type="button" className="lookup-clear" aria-label="Limpiar selección" onClick={()=>onChange(null)}><X/></button>}
    {open&&<div className="lookup-popover"><div className="lookup-search"><Search/><input autoFocus value={query} onChange={event=>setQuery(event.target.value)} placeholder={config.placeholder??"Buscar"}/></div><div className="lookup-options">{isError?<p>No se pudieron cargar las opciones.</p>:filtered.length===0?<p>{isLoading?"Cargando…":"No hay coincidencias."}</p>:filtered.map(item=>{const itemValue=item[config.valueKey] as number|string;const active=String(itemValue)===String(value);return <button type="button" className={active?"is-selected":""} key={String(itemValue)} onClick={()=>{onChange(itemValue);setOpen(false);setQuery("")}}><span><strong>{lookupText(item,config)}</strong>{config.secondaryKey&&item[config.secondaryKey]!==null&&<small>{displayText(item[config.secondaryKey])}</small>}</span>{active&&<Check/>}</button>})}</div></div>}
  </div>;
}

function DayPicker({value,onChange}:{value:string[];onChange:(value:string[])=>void}){return <div className="day-picker">{WEEK_DAYS.map(day=>{const active=value.includes(day);return <button type="button" aria-pressed={active} className={active?"is-selected":""} key={day} onClick={()=>onChange(active?value.filter(item=>item!==day):WEEK_DAYS.filter(item=>item===day||value.includes(item)))}>{active&&<Check/>}{day.slice(0,3)}</button>})}</div>}
function normalizeDays(value:unknown){if(Array.isArray(value))return value.map(String);if(typeof value==="string")return value.split(",").map(day=>day.trim()).filter(Boolean);return []}
function lookupText(item:EntityRecord,config:LookupConfig){return config.labelKeys.map(key=>displayText(item[key])).filter(Boolean).join(" · ")}
function displayText(value:unknown){if(Array.isArray(value))return value.join(", ");return value===null||value===undefined?"":String(value)}
function display(value:unknown){if(value===null||value===undefined||value==="")return <span className="muted">—</span>;if(typeof value==="boolean")return <span className={`status-dot ${value?"status-dot--on":""}`}>{value?"Activo":"Inactivo"}</span>;if(Array.isArray(value))return value.join(", ");return String(value)}
function capitalize(value:string){return value.charAt(0).toUpperCase()+value.slice(1)}
