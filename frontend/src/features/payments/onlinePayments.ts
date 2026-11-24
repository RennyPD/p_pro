import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";

export type OnlineStudent = { student_id: number; name: string; balance: string };
export type OnlineOptions = {
  enabled: boolean;
  gateway: string | null;
  min_amount: string;
  students: OnlineStudent[];
};
export type GatewayRedirect = { method: string; url: string; fields: Record<string, string> };
export type OnlineIntent = {
  id: string;
  status: string;
  amount: string;
  currency: string;
  gateway: string;
  authorization_code: string | null;
  message: string | null;
  receipts: string[];
};

export function useOnlineOptions() {
  return useQuery({
    queryKey: ["payments", "online-options"],
    queryFn: () => api.get<OnlineOptions>("/online-payments/options").then(r => r.data),
    retry: false,
  });
}

/** Send the browser to the bank's page: a link, or a form posted for it. */
export function goToGateway(redirect: GatewayRedirect) {
  if (redirect.method === "GET") {
    const query = new URLSearchParams(redirect.fields).toString();
    window.location.assign(query ? `${redirect.url}?${query}` : redirect.url);
    return;
  }
  const form = document.createElement("form");
  form.method = "POST";
  form.action = redirect.url;
  for (const [name, value] of Object.entries(redirect.fields)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
}
