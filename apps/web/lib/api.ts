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

export interface ShotFrame {
  id: string;
  image_url: string;
  alt_text: string;
  generated_at: string;
}

export interface Shot {
  id: string;
  shot_number: number;
  characters: string[];
  location: string;
  time_of_day: string;
  action_summary: string;
  suggested_camera: string;
  dialogue_snippet: string | null;
  needs_review: boolean;
  frame: ShotFrame | null;
}

export interface Scene {
  id: string;
  scene_number: number;
  heading: string;
  time_of_day: string;
  needs_review: boolean;
  shots: Shot[];
}

export interface PrevisCustomization {
  title: string;
  accent_color: string;
  tone_note: string;
}

export interface ProjectDetail extends Project {
  scenes: Scene[];
  deployed_app_url: string | null;
  previs_customization: PrevisCustomization | null;
}

export interface JobStep {
  agent: string;
  status: string;
  at: string | null;
  completed: number | null;
  total: number | null;
  failed: number | null;
}

export interface Job {
  id: string;
  status: string;
  steps: JobStep[];
  deployed_app_url: string | null;
  error_detail: string | null;
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
    return request<{ id: string; job_id: string | null }>(`/api/v1/projects/${projectId}/scripts`, {
      method: "POST",
      body: form,
    });
  },

  getProject: (projectId: string) => request<ProjectDetail>(`/api/v1/projects/${projectId}`),

  getJob: (jobId: string) => request<Job>(`/api/v1/jobs/${jobId}`),

  iterate: (projectId: string, iterationRequest: string) =>
    request<{ job_id: string }>(`/api/v1/projects/${projectId}/iterate`, {
      method: "POST",
      body: JSON.stringify({ request: iterationRequest }),
    }),
};
