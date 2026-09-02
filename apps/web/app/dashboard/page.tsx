"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Project } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [title, setTitle] = useState("");
  const [styleReference, setStyleReference] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && !window.localStorage.getItem("scenecraft_token")) {
      router.push("/");
      return;
    }
    refreshProjects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refreshProjects() {
    try {
      const { projects } = await api.listProjects();
      setProjects(projects);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/");
        return;
      }
      setError("Couldn't load your projects.");
    }
  }

  async function handleCreateProject(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const project = await api.createProject(title, styleReference || undefined);
      setTitle("");
      setStyleReference("");
      setSelectedProjectId(project.id);
      await refreshProjects();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create the project.");
    }
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedProjectId || !file) return;
    setError(null);
    setStatus("Uploading…");
    try {
      const script = await api.uploadScript(selectedProjectId, file);
      setFile(null);
      const query = script.job_id ? `?job=${script.job_id}` : "";
      router.push(`/dashboard/${selectedProjectId}${query}`);
    } catch (err) {
      setStatus(null);
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    }
  }

  return (
    <main className="min-h-screen bg-charcoal px-6 py-10 text-chalk">
      <div className="mx-auto max-w-2xl">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-signal">Production board</p>
        <h1 className="mt-2 text-2xl font-semibold">Your projects</h1>
        <div className="mb-8 mt-4 h-2 w-16 slate-stripe rounded-sm" aria-hidden="true" />

        <section className="mb-10 rounded-lg border border-wire bg-charcoal2 p-5">
          <h2 className="mb-3 font-mono text-xs uppercase tracking-wide text-chalk/50">New project</h2>
          <form onSubmit={handleCreateProject} className="flex flex-col gap-3 sm:flex-row">
            <input
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Project title"
              className="focus-ring flex-1 rounded-md border border-wire bg-charcoal px-3 py-2 outline-none"
            />
            <input
              value={styleReference}
              onChange={(e) => setStyleReference(e.target.value)}
              placeholder="Style reference (optional)"
              className="focus-ring flex-1 rounded-md border border-wire bg-charcoal px-3 py-2 outline-none"
            />
            <button
              type="submit"
              className="focus-ring rounded-md bg-signal px-4 py-2 font-medium text-charcoal hover:brightness-95"
            >
              Create
            </button>
          </form>
        </section>

        <section className="mb-10">
          <h2 className="mb-3 font-mono text-xs uppercase tracking-wide text-chalk/50">Projects</h2>
          {projects === null ? (
            <p className="text-chalk/50">Loading…</p>
          ) : projects.length === 0 ? (
            <p className="text-chalk/50">No projects yet — create one above to get started.</p>
          ) : (
            <ul className="space-y-2">
              {projects.map((p) => (
                <li key={p.id} className="flex items-stretch gap-2">
                  <button
                    onClick={() => setSelectedProjectId(p.id)}
                    className={`focus-ring flex-1 rounded-md border px-4 py-3 text-left transition ${
                      selectedProjectId === p.id
                        ? "border-signal bg-signal/10"
                        : "border-wire bg-charcoal2 hover:border-chalk/30"
                    }`}
                  >
                    <span className="font-medium">{p.title}</span>
                    {p.style_reference && (
                      <span className="ml-2 text-sm text-chalk/50">— {p.style_reference}</span>
                    )}
                  </button>
                  <button
                    onClick={() => router.push(`/dashboard/${p.id}`)}
                    className="focus-ring rounded-md border border-wire px-3 text-sm text-chalk/70 hover:border-chalk/30"
                  >
                    Open
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {selectedProjectId && (
          <section className="rounded-lg border border-wire bg-charcoal2 p-5">
            <h2 className="mb-3 font-mono text-xs uppercase tracking-wide text-chalk/50">Upload script</h2>
            <form onSubmit={handleUpload} className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <input
                type="file"
                accept=".txt,.pdf,text/plain,application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="focus-ring flex-1 text-sm text-chalk/70 file:mr-3 file:rounded-md file:border-0 file:bg-wire file:px-3 file:py-2 file:text-chalk"
              />
              <button
                type="submit"
                disabled={!file}
                className="focus-ring rounded-md bg-signal px-4 py-2 font-medium text-charcoal hover:brightness-95 disabled:opacity-40"
              >
                Upload
              </button>
            </form>
            {status && <p className="mt-3 text-sm text-chalk/60">{status}</p>}
          </section>
        )}

        {error && (
          <p role="alert" className="mt-6 rounded-md border border-signal/40 bg-signal/10 px-3 py-2 text-sm text-signal">
            {error}
          </p>
        )}
      </div>
    </main>
  );
}
