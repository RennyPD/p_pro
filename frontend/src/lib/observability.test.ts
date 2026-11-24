import type { ErrorEvent } from "@sentry/react";
import { describe, expect, it } from "vitest";
import { initErrorTracking, mask, scrub } from "./observability";

describe("error tracking", () => {
  it("masks emails, long numbers and tokens", () => {
    expect(mask("Fallo para ana@correo.do, cédula 001-1234567-8, token=abc")).toBe(
      "Fallo para [correo], cédula [número], token [oculto]",
    );
  });

  it("keeps the error and drops personal data", () => {
    const event = {
      type: undefined,
      request: { url: "https://colegio.nexo.do/students/5?q=ana#x", data: "cuerpo" },
      user: { id: "5", email: "ana@correo.do" },
      breadcrumbs: [{ message: "click" }],
      extra: { form: "datos" },
      message: "Error con ana@correo.do",
      exception: { values: [{ type: "Error", value: "No se guardó 8095551234" }] },
    } as unknown as ErrorEvent;
    const clean = scrub(event);
    expect(clean.request).toEqual({ url: "https://colegio.nexo.do/students/5" });
    expect(clean.user).toBeUndefined();
    expect(clean.breadcrumbs).toBeUndefined();
    expect(clean.extra).toBeUndefined();
    expect(clean.message).toBe("Error con [correo]");
    expect(clean.exception?.values?.[0].value).toBe("No se guardó [número]");
  });

  it("stays off without a DSN", async () => {
    expect(await initErrorTracking("")).toBe(false);
  });
});
