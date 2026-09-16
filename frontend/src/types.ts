export type Role = "admin" | "teacher" | "student";
export interface User { user_id:number; username:string; email:string; role_id:number; role_name:Role; student_id:number|null; teacher_id:number|null }
export interface TokenResponse { access_token:string; token_type:string; user:User }
export type RecordValue = string | number | boolean | null | string[];
export type EntityRecord = Record<string, RecordValue>;
export interface FieldConfig { name:string; label:string; type?:"text"|"email"|"password"|"number"|"date"|"time"|"checkbox"|"select"|"multiselect"; required?:boolean; placeholder?:string; options?:{label:string;value:string|number}[] }
export interface ResourceConfig { key:string; title:string; singular:string; description:string; endpoint:string; idField:string; searchPlaceholder:string; columns:{key:string;label:string;render?:(value:RecordValue,row:EntityRecord)=>string}[]; fields:FieldConfig[]; allowDelete?:boolean }
