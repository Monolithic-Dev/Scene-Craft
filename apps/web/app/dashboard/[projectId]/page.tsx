"use client";

import { use, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError, Job, JobStep, ProjectDetail } from "@/lib/api";
import { subscribeToJobTrace } from "@/lib/firebase";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["complete", "failed_needs_review", "needs_clarification"]);

function statusColor(status: string): string {
  if (status === "failed" || status === "running" || status === "needs_clarification") {
    return "text-signal";
  }
  if (status === "complete") return "text-chalk/70";
  return "text-chalk/40";
}

function stepList(steps: JobStep[]) {
  return (
    <ul className="space-y-2">
      {steps.map((step) => (
        <li key={step.agent} className="flex items-center justify-between text-sm">
          <span className="capitalize">{step.agent.replace("_", " ")}</span>
          <span className={statusColor(step.status)}>
            {step.status.replace("_", " ")}
            {step.total != null ? ` (${step.completed ?? 0}/${step.total})` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

function FrameThumbnail({ url, alt }: { url: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div
        title={alt}
        className="flex h-16 w-24 shrink-0 items-center justify-center overflow-hidden rounded-md border border-wire bg-charcoal px-1 text-center text-[9px] leading-tight text-chalk/40"
      >
        <span className="line-clamp-5">{alt}</span>
      </div>
    );
  }
  // image_url is a local file:// URL in dev / Cloud Storage URL in prod, not
  // a static asset next/image can optimize.
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={alt}
      onError={() => setFailed(true)}
      className="h-16 w-24 shrink-0 rounded-md border border-wire object-cover"
    />
  );
}

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(searchParams.get("job"));
  const [error, setError] = useState<string | null>(null);
  const [iterationText, setIterationText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function refreshProject() {
    try {
      const detail = await api.getProject(projectId);
      setProject(detail);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/");
        return;
      }
      setError(err instanceof ApiError ? err.message : "Couldn't load this project.");
    }
  }

  useEffect(() => {
    if (typeof window !== "undefined" && !window.localStorage.getItem("scenecraft_token")) {
      router.push("/");
      return;
    }
    // Auth-gated data fetch on mount, same pattern as dashboard/page.tsx —
    // react-hooks/set-state-in-effect's cascading-render concern doesn't
    // apply here (there's no local render to synchronize, only a fetch on
    // navigation to this route).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshProject();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // Live agent-trace panel (PHASE-05-ITERATION-AND-TRACE-UI.md SS7):
  // subscribes directly to Firestore when configured (real push updates,
  // no poll delay); falls back to polling GET /jobs/{id} otherwise — same
  // data shape either way, since the trace document mirrors JobResponse.
  useEffect(() => {
    if (!activeJobId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    function handleTerminal(status: string) {
      if (TERMINAL_STATUSES.has(status)) void refreshProject();
    }

    const unsubscribe = subscribeToJobTrace(
      activeJobId,
      (trace) => {
        if (cancelled || !trace) return;
        setJob(trace);
        handleTerminal(trace.status);
      },
      (err) => {
        if (!cancelled) setError(err.message);
      },
    );

    if (unsubscribe) {
      return () => {
        cancelled = true;
        unsubscribe();
      };
    }

    // Firestore not configured — poll instead.
    async function poll() {
      try {
        const current = await api.getJob(activeJobId as string);
        if (cancelled) return;
        setJob(current);
        if (TERMINAL_STATUSES.has(current.status)) {
          handleTerminal(current.status);
          return;
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Couldn't check job status.");
        }
      }
    }
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeJobId]);

  async function handleIterate(e: React.FormEvent) {
    e.preventDefault();
    if (!iterationText.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const { job_id } = await api.iterate(projectId, iterationText.trim());
      setIterationText("");
      setActiveJobId(job_id);
      setJob(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't submit that request.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!project) {
    return (
      <main className="min-h-screen bg-charcoal px-6 py-10 text-chalk">
        <p className="text-chalk/50">Loading…</p>
        {error && (
          <p role="alert" className="mt-3 text-signal">
            {error}
          </p>
        )}
      </main>
    );
  }

  const jobInFlight = job !== null && !TERMINAL_STATUSES.has(job.status);

  return (
    <main className="min-h-screen bg-charcoal px-6 py-10 text-chalk">
      <div className="mx-auto max-w-3xl">
        <button
          onClick={() => router.push("/dashboard")}
          className="focus-ring text-sm text-chalk/50 hover:text-chalk"
        >
          ← Back to projects
        </button>
        <h1 className="mt-3 text-2xl font-semibold">{project.title}</h1>
        {project.style_reference && (
          <p className="mt-1 text-sm text-chalk/50">{project.style_reference}</p>
        )}
        <div className="mb-8 mt-4 h-2 w-16 slate-stripe rounded-sm" aria-hidden="true" />

        {job && jobInFlight && (
          <section className="mb-8 rounded-lg border border-wire bg-charcoal2 p-5">
            <h2 className="mb-3 font-mono text-xs uppercase tracking-wide text-chalk/50">
              Generating…
            </h2>
            {stepList(job.steps)}
          </section>
        )}

        {job?.status === "failed_needs_review" && (
          <p
            role="alert"
            className="mb-8 rounded-md border border-signal/40 bg-signal/10 px-3 py-2 text-sm text-signal"
          >
            Generation needs review: {job.error_detail ?? "an unspecified error occurred."}
          </p>
        )}

        {job?.status === "needs_clarification" && (
          <div className="mb-8 rounded-lg border border-signal/40 bg-signal/10 p-4">
            <p className="text-xs uppercase tracking-wide text-signal">SceneCraft asks</p>
            <p className="mt-1 text-sm text-chalk">{job.error_detail}</p>
          </div>
        )}

        {project.deployed_app_url && (
          <section className="mb-8 rounded-lg border border-wire bg-charcoal2 p-5">
            <h2 className="mb-3 font-mono text-xs uppercase tracking-wide text-chalk/50">
              Live previs
            </h2>
            <a
              href={project.deployed_app_url}
              className="focus-ring inline-block rounded-md bg-signal px-4 py-2 font-medium text-charcoal hover:brightness-95"
            >
              Open previs app →
            </a>
          </section>
        )}

        {project.deployed_app_url && (
          <section className="mb-8 rounded-lg border border-wire bg-charcoal2 p-5">
            <h2 className="mb-3 font-mono text-xs uppercase tracking-wide text-chalk/50">
              Iterate
            </h2>
            <form onSubmit={handleIterate} className="flex gap-3">
              <input
                value={iterationText}
                onChange={(e) => setIterationText(e.target.value)}
                disabled={jobInFlight || submitting}
                placeholder={
                  job?.status === "needs_clarification"
                    ? "Answer SceneCraft's question…"
                    : "e.g. make scene 4 night-time"
                }
                className="focus-ring flex-1 rounded-md border border-wire bg-charcoal px-3 py-2 text-chalk outline-none disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={jobInFlight || submitting || !iterationText.trim()}
                className="focus-ring rounded-md bg-signal px-4 py-2 font-medium text-charcoal hover:brightness-95 disabled:opacity-40"
              >
                Send
              </button>
            </form>
          </section>
        )}

        <section>
          <h2 className="mb-3 font-mono text-xs uppercase tracking-wide text-chalk/50">
            Breakdown
          </h2>
          {project.scenes.length === 0 ? (
            <p className="text-chalk/50">No breakdown yet.</p>
          ) : (
            <ul className="space-y-6">
              {project.scenes.map((scene) => (
                <li key={scene.id}>
                  <h3 className="font-medium">
                    {scene.heading}
                    {scene.needs_review && (
                      <span className="ml-2 text-xs text-signal">needs review</span>
                    )}
                  </h3>
                  <ul className="mt-2 space-y-3 border-l border-wire pl-4">
                    {scene.shots.map((shot) => (
                      <li key={shot.id} className="text-sm">
                        <div className="flex items-start gap-3">
                          {shot.frame && (
                            <FrameThumbnail url={shot.frame.image_url} alt={shot.frame.alt_text} />
                          )}
                          <div>
                            <p>{shot.action_summary}</p>
                            <p className="text-chalk/50">
                              {shot.suggested_camera} ·{" "}
                              {shot.characters.join(", ") || "no characters"}
                            </p>
                            {shot.needs_review && (
                              <p className="text-xs text-signal">needs review</p>
                            )}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </section>

        {error && (
          <p
            role="alert"
            className="mt-6 rounded-md border border-signal/40 bg-signal/10 px-3 py-2 text-sm text-signal"
          >
            {error}
          </p>
        )}
      </div>
    </main>
  );
}
