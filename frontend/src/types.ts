export type Role = "admin" | "teacher" | "student" | "guardian";

export interface User { user_id:number; username:string; email:string; role_id:number; role_name:Role; student_id:number|null; teacher_id:number|null; guardian_id?:number|null }
export interface TokenResponse { access_token:string; token_type:string; user:User }
export type RecordValue = string | number | boolean | null | string[];
export type EntityRecord = Record<string, RecordValue>;
export interface LookupConfig { endpoint:string; valueKey:string; labelKeys:string[]; secondaryKey?:string; placeholder?:string }
export interface FieldConfig {
  name:string; label:string;
  type?:"text"|"email"|"password"|"number"|"date"|"time"|"checkbox"|"select"|"multiselect"|"lookup"|"days";
  required?:boolean; placeholder?:string;
  options?:{label:string;value:string|number}[];
  lookup?:LookupConfig;
}
export interface ResourceConfig { key:string; title:string; singular:string; description:string; endpoint:string; idField:string; searchPlaceholder:string; columns:{key:string;label:string;render?:(value:RecordValue,row:EntityRecord)=>string}[]; fields:FieldConfig[]; allowDelete?:boolean }
