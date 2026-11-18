// Types generated from the backend's OpenAPI schema (npm run api:types).
// Use ApiSchema<"Name"> instead of writing API payload types by hand.
import type { components } from "./api-schema";

export type ApiSchemas = components["schemas"];
export type ApiSchema<Name extends keyof ApiSchemas> = ApiSchemas[Name];
