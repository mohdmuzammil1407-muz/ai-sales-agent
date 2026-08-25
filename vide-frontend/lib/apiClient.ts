import { clearAdminSession, getToken } from "@/lib/auth";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

function getAuthHeaders(): HeadersInit {
  const token = getToken();

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function parseError(res: Response) {
  const payload = await res.json().catch(() => null);

  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }

  return `API Error: ${res.status}`;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    clearAdminSession();

    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }

    throw new Error("Unauthorized - session expired");
  }

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

function resolveEndpoint(endpoint: string) {
  return endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
}

export async function adminGet<T>(endpoint: string): Promise<T> {
  const res = await fetch(resolveEndpoint(endpoint), {
    method: "GET",
    headers: getAuthHeaders(),
    cache: "no-store",
  });

  return handleResponse<T>(res);
}

export async function adminPost<T>(
  endpoint: string,
  body: unknown
): Promise<T> {
  const res = await fetch(resolveEndpoint(endpoint), {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
  });

  return handleResponse<T>(res);
}

export async function adminPut<T>(
  endpoint: string,
  body: unknown
): Promise<T> {
  const res = await fetch(resolveEndpoint(endpoint), {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
  });

  return handleResponse<T>(res);
}

export async function adminDelete<T>(endpoint: string): Promise<T> {
  const res = await fetch(resolveEndpoint(endpoint), {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  return handleResponse<T>(res);
}
