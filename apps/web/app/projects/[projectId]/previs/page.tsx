"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, ProjectDetail, Shot } from "@/lib/api";

const DEFAULT_ACCENT = "#e8a33d";

function shotsToCsv(scenes: ProjectDetail["scenes"]): string {
  const header = ["scene", "shot", "location", "time_of_day", "camera", "characters", "action"];
  const rows = scenes.flatMap((scene) =>
    scene.shots.map((shot) => [
      scene.heading,
      String(shot.shot_number),
      shot.location,
      shot.time_of_day,
      shot.suggested_camera,
      shot.characters.join("; "),
      shot.action_summary,
    ]),
  );
  const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
  return [header, ...rows].map((row) => row.map(escape).join(",")).join("\n");
}

function FrameImage({ url, alt }: { url: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div className="flex aspect-video w-full items-center justify-center rounded-md border border-wire bg-charcoal2 px-3 text-center text-sm text-chalk/40">
        {alt}
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
      className="aspect-video w-full rounded-md border border-wire object-cover"
    />
  );
}

function ShotCard({ shot }: { shot: Shot }) {
  return (
    <div className="rounded-lg border border-wire bg-charcoal2 p-4">
      {shot.frame ? (
        <FrameImage url={shot.frame.image_url} alt={shot.frame.alt_text} />
      ) : (
        <div className="flex aspect-video w-full items-center justify-center rounded-md border border-wire bg-charcoal text-sm text-chalk/40">
          No frame yet
        </div>
      )}
      <p className="mt-3 text-sm text-chalk/40">Shot {shot.shot_number}</p>
      <p className="mt-1">{shot.action_summary}</p>
      <p className="mt-1 text-sm text-chalk/60">
        {shot.suggested_camera} · {shot.location} · {shot.time_of_day}
      </p>
      <p className="mt-1 text-sm text-chalk/60">
        {shot.characters.length > 0 ? shot.characters.join(", ") : "No characters"}
      </p>
      {shot.needs_review && (
        <p className="mt-2 text-xs" style={{ color: DEFAULT_ACCENT }}>
          Under review
        </p>
      )}
    </div>
  );
}

export default function PrevisPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const router = useRouter();

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && !window.localStorage.getItem("scenecraft_token")) {
      router.push("/");
      return;
    }
    (async () => {
      try {
        const detail = await api.getProject(projectId);
        setProject(detail);
        setSelectedSceneId(detail.scenes[0]?.id ?? null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.push("/");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Couldn't load this previs.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const selectedScene = useMemo(
    () => project?.scenes.find((s) => s.id === selectedSceneId) ?? null,
    [project, selectedSceneId],
  );

  function handleExportCsv() {
    if (!project) return;
    const csv = shotsToCsv(project.scenes);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${project.title.replace(/\s+/g, "-").toLowerCase()}-shot-list.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  if (error) {
    return (
      <main className="min-h-screen bg-charcoal px-6 py-10 text-chalk">
        <p role="alert" className="text-signal">
          {error}
        </p>
      </main>
    );
  }

  if (!project) {
    return (
      <main className="min-h-screen bg-charcoal px-6 py-10 text-chalk">
        <p className="text-chalk/50">Loading…</p>
      </main>
    );
  }

  const accent = project.previs_customization?.accent_color || DEFAULT_ACCENT;

  return (
    <main className="min-h-screen bg-charcoal text-chalk">
      <header className="border-b border-wire px-6 py-6">
        <p className="font-mono text-xs uppercase tracking-[0.3em]" style={{ color: accent }}>
          Previs
        </p>
        <h1 className="mt-2 text-2xl font-semibold">{project.title}</h1>
        {project.previs_customization?.tone_note && (
          <p className="mt-1 text-sm text-chalk/60">{project.previs_customization.tone_note}</p>
        )}
        <button
          onClick={handleExportCsv}
          className="focus-ring mt-4 rounded-md border px-4 py-2 text-sm font-medium transition hover:brightness-95"
          style={{ borderColor: accent, color: accent }}
        >
          Export shot list (CSV)
        </button>
      </header>

      <div className="flex flex-col md:flex-row">
        <nav className="border-b border-wire p-4 md:w-64 md:shrink-0 md:border-b-0 md:border-r">
          <h2 className="mb-2 font-mono text-xs uppercase tracking-wide text-chalk/50">Scenes</h2>
          {project.scenes.length === 0 ? (
            <p className="text-sm text-chalk/40">No scenes yet.</p>
          ) : (
            <ul className="space-y-1">
              {project.scenes.map((scene) => (
                <li key={scene.id}>
                  <button
                    onClick={() => setSelectedSceneId(scene.id)}
                    className={`focus-ring w-full rounded-md px-3 py-2 text-left text-sm transition ${
                      selectedSceneId === scene.id
                        ? "bg-charcoal2 font-medium"
                        : "text-chalk/60 hover:bg-charcoal2/60"
                    }`}
                  >
                    {scene.heading}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>

        <section className="flex-1 p-6">
          {selectedScene ? (
            <>
              <h2 className="mb-4 text-lg font-medium">{selectedScene.heading}</h2>
              {selectedScene.shots.length === 0 ? (
                <p className="text-sm text-chalk/40">No shots in this scene yet.</p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {selectedScene.shots.map((shot) => (
                    <ShotCard key={shot.id} shot={shot} />
                  ))}
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-chalk/40">Select a scene to view its shots.</p>
          )}
        </section>
      </div>
    </main>
  );
}
