const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("scenecraft_token") : null;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.error ?? { code: "UNKNOWN_ERROR", message: "Something went wrong." };
    throw new ApiError(detail.code, detail.message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface Project {
  id: string;
  title: string;
  style_reference: string | null;
  created_at: string;
  updated_at: string;
}

export const api = {
  signup: (email: string, password: string) =>
    request<{ id: string; email: string }>("/api/v1/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  listProjects: () => request<{ projects: Project[] }>("/api/v1/projects"),

  createProject: (title: string, styleReference?: string) =>
    request<Project>("/api/v1/projects", {
      method: "POST",
      body: JSON.stringify({ title, style_reference: styleReference ?? null }),
    }),

  uploadScript: (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/api/v1/projects/${projectId}/scripts`, {
      method: "POST",
      body: form,
    });
  },
};
