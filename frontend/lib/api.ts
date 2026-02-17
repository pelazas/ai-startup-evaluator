const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
let tokenGetter: (() => string | null) | null = null;

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

export function setAuthTokenGetter(getter: () => string | null): void {
  tokenGetter = getter;
}

function getToken(): string | null {
  return tokenGetter ? tokenGetter() : null;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    const fallback = `Request failed (${response.status})`;
    try {
      const json = (await response.json()) as { detail?: string };
      throw new Error(json.detail ?? fallback);
    } catch {
      throw new Error(fallback);
    }
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: async <T>(path: string, options: Omit<RequestOptions, "body" | "method"> = {}) => {
    const data = await apiRequest<T>(path, { ...options, method: "GET" });
    return { data };
  },
  post: async <T>(path: string, body?: unknown, options: Omit<RequestOptions, "body" | "method"> = {}) => {
    const data = await apiRequest<T>(path, { ...options, method: "POST", body });
    return { data };
  },
  put: async <T>(path: string, body?: unknown, options: Omit<RequestOptions, "body" | "method"> = {}) => {
    const data = await apiRequest<T>(path, { ...options, method: "PUT", body });
    return { data };
  },
};
