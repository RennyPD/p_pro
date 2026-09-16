const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function api(path, options = {}) {
  const token = localStorage.getItem("p_pro_token");
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "No fue posible completar la solicitud");
  return payload;
}
